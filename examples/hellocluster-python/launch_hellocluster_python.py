import logging

from slurmpilot import SlurmWrapper, JobCreationInfo, default_cluster_and_partition
from slurmpilot.util import unify

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cluster, partition = default_cluster_and_partition()
    # make the jobname unique by appending a coolname
    jobname = unify("examples/hello-cluster-python/job", method="coolname")
    slurm = SlurmWrapper(clusters=[cluster])
    jobinfo = JobCreationInfo(
        cluster=cluster,
        partition=partition,
        jobname=jobname,
        entrypoint="main_hello_cluster.py",
        python_args="--argument1 dummy",
        python_binary="~/miniconda3/bin/python",
        n_cpus=1,
        max_runtime_minutes=60,
        # Shows how to pass an environment variable to the running script
        env={"API_TOKEN": "DUMMY"},
    )
    jobid = slurm.schedule_job(jobinfo)

    slurm.wait_completion(jobname=jobname, max_seconds=600)
    print(slurm.job_creation_metadata(jobname))
    print(slurm.status([jobname]))

    print("--logs:")
    slurm.print_log(jobname=jobname)
