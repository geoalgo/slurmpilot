import json
import logging
import re
import shlex
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from .config import Config, default_cluster_and_partition, load_config  # noqa: F401
from .job_creation_info import JobCreationInfo  # noqa: F401
from .job_metadata import JobMetadata
from .job_path import JobPath
from .mock_slurm import MockSlurm
from .remote_command import LocalExecution, RemoteExecution, SSHExecution
from .slurm_script import generate_slurm_script
from .slurmpilot_logging import SlurmPilotLogging
from .util import unify  # noqa: F401

logger = logging.getLogger(__name__)

MOCK_CLUSTER = "mock"
LOCAL_CLUSTER = "local"

# sacct format used throughout — must match MockSlurm.SACCT_HEADER
SACCT_FORMAT = "JobID,Elapsed,start,State,nodelist"

TERMINAL_STATES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY"})


@dataclass
class QueuePosition:
    """Position and priority of a pending job within its partition queue.

    Attributes:
        jobid: Slurm job id.
        partition: The partition the job is queued in.
        priority: This job's Slurm priority score, or None if not found in the queue.
        position: 1-based rank among PENDING jobs sorted by priority (descending),
                  or None if the job is not currently pending (e.g. already running).
        total_pending: Total number of PENDING jobs in the partition.
        top_priority: Priority score of the highest-priority pending job, or None if
                      there are no pending jobs.
    """

    jobid: int
    partition: str
    priority: int | None
    position: int | None
    total_pending: int
    top_priority: int | None


def _parse_squeue_rows(output: str) -> list[dict]:
    """Parse pipe-delimited squeue output into a list of row dicts.

    Expected format (one line per job, no header)::

        squeue -h -o "%i|%Q|%T"

    Returns dicts with keys ``jobid`` (int), ``priority`` (int), ``state`` (str).
    Lines that cannot be parsed are silently skipped.
    """
    rows = []
    for line in output.strip().splitlines():
        parts = line.strip().split("|")
        if len(parts) < 3:
            continue
        try:
            rows.append({
                "jobid": int(parts[0].strip()),
                "priority": int(parts[1].strip()),
                "state": parts[2].strip(),
            })
        except ValueError:
            continue
    return rows


def _compute_queue_position(jobid: int, partition: str, rows: list[dict]) -> QueuePosition:
    """Derive a :class:`QueuePosition` from parsed squeue rows.

    *rows* must already be sorted by priority descending (as returned by
    ``squeue --sort=-Q``).  Only ``PENDING`` rows are considered for ranking.
    """
    pending = [r for r in rows if r["state"] == "PENDING"]
    total_pending = len(pending)
    top_priority = pending[0]["priority"] if pending else None

    position: int | None = None
    priority: int | None = None
    for i, row in enumerate(pending):
        if row["jobid"] == jobid:
            position = i + 1
            priority = row["priority"]
            break

    return QueuePosition(
        jobid=jobid,
        partition=partition,
        priority=priority,
        position=position,
        total_pending=total_pending,
        top_priority=top_priority,
    )


