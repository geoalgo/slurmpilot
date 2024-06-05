import dataclasses
import json
import logging
import os
import re
import shutil
import time
from _socket import gaierror
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, List

from invoke import UnexpectedExit
from paramiko.ssh_exception import AuthenticationException

from slurmpilot.callback.callback import SlurmSchedulerCallback
from slurmpilot.config import Config, load_config
from slurmpilot.jobpath import JobPathLogic
from slurmpilot.remote_command import (
    RemoteCommandExecutionFabrik,
    RemoteExecution,
)
from slurmpilot.util import print_table

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)


@dataclass
class JobCreationInfo:
    jobname: str
    entrypoint: str = None
    src_dir: str = None
    # TODO
    # dependencies: List[str] = []

    # ressources
    cluster: str = None
    partition: str = None
    n_cpus: int = 1  # number of cores
    n_gpus: int = None  # number of gpus per node
    mem: int = None  # memory pool for each core in MB
    max_runtime_minutes: int = 60  # max runtime in minutes
    account: str = None
    env: dict = None

    def check_path(self):
        assert Path(
            self.src_dir
        ).exists(), f"The src_dir path {self.src_dir} is missing."
        entrypoint_path = Path(self.src_dir) / self.entrypoint
        assert (
            entrypoint_path.exists()
        ), f"The entrypoint could not be found at {entrypoint_path}."

    def sbatch_preamble(self) -> str:
        """
        Spits a preamble like this one valid for sbatch:
        #SBATCH -p {partition}
        #SBATCH --mem {mem}
        ...
        :return:
        """
        res = ""
        sbatch_line = lambda config: f"#SBATCH {config}\n"
        res += sbatch_line(f"--job-name={self.jobname}")
        res += sbatch_line(f"--output=logs/stdout")
        res += sbatch_line(f"--error=logs/stderr")
        if self.n_cpus:
            res += sbatch_line(f"--cpus-per-task={self.n_cpus}")
        if self.partition:
            res += sbatch_line(f"--partition={self.partition}")
        if self.mem:
            res += sbatch_line(f"--mem={self.mem}")
        if self.n_gpus and self.n_gpus > 0:
            res += sbatch_line(f"--gres=gpu:{self.n_gpus}")
        if self.account:
            res += sbatch_line(f"--account={self.account}")
        if self.max_runtime_minutes:
            assert isinstance(self.max_runtime_minutes, int), "maxruntime must be an integer expressing the number of minutes"
            res += sbatch_line(f"--time={self.max_runtime_minutes}")
        # res += sbatch_line("--chdir .")
        return res

class JobStatus:
    completed: str = "COMPLETED"
    pending: str = "PENDING"
    failed: str = "FAILED"
    running: str = "RUNNING"
    cancelled: str = "CANCELLED"

    def statuses(self):
        return [self.completed, self.pending, self.failed, self.running, self.cancelled]


@dataclass
class JobMetadata:
    user: str
    date: str
    job_creation_info: JobCreationInfo
    cluster: str

    def to_json(self) -> str:
        # The methods `to_json` and `from_json` are there because we have nested dataclasses which makes JobMetadata
        # not directly Json serializable
        class EnhancedJSONEncoder(json.JSONEncoder):
            def default(self, o):
                if dataclasses.is_dataclass(o):
                    return dataclasses.asdict(o)
                return super().default(o)
        return json.dumps(self, cls=EnhancedJSONEncoder)

    @classmethod
    def from_json(cls, string) -> "JobMetadata":
        dict_from_string = json.loads(string)
        dict_from_string["job_creation_info"] = JobCreationInfo(**dict_from_string["job_creation_info"])
        return JobMetadata(
            **dict_from_string,

        )



