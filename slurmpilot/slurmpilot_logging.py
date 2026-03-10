"""User-facing console output for SlurmPilot operations."""
from pathlib import Path

_RESET = "\033[0m"
_CYAN = "\033[1;30;34m"  # cluster
_PINK = "\033[1;31;31m"  # jobname / paths
_GREEN = "\033[1;32m"   # job id


def _cluster(text) -> str:
    return f"{_CYAN}{text}{_RESET}"


def _jobname(text) -> str:
    return f"{_PINK}{text}{_RESET}"


def _jobid(text) -> str:
    return f"{_GREEN}{text}{_RESET}"


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1_000:
        return f"{size_bytes} B"
    elif size_bytes < 1_000_000:
        return f"{size_bytes / 1_000:.1f} KB"
    elif size_bytes < 1_000_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    else:
        return f"{size_bytes / 1_000_000_000:.1f} GB"


class SlurmPilotLogging:
    def connecting(self, cluster: str) -> None:
        print(f"Establishing ssh connection with {_cluster(cluster)}")

    def start_job(self, jobname: str, cluster: str) -> None:
        print(f"Starting job {_jobname(jobname)} on {_cluster(cluster)}.")

    def send_data(self, local_path: Path, cluster: str, remote_path: Path) -> None:
        size_bytes = sum(f.stat().st_size for f in Path(local_path).rglob("*") if f.is_file())
        print(
            f"Sending job data from {_jobname(local_path)} to "
            f"{_cluster(cluster)}:{_jobname(remote_path)} ({_human_size(size_bytes)})"
        )

    def job_submitted(self, cluster: str, jobid: int) -> None:
        print(
            f"\nJob submitted to Slurm / {_cluster(cluster)} with id {_jobid(jobid)} "
            f"saving the jobid locally."
        )

    def job_tips(self, jobname: str) -> None:
        print(
            f"\nYou can use the following commands in a terminal:\n"
            f"📋 show the log of your job: {_cluster(f'sp log {jobname}')}\n"
            f"📥 sync the artifact of your job: {_cluster(f'sp download {jobname}')}\n"
            f"📊 show the status of your job: {_cluster(f'sp status {jobname}')}\n"
            f"🛑 stop your job: {_cluster(f'sp stop {jobname}')}"
        )


if __name__ == "__main__":
    log = SlurmPilotLogging()
    cluster = "kislurm"
    jobname = "examples/hello-cluster/job-hopeful-brawny-spoonbill-from-sirius"
    local_path = Path(f"/Users/salinasd/slurmpilot/jobs/{jobname}")
    remote_path = Path(f"~/slurmpilot/jobs/{jobname}")

    log.connecting(cluster)
    log.start_job(jobname, cluster)
    log.send_data(local_path, cluster, remote_path)
    log.job_submitted(cluster, jobid=27495955)
    log.job_tips(jobname)
