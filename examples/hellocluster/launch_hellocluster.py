import logging
from slurmpilot import (
    default_cluster_and_partition,
    SlurmPilot,
    JobCreationInfo,
    unify,
)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cluster, partition = default_cluster_and_partition()
    jobname = unify(
        "examples/hello-cluster/job", method="coolname"
    )  # make the jobname unique by appending a coolname
    slurm = SlurmPilot(clusters=[cluster])
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
