import argparse
import yaml
import logging

from slurmpilot.config import default_cluster_and_partition
from slurmpilot.slurm_wrapper import SlurmWrapper, JobCreationInfo
from slurmpilot.util import unify

def load_config(config_path):
    """
    Load configuration from a YAML file.
    :param config_path: Path to the YAML configuration file.
    :return: Parsed configuration as a dictionary.
    """
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def main():
    parser = argparse.ArgumentParser(description="Load configurations from a YAML file.")
    parser.add_argument("config", type=str, help="Path to the YAML configuration file")
    args = parser.parse_args()

    # Load the configuration
    config = load_config(args.config)

    # Logging configuration
    logging.basicConfig(level=logging.INFO)

    cluster = config.get("cluster", None)
    if cluster is None:
        cluster, partition = default_cluster_and_partition()
        logging.warn(f"Cluster not specified. Using the default cluster ({cluster}) and partition ({partition}).")
    else:
        partition = config["job"].get("partition", None)
        assert partition is not None, f"The cluster is specified ({cluster}), but the partition isn't. Either specify both or neither."

    # set the job name
    method = config.get("method", "coolname")
    jobname = unify(config["job"].get("jobname", "default-job-name"), method)
    max_runtime_minutes = config.get("max_runtime_minutes", 24 * 60)

    slurm = SlurmWrapper(clusters=[cluster])

    script_config = config.get("script", {})
    job_config = config.get("job")
    template_data = config.get("template", {})

    for key in ["partition", "jobname"]:
        job_config.pop(key, None)

    # Job Information
    jobinfo = JobCreationInfo(
        cluster=cluster,
        partition=partition,
        jobname=jobname,
        **job_config,
        **script_config,
        template_data=template_data
    )

    jobid = slurm.schedule_job(jobinfo)
    slurm.wait_completion(jobname=jobname, max_seconds=max_runtime_minutes * 60)
    print(slurm.job_creation_metadata(jobname))
    print(slurm.status(jobname))
    print("--logs:")
    slurm.print_log(jobname=jobname)

if __name__ == "__main__":
    main()
