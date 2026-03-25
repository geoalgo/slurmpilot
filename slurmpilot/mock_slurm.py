"""
Mock Slurm binaries (sbatch, sacct, scancel) using local processes.

Intended for testing without a real Slurm cluster:
- sbatch: launches a bash subprocess and uses its PID as the job id.
- scancel: sends SIGTERM to the process.
- sacct: polls the process state and returns pipe-delimited output in the
  same format as the real sacct command.
"""
import os
import re
import signal
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class _Job:
    jobid: int
    process: subprocess.Popen
    start_time: datetime
    stdout_path: Path | None
    stderr_path: Path | None


def _parse_sbatch_directive(script_text: str, flag: str) -> str | None:
    """Return the value of an `#SBATCH --flag=value` directive, or None."""
    match = re.search(rf"^#SBATCH\s+--{flag}=(.+)$", script_text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _format_elapsed(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class MockSlurm:
    """
    Simulates a Slurm cluster using local processes.

    Usage::

        slurm = MockSlurm()
        jobid = slurm.sbatch(Path("slurm_script.sh"), cwd=Path("/tmp/myjob"))
        output = slurm.sacct([jobid])
        slurm.scancel(jobid)
    """

    SACCT_HEADER = "JobID|Elapsed|Start|State|NodeList|"

    def __init__(self):
        self._jobs: dict[int, _Job] = {}

    def sbatch(
        self,
        script_path: Path,
        cwd: Path | None = None,
        env: dict | None = None,
    ) -> int:
        """
        Launch `script_path` as a local bash process.

        Reads `#SBATCH --output` and `#SBATCH --error` from the script to
        redirect stdout/stderr. Returns the PID as the job id.
        """
        script_path = Path(script_path)
        script_text = script_path.read_text()

        stdout_path = self._resolve_log_path(
            _parse_sbatch_directive(script_text, "output"), cwd
        )
        stderr_path = self._resolve_log_path(
            _parse_sbatch_directive(script_text, "error"), cwd
        )

        for p in (stdout_path, stderr_path):
            if p is not None:
                p.parent.mkdir(parents=True, exist_ok=True)

        stdout_file = open(stdout_path, "w") if stdout_path else subprocess.DEVNULL
        stderr_file = open(stderr_path, "w") if stderr_path else subprocess.DEVNULL

        try:
            process = subprocess.Popen(
                ["bash", str(script_path)],
                cwd=cwd,
                stdout=stdout_file,
                stderr=stderr_file,
                env=env,
            )
        finally:
            # Close parent's copies of the fds; child keeps its own.
            if stdout_file is not subprocess.DEVNULL:
                stdout_file.close()
            if stderr_file is not subprocess.DEVNULL:
                stderr_file.close()

        jobid = process.pid
        self._jobs[jobid] = _Job(
            jobid=jobid,
            process=process,
            start_time=datetime.now(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        return jobid

    def scancel(self, jobid: int) -> None:
        """Send SIGTERM to the process corresponding to `jobid`."""
        job = self._jobs.get(jobid)
        if job is None:
            raise ValueError(f"Unknown job id: {jobid}")
        try:
            os.kill(jobid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # process already finished

    def sacct(self, job_ids: list[int]) -> str:
        """
        Return pipe-delimited sacct output for the given job ids.

        Format matches::

            sacct --format="JobID,Elapsed,start,State,nodelist" -X -p --jobs=...

        State mapping:
        - Process running  → RUNNING
        - Exit code 0      → COMPLETED
        - Exit code < 0    → CANCELLED (killed by signal)
        - Exit code > 0    → FAILED
        """
        lines = [self.SACCT_HEADER]
        for jobid in job_ids:
            job = self._jobs.get(jobid)
            if job is None:
                continue
            lines.append(self._format_sacct_row(job))
        return "\n".join(lines)

    def wait(self, jobid: int, timeout: float = 10.0) -> int:
        """Wait for a job to finish and return its exit code."""
        job = self._jobs[jobid]
        return job.process.wait(timeout=timeout)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_log_path(value: str | None, cwd: Path | None) -> Path | None:
        if value is None:
            return None
        p = Path(value)
        if cwd is not None and not p.is_absolute():
            return cwd / p
        return p

    def _format_sacct_row(self, job: _Job) -> str:
        return_code = job.process.poll()
        if return_code is None:
            state = "RUNNING"
        elif return_code == 0:
            state = "COMPLETED"
        elif return_code < 0:
            state = "CANCELLED"
        else:
            state = "FAILED"

        elapsed = (datetime.now() - job.start_time).total_seconds()
        elapsed_str = _format_elapsed(elapsed)
        start_str = job.start_time.strftime("%Y-%m-%dT%H:%M:%S")
        return f"{job.jobid}|{elapsed_str}|{start_str}|{state}|local|"
