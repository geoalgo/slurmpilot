import logging

from pathlib import Path

from slurmpilot.config import default_cluster_and_partition, load_config
from slurmpilot.slurm_wrapper import SlurmWrapper, JobCreationInfo
from slurmpilot.util import unify

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    user_path = Path('slurmpilot/config')
    config = load_config(user_path=user_path)
    cluster, partition = default_cluster_and_partition(user_path=user_path)
    jobname = unify("hello-cluster", method="coolname")  # make the jobname unique by appending a coolname
    slurm = SlurmWrapper(config=config, clusters=[cluster])
    max_runtime_minutes = 60
    jobinfo = JobCreationInfo(
        cluster=cluster,
        partition=partition,
        jobname=jobname,
        entrypoint="hellocluster_script.sh",
        src_dir="./",
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