class SlurmWrapper:
    def __init__(
        self,
        config: Config | None = None,
        clusters: List[str] | None = None,
    ):
        if config is not None:
            self.config = config
        else:
            self.config = load_config()
        if clusters is None:
            clusters = list(self.config.cluster_configs.keys())
        for cluster in clusters:
            assert cluster in self.config.cluster_configs, (
                f"config not found for cluster {cluster}, "
                f"available clusters: {self.config.cluster_configs.keys()}"
            )
        self.clusters = clusters
        self.job_scheduling_callback = SlurmSchedulerCallback()
        self.connections = {}
        for cluster, config in self.config.cluster_configs.items():
            if cluster in clusters:
                self.connections[cluster] = RemoteCommandExecutionFabrik(master=config.host, user=config.user if config.user else os.getenv("USER"))
                try:
                    logger.debug(f"Try sending command to {cluster}.")
                    self.job_scheduling_callback.on_establishing_connection(cluster=cluster)
                    self.connections[cluster].run("ls")
                except (gaierror, AuthenticationException) as e:
                    raise ValueError(f"Cannot connect to cluster {cluster}. Verify your ssh access.")

    def list_clusters(self, cluster: str | None = None) -> List[str]:
        # return a list consisting of the provided cluster if not None or all the clusters if None
        return [cluster] if cluster else self.clusters

    def print_utilisation(self, cluster: str | None = None) -> None:
        for cluster_to_show in self.list_clusters(cluster):
            print(cluster_to_show)
            res = self.connections[cluster_to_show].run("sfree", pty=True)
            print(res.stdout)

    def schedule_job(self, job_info: JobCreationInfo, dryrun: bool = False) -> int:
        # TODO support passing all arguments directly instead of intermediate object
        """
        remote location {slurmpilot_remote}/{jobname} stores:
        * stderr/
        * stdout/
        * slurm_command.sh
        * possible artifacts written by script
        * source dir provided in job_info
        :param dryrun: whether to run a dry run mode which only sends the source remotely but does
        not schedule the job on slurm
        :return: slurm job id if not running in `dry_run` mode
        """
        job_info.check_path()
        cluster_connection = self.connections[job_info.cluster]
        self.job_scheduling_callback.on_job_scheduled_start(cluster=job_info.cluster, jobname=job_info.jobname)
        # generate slurm launcher script in slurmpilot dir
        local_job_paths = self._generate_local_folder(job_info)

        # tar and send slurmpilot dir
        remote_job_paths = self.remote_path(job_info)
        self.job_scheduling_callback.on_sending_artifact(
            localpath=str(local_job_paths.resolve_path()),
            remotepath=str(remote_job_paths.resolve_path()),
            cluster=job_info.cluster,
            # f"Preparing local folder at {local_job_paths.resolve_path()}"
        )

        cluster_connection.upload_folder(
            local_job_paths.job_path(), remote_job_paths.job_path().parent
        )

        # call sbatch remotely
        if not dryrun:
            jobid = self._call_sbatch_remotely(
                cluster_connection, local_job_paths, remote_job_paths,
                sbatch_env=job_info.env if job_info.env else {},
            )
            self.job_scheduling_callback.on_job_submitted_to_slurm(jobname=job_info.jobname, jobid=jobid)
            return jobid
        else:
            return None

    def stop_job(self, jobname: str):
        metadata = self.job_creation_metadata(jobname)
        jobid = self.jobid_from_jobname(jobname)
        self.connections[metadata["cluster"]].run(f"scancel {jobid}")

    def wait_completion(
        self,
        jobname: str,
        max_seconds: int = 60,
    ) -> str:
        """
        :param max_seconds: waits for the given number of seconds if defined else waits for status COMPLETED or FAILED
        :return: final status polled
        """
        self.job_scheduling_callback.on_suggest_command_before_wait_completion(jobname=jobname)
        from rich.live import Live
        from rich.text import Text
        from rich.spinner import Spinner
        starttime = time.time()
        spinner_name = "dots"
        current_status = self.status(jobname)
        text = f"Waiting job to finish, current status {current_status}"
        wait_interval = 1
        with Live(Spinner(spinner_name, text=Text(text, style="green")), refresh_per_second=20) as live:
            i = 0
            while (
                    current_status in [JobStatus.pending, JobStatus.running] and wait_interval * i < max_seconds
            ):
                current_status = self.status(jobname)
                text = (f"Waiting job to finish, current status {current_status} (updated every {wait_interval}s, "
                        f"waited for {int(time.time() - starttime)}s)")
                live.renderable.update(text=Text(text, style="green"))
                time.sleep(wait_interval)  # todo exponential backoff to avoid QOS issues
                i += 1
        return current_status

    def _call_sbatch_remotely(
        self,
        cluster_connection: RemoteExecution,
        local_job_paths: JobPathLogic,
        remote_job_path: JobPathLogic,
        sbatch_env: dict,
    ) -> int:
        # call sbatch remotely and returns slurm job id if successful
        if sbatch_env:
            # pass environment variable to sbatch in the following form:
            # sbatch --export=REPS=500,X='test' slurm_script.sh
            export_env = "--export=ALL,"
            export_env += ",".join(f"{var_name}={var_value}" for var_name, var_value in sbatch_env.items())
        else:
            export_env = ""
        try:
            # TODO import make those idempotent, running `sbatch slurm_script.sh` or `sbatch path_to_script/slurm_script.sh`
            #  should work no matter the directory and variables should be saved for easier reproducibility
            res = cluster_connection.run(
                f"cd {remote_job_path.job_path()}; mkdir -p logs/; sbatch {export_env} slurm_script.sh",
                env={
                    # "SLURMPILOT_PATH": remote_job_path.slurmpilot_path(),
                    # TODO FIXME HIGH priority
                    #  1) consider evaluating a path on remote to fix the issue
                    "SLURMPILOT_PATH": "/p/home/jusers/salinas2/juwels/salinas2/slurmpilot",
                    "SLURMPILOT_JOBPATH": remote_job_path.resolve_path(),
                }
            )
        except UnexpectedExit as e:
            raise ValueError("Could not execute sbatch on the remote host, error:" + str(e))
        if res.failed:
            raise ValueError(
                f"Could not submit job, got the following error:\n{res.stderr}"
            )
        elif len(res.stderr) > 0:
            raise ValueError(
                f"Could not submit job, got the following error:\n{res.stderr}"
            )
        else:
            # should be something like 'Submitted batch job 11301013'
            stdout = res.stdout
            slurm_submitted_msg = "Submitted batch job "
            if stdout.startswith(slurm_submitted_msg):
                matches = re.match(slurm_submitted_msg + r"(\d*)", stdout)
                logging.debug(stdout)
                jobid = int(matches.groups()[0])
                # Save the jobid locally so that we can later maps jobname to jobid for slurm query
                # We do not save it remotely as it does not seem necessary but we could if needed
                self._save_jobid(local_job_paths, jobid)
                return jobid
            else:
                raise ValueError(
                    f"Job scheduled without error but could not parse slurm output: {stdout}"
                )

    def remote_path(self, job_info: JobCreationInfo):
        return JobPathLogic(
            jobname=job_info.jobname,
            entrypoint=job_info.entrypoint,
            src_dir_name=Path(job_info.src_dir).name if job_info.src_dir else None,
            root_path=self.config.remote_slurmpilot_path(job_info.cluster),
        )

    def _generate_local_folder(self, job_info: JobCreationInfo):
        local_job_paths = JobPathLogic(
            jobname=job_info.jobname,
            entrypoint=job_info.entrypoint,
            src_dir_name=Path(job_info.src_dir).resolve().name,
            root_path=self.config.local_slurmpilot_path(),
        )
        assert (
            not local_job_paths.job_path().exists()
        ), f"jobname {job_info.jobname} has already been used, jobnames must be unique please use another one"

        # copy source, generate main slurm script and metadata
        shutil.copytree(src=job_info.src_dir, dst=local_job_paths.src_path())
        self._generate_main_slurm_script(local_job_paths, job_info)
        self._generate_metadata(local_job_paths, job_info)
        return local_job_paths

    def _generate_main_slurm_script(
        self, local_job_paths: JobPathLogic, job_info: JobCreationInfo
    ):
        with open(local_job_paths.slurm_entrypoint_path(), "w") as f:
            f.write("#!/bin/bash\n")
            f.write(job_info.sbatch_preamble())
            f.write(f"bash {local_job_paths.entrypoint_path_from_cwd()}\n")

    def _save_jobid(self, local_job_paths: JobPathLogic, jobid: int):
        metadata = {
            "jobid": jobid,
        }
        with open(local_job_paths.jobid_path(), "w") as f:
            f.write(json.dumps(metadata))

    def log(self, jobname: str, cluster: str | None = None):
        if cluster is None:
            cluster = self.cluster(jobname)
        local_path = JobPathLogic(jobname=jobname)
        self._download_logs(local_path, cluster=cluster, jobname=jobname)
        if local_path.stderr_path().exists():
            with open(local_path.stderr_path()) as f:
                stderr = "".join(f.readlines())
        else:
            stderr = None
        if local_path.stdout_path().exists():
            with open(local_path.stdout_path()) as f:
                stdout = "".join(f.readlines())
        else:
            stdout = None
        return stdout, stderr

    def print_log(self, jobname: str | None = None):
        """
        :param jobname: if not specified uses the last job
        :return: print log of specified job
        """
        if jobname is None:
            jobname = self.latest_job()
            print(f"No jobname was passed, showing log of latest job {jobname}")
        cluster = self.cluster(jobname)
        stderr, stdout = self.log(jobname=jobname, cluster=cluster)
        if stderr:
            print(f"stderr:\n{stderr}")
        if stdout:
            print(f"stdout:\n{stdout}")

    def latest_job(self) -> str:
        files = list((self.config.local_slurmpilot_path() / "jobs").expanduser().glob("*"))
        if len(files) > 0:
            latest_file = max(
                [f for f in files if f.is_dir()], key=lambda item: item.stat().st_ctime
            )
            jobname = Path(latest_file).name
            return jobname
        raise ValueError(f"No job was found at {self.config.local_slurmpilot_path()}")

    def cluster(self, jobname: str):
        """
        :param jobname:
        :return: retrieves the cluster where `jobname` was launched by querying local files
        """
        job_metadata = self.job_creation_metadata(jobname=jobname)
        return job_metadata["cluster"]

    def list_jobs(self) -> List[JobMetadata]:
        files = list((self.config.local_slurmpilot_path() / "jobs").expanduser().glob("*"))
        rows = []
        for file in files:
            if not file.is_file() and (file / "metadata.json").exists():
                print(file)
                with open(file / "metadata.json", "r") as f:
                    try:
                        rows.append(JobMetadata.from_json(f.readline()))
                    except json.decoder.JSONDecodeError:
                        pass
        return rows

    def list_jobs_slurm(
        self,
        cluster: str | None = None,
        print_list: bool = True,
        sacct_format: str | None = None,
    ) -> List[dict]:
        """
        :return: fetch information from Slurm for each job containing JobID,JobName%30,Partition,Elapsed,State%15
        """
        rows = []
        for cluster in self.list_clusters(cluster):
            if sacct_format is None:
                sacct_format = "JobName,Elapsed,Partition,start,State"
            res = self.connections[cluster].run(
                f'sacct --format="{sacct_format}" -X -p'
            )
            lines = res.stdout.split("\n")
            keys = lines[0].split("|")[:-1]
            for line in lines[1:]:
                if line:
                    rows.append(dict(zip(keys, line.split("|")[:-1])))
                    rows[-1]["cluster"] = cluster
            if print_list:
                print_table(rows)
        return rows

    def download_job(self, jobname: str | None = None):
        if jobname is None:
            jobname = self.latest_job()
        cluster = self.cluster(jobname)
        local_path = JobPathLogic(jobname=jobname)
        remote_path = JobPathLogic.from_jobname(
            jobname=jobname,
            root_path=self.config.remote_slurmpilot_path(cluster),
        )
        self.connections[cluster].download_folder(
            remote_path.resolve_path(),
            local_path.resolve_path(),
        )

    def _download_logs(self, local_path, cluster: str, jobname: str):
        # 1) download log from remote file
        # 2) show in console
        # we could also consider streaming
        remote_path = JobPathLogic.from_jobname(
            jobname=jobname,
            root_path=self.config.remote_slurmpilot_path(cluster),
        )
        try:
            self.connections[cluster].download_file(
                remote_path.stderr_path(), local_path.stderr_path()
            )
            self.connections[cluster].download_file(
                remote_path.stdout_path(), local_path.stdout_path()
            )
        except FileNotFoundError:
            return ""

    def status(self, jobname: str):
        """sacct --jobs=11301195 --format=State -X"""
        cluster = self.job_creation_metadata(jobname)["cluster"]
        jobid = self.jobid_from_jobname(jobname)
        res = self.connections[cluster].run(
            f"sacct --jobs={jobid} --format=State -X -p"
        )
        stdout = res.stdout
        # TODO a bit fragile
        assert "State" in stdout
        status = res.stdout.split("|")[1].strip("\n")
        if "CANCELLED" in status:
            # 'CANCELLED by 25416' -> CANCELLED
            status = status.split(" ")[0]
        if len(status) == 0:
            return JobStatus.pending
        else:
            assert (
                status in JobStatus().statuses()
            ), f"status {status} not in {JobStatus().statuses()}"
            return status

    def jobid_from_jobname(self, jobname: str) -> int:
        # several options are possible:
        # 1) store info in jobname folder
        # 2) runs sacct -X --format=jobname%30,jobid remotely and parse output
        # 3) store mapping locally in DB
        # We choose here the first one because it avoids a remote/call parsing or to setup a DB

        # Option 2)
        # res = self.connection.run(f"sacct -X --format=jobname%30,jobid  | grep {jobname} | tail -n 1")
        # # "example-j+ 11301527" -> 11301527
        # return int(res.stdout.split(" ")[-1])
        local_path = JobPathLogic(jobname=jobname)
        with open(local_path.jobid_path(), "r") as f:
            return json.load(f)["jobid"]

    def job_creation_metadata(self, jobname: str) -> dict:
        local_path = JobPathLogic(jobname=jobname)
        with open(local_path.metadata_path(), "r") as f:
            return json.load(f)

    def _generate_metadata(self, local_path: JobPathLogic, job_info: JobCreationInfo):
        metadata = JobMetadata(
            user=os.getenv("USER"),
            date=str(datetime.now()),
            job_creation_info=job_info,
            cluster=job_info.cluster,
        )
        with open(local_path.metadata_path(), "w") as f:
            f.write(metadata.to_json())
