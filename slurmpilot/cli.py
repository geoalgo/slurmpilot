import argparse
import os

import yaml

from slurmpilot.config import load_config, ClusterConfig, config_path
from slurmpilot.slurm_wrapper import SlurmWrapper


def jobname_from_cli_args_or_take_latest(args):
    if args.job:
        try:
            return SlurmWrapper.job_creation_metadata(args.job)
        except FileNotFoundError as e:
            print(
                f"Jobname passed not found, searching for a jobname which contains {args.job}."
            )
            job_metadata = SlurmWrapper.latest_job(pattern=args.job)
            return job_metadata

    else:
        job_metadata = SlurmWrapper.latest_job()
        print(f"No jobs specified, retrieved the latest one: {job_metadata.jobname}")
        return job_metadata


def main():
    parser = argparse.ArgumentParser(
        prog="Slurmpilot CLI",
        # description='What the program does',
        # epilog='Text at the bottom of help'
    )
    # TODO list all local jobs and all remote jobs
    parser.add_argument(
        "job", help="Jobname to be queried, leave empty to use the last one", nargs="?"
    )
    parser.add_argument(
        "--log",
        help="Show log for the specified job",
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--stop", help="Stop the specified job", action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--download",
        help="Download data for the specified job",
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--status",
        help="Show status for the specified job",
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--list-jobs", help="List n latest jobs", required=False, type=int, default=5
    )

    parser.add_argument(
        "--test-ssh-connections",
        help="Test ssh connections",
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--add-cluster", help="Add a new cluster", action=argparse.BooleanOptionalAction
    )

    args = parser.parse_args()
    is_command_requiring_jobname = any(
        [args.log, args.download, args.status, args.stop]
    )
    if (
        not is_command_requiring_jobname
        and not args.test_ssh_connections
        and not args.add_cluster
        and not args.list_jobs
    ):
        raise ValueError(
            "No action specifed, run slurmpilot YOURJOB --log to display the log, or use --status for other actions."
        )

    if is_command_requiring_jobname:
        job = jobname_from_cli_args_or_take_latest(args)
        slurm = SlurmWrapper(clusters=[job.cluster])
        # TODO use match
        if args.log:
            print(slurm.format_string_jobname("Displaying log for job", job.jobname))
            slurm.print_log(jobname=job.jobname)
        if args.download:
            print(slurm.format_string_jobname("Downloading job", job.jobname))
            slurm.download_job(jobname=job.jobname)
        if args.status:
            print(slurm.format_string_jobname("Displaying status for job", job.jobname))
            print(slurm.status(jobnames=[job.jobname])[0])
        if args.stop:
            print(slurm.format_string_jobname("Stopping job", job.jobname))
            slurm.stop_job(jobname=job.jobname)
    else:
        if args.test_ssh_connections:
            slurm = SlurmWrapper(config=load_config())
            print(
                f"Could load successfully ssh connections from {list(slurm.connections.keys())} clusters."
            )
            # TODO print a table with ✅❌ symbols
        elif args.add_cluster:
            cluster = input("Name of the cluster:")
            hostname = input("Hostname:")
            username = input(f'Username (optional, default to {os.getenv("USER")}):')
            account = input("Default account (optional):")
            default_partition = input("Default partition (optional):")
            remote_path = input(f"Remote path (default to slurmpilot/):")

            prompt_for_login_password = (
                input(
                    f"Prompt for a login password for ssh if you set a key password? (y/n) optional and deactivated by default:"
                )
                .lower()
                .strip()
                == "y"
            )
            prompt_for_login_passphrase = (
                input(
                    f"Prompt for a login passphrase for ssh if you set a key password? (y/n) optional and deactivated by default:"
                )
                .lower()
                .strip()
                == "y"
            )

            config_cluster_path = config_path / "clusters" / f"{cluster}.yaml"
            print(f"Saving cluster configuration {cluster} to {config_cluster_path}")
            config = ClusterConfig(
                host=hostname,
                remote_path=remote_path,
                account=account,
                user=username,
                default_partition=default_partition,
                prompt_for_login_passphrase=prompt_for_login_passphrase,
                prompt_for_login_password=prompt_for_login_password,
            )
            print(f"Going to save {config} to {config_cluster_path}")

            with open(config_path / "clusters" / f"{cluster}.yaml", "w") as f:
                dict_without_none = {k: v for k, v in config.__dict__.items() if v}
                yaml.dump(dict_without_none, f)

            try:
                print(f"Testing configuration {cluster} with ssh.")
                SlurmWrapper(config=load_config(), clusters=[cluster])
                print(f"✅ Could connect to ssh, cluster successfully installed.")
            except ValueError as e:
                print(
                    f"⚠️ Could not connect to ssh, you can remove the file {config_cluster_path} or rerun this script"
                )
                # config_cluster_path.unlink()
        elif args.list_jobs:
            n_jobs = args.list_jobs
            SlurmWrapper(check_connection=False, config=load_config()).print_jobs(
                n_jobs=n_jobs
            )


if __name__ == "__main__":
    main()