class SlurmPilot:
    """Schedules and monitors Slurm jobs.

    Supported cluster values:
        - ``"mock"``: runs jobs as local processes via :class:`MockSlurm` (no
          real Slurm required; useful for testing).
        - ``"local"``: calls the real sbatch/sacct/scancel binaries on the
          local machine.
        - any other string: treated as a hostname (or alias defined in
          ``config.cluster_configs``) and accessed via SSH.

    Job files are stored locally under ``config.local_slurmpilot_path()/jobs/{jobname}/``.
    """

    def __init__(
        self,
        config: Config | None = None,
        clusters: List[str] | None = None,
    ):
        self.config = config if config is not None else load_config()
        self.clusters = clusters or [MOCK_CLUSTER]

        self._log = SlurmPilotLogging()
        self._mock_slurms: dict[str, MockSlurm] = {
            c: MockSlurm() for c in self.clusters if c == MOCK_CLUSTER
        }
        self._connections: dict[str, RemoteExecution] = {}
        for cluster in self.clusters:
            if cluster == MOCK_CLUSTER:
                continue
            elif cluster == LOCAL_CLUSTER:
                self._connections[cluster] = LocalExecution()
            else:
                cfg = self.config.cluster_configs.get(cluster)
                if cfg:
                    self._connections[cluster] = SSHExecution(host=cfg.host, user=cfg.user)
                else:
                    self._connections[cluster] = SSHExecution(host=cluster)

    def schedule_job(self, job_info: JobCreationInfo, dryrun: bool = False) -> int | None:
        """Prepare and submit a job.

        Copies ``src_dir`` to the local job folder, generates ``slurm_script.sh``,
        writes ``metadata.json``, and (unless ``dryrun``) uploads if needed,
        calls sbatch, and writes ``jobid.json``.

        :param job_info: full job specification.
        :param dryrun: if True, prepare all files but do not submit to Slurm.
        :return: Slurm job id, or None in dryrun mode.
        """
        job_info.check_path()

        src_dir_name = Path(job_info.src_dir).resolve().name
        local = JobPath(
            jobname=job_info.jobname,
            root=self.config.local_slurmpilot_path(),
            src_dir_name=src_dir_name,
        )

        if local.job_dir.exists():
            raise ValueError(
                f"Job '{job_info.jobname}' already exists at {local.job_dir}. "
                "Jobnames must be unique."
            )

        shutil.copytree(src=job_info.src_dir, dst=local.src)
        if isinstance(job_info.python_args, list):
            lines = []
            for arg in job_info.python_args:
                if isinstance(arg, dict):
                    lines.append(" ".join(f"--{k}={v}" for k, v in arg.items()))
                else:
                    lines.append(arg)
            (local.job_dir / "python-args.txt").write_text("\n".join(lines) + "\n")
        if job_info.python_libraries:
            for lib in job_info.python_libraries:
                lib_path = Path(lib)
                shutil.copytree(src=lib_path, dst=local.job_dir / lib_path.name)

        job_run_dir = self._job_run_dir(job_info.cluster, local, job_info)
        script = generate_slurm_script(
            job_info=job_info,
            entrypoint_from_cwd=local.entrypoint_from_cwd(job_info.entrypoint),
            job_run_dir=job_run_dir,
        )
        local.slurm_script.write_text(script)
        local.metadata.write_text(
            JobMetadata(
                jobname=job_info.jobname,
                cluster=job_info.cluster,
                date=str(datetime.now()),
                remote_path=job_info.remote_path,
            ).to_json()
        )

        if dryrun:
            return None

        self._log.start_job(job_info.jobname, job_info.cluster)
        jobid = self._submit(job_info, local)
        local.jobid_file.write_text(json.dumps({"jobid": jobid}))
        self._log.job_submitted(job_info.cluster, jobid)
        self._log.job_tips(job_info.jobname)
        return jobid

    def status(self, jobnames: list[str]) -> list[str | None]:
        """Return the Slurm state for each jobname (RUNNING, COMPLETED, FAILED, …).

        Returns ``None`` for jobs whose ``jobid.json`` is missing.
        """
        return [self._single_status(jn) for jn in jobnames]

    def log(self, jobname: str, index: int | None = None) -> tuple[str, str]:
        """Return ``(stdout, stderr)`` for the given job.

        For mock/local clusters the logs are read directly from the local job
        directory.  For SSH clusters the log folder is downloaded first.

        :param index: task index for job arrays (not yet supported).
        :return: ``(stdout, stderr)``; empty strings if not yet written.
        """
        local = JobPath(jobname=jobname, root=self.config.local_slurmpilot_path())
        cluster = self._read_cluster(jobname)

        if cluster is not None and cluster not in (MOCK_CLUSTER, LOCAL_CLUSTER):
            self._download_logs(cluster, jobname, local)

        stdout = local.stdout.read_text(errors="replace") if local.stdout.exists() else ""
        stderr = local.stderr.read_text(errors="replace") if local.stderr.exists() else ""
        return stdout, stderr

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remote_root(self, job_info: JobCreationInfo) -> Path:
        """Remote slurmpilot root for this job (job_info.remote_path overrides cluster config)."""
        if job_info.remote_path:
            return Path(job_info.remote_path)
        return self.config.remote_slurmpilot_path(job_info.cluster)

    def _job_run_dir(self, cluster: str, local: JobPath, job_info: JobCreationInfo | None = None) -> Path:
        """Working directory on the execution host embedded in the Slurm script."""
        if cluster in (MOCK_CLUSTER, LOCAL_CLUSTER):
            return local.job_dir
        root = self._remote_root(job_info) if job_info else self.config.remote_slurmpilot_path(cluster)
        return JobPath(
            jobname=local.jobname,
            root=root,
        ).job_dir

    def _submit(self, job_info: JobCreationInfo, local: JobPath) -> int:
        cluster = job_info.cluster
        if cluster == MOCK_CLUSTER:
            return self._mock_slurms[cluster].sbatch(
                script_path=local.slurm_script,
                cwd=local.job_dir,
                env=job_info.env or None,
            )
        connection = self._connections[cluster]
        if cluster == LOCAL_CLUSTER:
            job_dir = local.job_dir
        else:
            # Upload the local job folder to the remote host first.
            remote = JobPath(
                jobname=job_info.jobname,
                root=self._remote_root(job_info),
            )
            self._log.connecting(cluster)
            self._log.send_data(local.job_dir, cluster, remote.job_dir)
            connection.upload_folder(local.job_dir, remote.job_dir.parent)
            job_dir = remote.job_dir
        return _call_sbatch(connection, job_dir, job_info.jobname, job_info.env)

    def _single_status(self, jobname: str) -> str | None:
        jobid = self._read_jobid(jobname)
        if jobid is None:
            return None
        cluster = self._read_cluster(jobname)
        if cluster is None:
            return None
        if cluster == MOCK_CLUSTER:
            sacct_out = self._mock_slurms[cluster].sacct([jobid])
        else:
            result = self._connections[cluster].run(
                f'sacct --format="{SACCT_FORMAT}" -X -p --jobs={jobid}'
            )
            if result.failed:
                logger.warning(f"sacct failed for {jobname}: {result.stderr}")
                return None
            sacct_out = result.stdout
        return _parse_sacct_state(sacct_out, jobid)

    def _download_logs(self, cluster: str, jobname: str, local: JobPath) -> None:
        remote = JobPath(
            jobname=jobname,
            root=self._remote_root_for_job(jobname, cluster),
        )
        try:
            self._connections[cluster].download_folder(remote.log_dir, local.log_dir.parent)
        except Exception as e:
            logger.warning(f"Could not download logs for {jobname}: {e}")

    def _read_jobid(self, jobname: str) -> int | None:
        f = JobPath(jobname=jobname, root=self.config.local_slurmpilot_path()).jobid_file
        if not f.exists():
            return None
        return json.loads(f.read_text())["jobid"]

    def _read_metadata(self, jobname: str) -> JobMetadata | None:
        f = JobPath(jobname=jobname, root=self.config.local_slurmpilot_path()).metadata
        if not f.exists():
            return None
        return JobMetadata.from_json(f.read_text())

    def _read_cluster(self, jobname: str) -> str | None:
        meta = self._read_metadata(jobname)
        return meta.cluster if meta else None

    def _remote_root_for_job(self, jobname: str, cluster: str) -> Path:
        """Remote slurmpilot root for an existing job, using stored remote_path if present."""
        meta = self._read_metadata(jobname)
        if meta and meta.remote_path:
            return Path(meta.remote_path)
        return self.config.remote_slurmpilot_path(cluster)

    def sacct_info(self, jobnames: list[str]) -> list[dict]:
        """Return full sacct info for each jobname, batched by cluster.

        Each dict has keys: ``jobname``, ``jobid``, ``task_id``, ``cluster``,
        ``creation``, ``elapsed``, ``state``, ``nodelist``.
        """
        from collections import defaultdict
        by_cluster: dict[str, list[tuple[JobMetadata, int]]] = defaultdict(list)
        for jn in jobnames:
            meta = self._read_metadata(jn)
            jobid = self._read_jobid(jn)
            if meta and jobid is not None:
                by_cluster[meta.cluster].append((meta, jobid))

        rows = []
        for cluster, pairs in by_cluster.items():
            jobid_to_meta = {jid: meta for meta, jid in pairs}
            job_ids_str = ",".join(str(jid) for _, jid in pairs)
            if cluster == MOCK_CLUSTER:
                sacct_out = self._mock_slurms[cluster].sacct([jid for _, jid in pairs])
            else:
                result = self._connections[cluster].run(
                    f'sacct --format="{SACCT_FORMAT}" -X -p --jobs={job_ids_str}'
                )
                if result.failed:
                    logger.warning(f"sacct failed for cluster {cluster}: {result.stderr}")
                    continue
                sacct_out = result.stdout

            for line in sacct_out.strip().split("\n")[1:]:
                parts = [p.strip() for p in line.split("|")]
                if not parts or not parts[0]:
                    continue
                raw_id, task_id = (parts[0].split("_") + [None])[:2]
                try:
                    jobid = int(raw_id)
                except ValueError:
                    continue
                meta = jobid_to_meta.get(jobid)
                if meta is None:
                    continue
                try:
                    parsed_task_id = int(task_id) if task_id is not None else None
                except ValueError:
                    parsed_task_id = None
                rows.append({
                    "jobname":  meta.jobname,
                    "jobid":    raw_id,
                    "task_id":  parsed_task_id,
                    "cluster":  cluster,
                    "creation": meta.date,
                    "elapsed":  parts[1] if len(parts) > 1 else "",
                    "state":    parts[3] if len(parts) > 3 else None,
                    "nodelist": parts[4] if len(parts) > 4 else "",
                })
        return rows

    def stop_job(self, jobname: str) -> None:
        """Cancel a running job via scancel (or MockSlurm for mock clusters)."""
        jobid = self._read_jobid(jobname)
        if jobid is None:
            raise ValueError(f"No jobid found for '{jobname}'")
        cluster = self._read_cluster(jobname)
        if cluster is None:
            raise ValueError(f"No metadata found for '{jobname}'")
        if cluster == MOCK_CLUSTER:
            self._mock_slurms[cluster].scancel(jobid)
        else:
            result = self._connections[cluster].run(f"scancel {jobid}")
            if result.failed:
                raise RuntimeError(f"scancel failed:\n{result.stderr}")

    def stop_all_jobs(self, clusters: list[str] | None = None) -> list[str]:
        """Cancel all tracked jobs on *clusters* (defaults to all known clusters).

        Batches scancel calls per cluster. Returns list of cancelled jobnames.
        """
        from collections import defaultdict

        from job_metadata import list_metadatas

        targets = set(clusters) if clusters else set(self.clusters)
        jobs_root = self.config.local_slurmpilot_path() / "jobs"
        metadatas = [m for m in list_metadatas(jobs_root) if m.cluster in targets]

        by_cluster: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for meta in metadatas:
            jobid = self._read_jobid(meta.jobname)
            if jobid is not None:
                by_cluster[meta.cluster].append((meta.jobname, jobid))

        cancelled = []
        for cluster, pairs in by_cluster.items():
            jobids_str = " ".join(str(jid) for _, jid in pairs)
            if cluster == MOCK_CLUSTER:
                for _, jid in pairs:
                    try:
                        self._mock_slurms[cluster].scancel(jid)
                    except Exception:
                        pass
            else:
                result = self._connections[cluster].run(f"scancel {jobids_str}")
                if result.failed:
                    logger.warning(f"scancel failed on {cluster}: {result.stderr}")
                    continue
            cancelled.extend(jn for jn, _ in pairs)
        return cancelled

    def test_ssh(self, cluster: str) -> bool:
        """Return True if an SSH connection to *cluster* can run a command."""
        if cluster in (MOCK_CLUSTER, LOCAL_CLUSTER):
            return True
        result = self._connections[cluster].run("hostname")
        return not result.failed

    def download_job(self, jobname: str) -> None:
        """Download the full remote job folder to the local machine.

        No-op for mock/local clusters (already local).
        """
        cluster = self._read_cluster(jobname)
        if cluster is None:
            raise ValueError(f"No metadata found for '{jobname}'")
        if cluster in (MOCK_CLUSTER, LOCAL_CLUSTER):
            return
        local = JobPath(jobname=jobname, root=self.config.local_slurmpilot_path())
        remote = JobPath(jobname=jobname, root=self._remote_root_for_job(jobname, cluster))
        self._connections[cluster].download_folder(remote.job_dir, local.job_dir.parent)

    def local_job_path(self, jobname: str) -> Path:
        """Return the local job directory for ``jobname``."""
        return JobPath(jobname=jobname, root=self.config.local_slurmpilot_path()).job_dir

    def remote_job_path(self, jobname: str) -> Path | None:
        """Return the remote job directory, or None for mock/local clusters."""
        cluster = self._read_cluster(jobname)
        if cluster is None or cluster in (MOCK_CLUSTER, LOCAL_CLUSTER):
            return None
        return JobPath(
            jobname=jobname,
            root=self._remote_root_for_job(jobname, cluster),
        ).job_dir

    def queue_position(self, jobname: str) -> QueuePosition | None:
        """Return the queue position of a pending job within its partition.

        Runs two ``squeue`` calls on the cluster:

        1. ``squeue -j <jobid> -h -o "%P"`` — discover the partition.
        2. ``squeue -p <partition> --sort=-Q -h -o "%i|%Q|%T"`` — list all jobs
           sorted by priority (descending) and compute the rank.

        Returns ``None`` for mock/local clusters or when the job cannot be found.
        The ``position`` field of the returned object is ``None`` when the job
        is no longer ``PENDING`` (e.g. it has started running or already finished).
        """
        jobid = self._read_jobid(jobname)
        cluster = self._read_cluster(jobname)
        if jobid is None or cluster is None or cluster == MOCK_CLUSTER:
            return None

        connection = self._connections[cluster]

        # Step 1: find the partition this job is queued in.
        result = connection.run(f'squeue -j {jobid} -h -o "%P"')
        if result.failed or not result.stdout.strip():
            logger.warning(f"squeue could not find job {jobid} on {cluster}")
            return None
        partition = result.stdout.strip().splitlines()[0].strip()

        # Step 2: list all jobs in that partition sorted by priority descending.
        result = connection.run(f'squeue -p {partition} --sort=-Q -h -o "%i|%Q|%T"')
        if result.failed:
            logger.warning(f"squeue failed on {cluster}: {result.stderr}")
            return None

        rows = _parse_squeue_rows(result.stdout)
        return _compute_queue_position(jobid, partition, rows)

    def wait_completion(self, jobname: str, max_seconds: int = 60) -> str | None:
        """Poll until the job reaches a terminal state or ``max_seconds`` elapse.

        :return: final Slurm state string, or ``None`` if status could not be determined.
        """
        terminal = TERMINAL_STATES
        deadline = time.time() + max_seconds
        status = None
        while time.time() < deadline:
            status = self._single_status(jobname)
            logger.info(f"Job '{jobname}' status: {status}")
            if status in terminal:
                break
            time.sleep(5)
        return status


