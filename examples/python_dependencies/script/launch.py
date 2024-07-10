"""
Example that shows how to launch a script that requires a library from another folder that is being copied over
 and added to Python path by Slurmpilot.
"""
import logging
import os
from pathlib import Path

from slurmpilot.slurm_wrapper import SlurmWrapper, JobCreationInfo
from slurmpilot.util import unify

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    cluster = "meta"
    partition = "mldlc_gpu-rtx2080"

    jobname = unify("custom-library", method="coolname")  # make the jobname unique by appending a coolname
    slurm = SlurmWrapper(clusters=[cluster])
    max_runtime_minutes = 60
    root_dir = Path(__file__).parent
    jobinfo = JobCreationInfo(
        cluster=cluster,
        jobname=jobname,
        entrypoint="main.sh",
        src_dir=str(root_dir),
        python_libraries=[str(root_dir.parent / "custom_library")],
        partition=partition,
        n_cpus=1,
        max_runtime_minutes=max_runtime_minutes,
        # Shows how to pass an environment variable to the running script
        env={"API_TOKEN": "DUMMY"},
    )
    jobid = slurm.schedule_job(jobinfo)

    slurm.wait_completion(jobname=jobname, max_seconds=max_runtime_minutes * 60)
    print(slurm.job_creation_metadata(jobname))
    print(slurm.status(jobname))

    print("--logs:")
    slurm.print_log(jobname=jobname)
