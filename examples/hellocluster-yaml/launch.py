import os
import argparse
from omegaconf import OmegaConf
import logging

from slurmpilot import (
    default_cluster_and_partition,
    SlurmWrapper,
    JobCreationInfo,
    unify,
)


def load_config(config_path):
    """
    Load configuration from a YAML file using OmegaConf.
    :param config_path: Path to the YAML configuration file.
    :return: Parsed configuration as an OmegaConf dictionary.
    """
    return OmegaConf.load(config_path)


def write_filled_template_to_file(
    template_path: str, output_path: str, template_data: dict
) -> None:
    with open(template_path, "r") as f:
        content = f.read()

    updated_template = content
    for key, replace in template_data.items():
        updated_template = updated_template.replace(key, str(replace))

    with open(output_path, "w") as outfile:
        outfile.write(updated_template)


def main():
    parser = argparse.ArgumentParser(
        description="Load configurations from a YAML file."
    )
    parser.add_argument("config", type=str, help="Path to the YAML configuration file")
    args = parser.parse_args()

    # Load the configuration
    config = load_config(args.config)

    # Logging configuration
    logging.basicConfig(level=logging.INFO)

    cluster = config.get("cluster", None)
    if cluster is None:
        cluster, partition = default_cluster_and_partition()
        logging.warn(
            f"Cluster not specified. Using the default cluster ({cluster}) and partition ({partition})."
        )
    else:
        partition = config.job.get("partition", None)
        assert (
            partition is not None
        ), f"The cluster is specified ({cluster}), but the partition isn't. Either specify both or neither."

    # set the job name
    method = config.get("method", "coolname")
    jobname = unify(config.job.get("jobname", "default-job-name"), method)
    max_runtime_minutes = config.get("max_runtime_minutes", 24 * 60)

    slurm = SlurmWrapper(clusters=[cluster])

    script_config = config.get("script", {})
    job_config = config.job
    template_config = config.template

    template_path = os.path.join(
        script_config.src_dir, template_config.entrypoint_template
    )
    output_path = os.path.join(script_config.src_dir, script_config.entrypoint)

    write_filled_template_to_file(
        template_path=template_path,
        output_path=output_path,
        template_data=OmegaConf.to_container(template_config.entries, resolve=True),
    )

    for key in ["partition", "jobname"]:
        job_config.pop(key, None)

    print(dict(job_config))
    print(dict(script_config))
    print(cluster, partition, jobname)

    # Job Information
    jobinfo = JobCreationInfo(
        cluster=cluster,
        partition=partition,
        jobname=jobname,
        **OmegaConf.to_container(job_config, resolve=True),
        **OmegaConf.to_container(script_config, resolve=True),
    )

    jobid = slurm.schedule_job(jobinfo)
    slurm.wait_completion(jobname=jobname, max_seconds=max_runtime_minutes * 60)
    print(slurm.job_creation_metadata(jobname))
    print(slurm.status(jobname))
    print("--logs:")
    slurm.print_log(jobname=jobname)


if __name__ == "__main__":
    main()