# ------------------------------------------------------------------
# Module-level helpers for real Slurm CLI calls
# ------------------------------------------------------------------

def _call_sbatch(
    connection: RemoteExecution,
    job_dir: Path,
    jobname: str,
    env: dict | None,
) -> int:
    """Run sbatch in ``job_dir`` via ``connection`` and return the Slurm job id."""
    env_vars = {"SP_JOBNAME": jobname}
    if env:
        env_vars.update(env)
    export = "--export=ALL," + ",".join(
        f"{k}={shlex.quote(str(v))}" for k, v in env_vars.items()
    )
    result = connection.run(
        f"cd {str(job_dir)} && mkdir -p logs && sbatch {export} slurm_script.sh"
    )
    if result.failed:
        raise RuntimeError(f"sbatch failed:\n{result.stderr}")
    match = re.search(r"Submitted batch job (\d+)", result.stdout)
    if not match:
        raise RuntimeError(f"Could not parse sbatch output: {result.stdout!r}")
    return int(match.group(1))


def _parse_sacct_state(sacct_output: str, jobid: int) -> str | None:
    """Parse pipe-delimited sacct output and return the State for ``jobid``.

    Handles plain jobs (``jobid``) and job arrays (``jobid_N``).
    For job arrays, returns the first non-terminal state found so that
    wait_completion keeps polling until all tasks finish.
    """
    jobid_str = str(jobid)
    states = []
    for line in sacct_output.strip().split("\n")[1:]:  # skip header
        parts = [p.strip() for p in line.split("|")]
        if not parts:
            continue
        raw_id = parts[0].split("_")[0]  # strip array suffix e.g. 123_0 -> 123
        if raw_id == jobid_str and len(parts) > 3:
            states.append(parts[3])
    if not states:
        return None
    # Return the first non-terminal state (job still running), or the last state if all terminal
    for s in states:
        if s not in TERMINAL_STATES:
            return s
    return states[-1]
