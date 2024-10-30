"""
Example that shows how to launch a script that requires a library from another folder that is being copied over
 and added to Python path by Slurmpilot.
"""

import logging
from pathlib import Path
from slurmpilot import SlurmWrapper, JobCreationInfo, default_cluster_and_partition
from slurmpilot.util import unify

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.basicConfig(level=logging.INFO)
    cluster, partition = default_cluster_and_partition()
    jobname = unify(
        "examples/custom-library/job", method="coolname"
    )  # make the jobname unique by appending a coolname
    slurm = SlurmWrapper(clusters=[cluster])
    max_runtime_minutes = 60
    root_dir = Path(__file__).parent
    jobinfo = JobCreationInfo(
        cluster=cluster,
        partition=partition,
        jobname=jobname,
        entrypoint="main_using_custom_library.py",
        python_args="--learning-rate 0.01",
        # bash_setup_command="source mmlu/setup_environment.sh",
        src_dir=str(root_dir / "script"),
        python_libraries=[str(root_dir / "custom_library")],
        python_binary="/home/salinasd/miniconda3/envs/mmlu/bin/python",
        n_cpus=1,
        max_runtime_minutes=max_runtime_minutes,
        # Shows how to pass an environment variable to the running script
        env={"API_TOKEN": "DUMMY"},
    )
    jobid = slurm.schedule_job(jobinfo)

    slurm.wait_completion(jobname=jobname, max_seconds=max_runtime_minutes * 60)
    print(slurm.job_creation_metadata(jobname))
    print(slurm.status([jobname]))

    print("--logs:")
    slurm.print_log(jobname=jobname)
