"""
* tool to display logs/status from terminal:
  * slurmpilot --help
  * slurmpilot --test-ssh-connections
  * slurmpilot --log  # show last log
  * slurmpilot --log job-name
  * slurmpilot --status 10  # show status of last 10 jobs (list pulled from local files)
  * slurmpilot --status job-name
  * slurmpilot --sync job-name  # sync artifacts
  * TODO: slurmpilot --delete-cluster-files --cluster meta
"""

import argparse
import os

import yaml

from slurmpilot.config import load_config, ClusterConfig, config_path
from slurmpilot.slurm_wrapper import SlurmWrapper

def jobname_from_cli_args_or_take_latest(args):
    if args.job:
        return SlurmWrapper.job_creation_metadata(args.job)
    else:
        job_metadata = SlurmWrapper.latest_job()
        print(f"No jobs specified, retrieved the latest one: {job_metadata.jobname}")
    return job_metadata

def main():
    parser = argparse.ArgumentParser(
        prog='Slurmpilot CLI',
        # description='What the program does',
        # epilog='Text at the bottom of help'
    )
    # TODO list all local jobs and all remote jobs
    parser.add_argument('job', help="Jobname to be queried, leave empty to use the last one", nargs='?')
    parser.add_argument('--log', help="Show log for the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--stop', help="Stop the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--download', help="Download data for the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--status', help="Show status for the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--sync', help="Retrieve job folder locally for the specified job",
                        action=argparse.BooleanOptionalAction)
    parser.add_argument('--test-ssh-connections', help="Test ssh connections", action=argparse.BooleanOptionalAction)
    parser.add_argument('--add-cluster', help="Add a new cluster", action=argparse.BooleanOptionalAction)

    args = parser.parse_args()

    is_command_requiring_jobname = any([args.log, args.download, args.status, args.sync, args.stop])
    if not is_command_requiring_jobname and not args.test_ssh_connections and not args.add_cluster:
        raise ValueError("No action specifed, run slurmpilot YOURJOB --log to display the log, or use --status, --sync for other actions.")

    if is_command_requiring_jobname:
        job = jobname_from_cli_args_or_take_latest(args)
        slurm = SlurmWrapper(clusters=[job.cluster])
        # TODO use match
        if args.log:
            print(f"Displaying log for job {job}.")
            slurm.print_log(jobname=job.jobname)
        if args.download:
            print(f"Downloading job {job}.")
            slurm.download_job(jobname=job.jobname)
        if args.status:
            print(f"Displaying status for job {job}.")
            print(slurm.status(jobname=job.jobname))
        if args.sync:
            print(f"Pulling folder locally for job {job}.")
            raise NotImplementedError("TODO implement me.")
        if args.stop:
            print(f"Stopping job {job}.")
            slurm.stop_job(jobname=job.jobname)
    else:
        if args.test_ssh_connections:
            slurm = SlurmWrapper(config=load_config())
            print(f"Could load successfully ssh connections from {list(slurm.connections.keys())} clusters.")
        elif args.add_cluster:
            cluster = input("Name of the cluster:")
            hostname = input("Hostname:")
            username = input(f'Username (optional, default to {os.getenv("USER")}):')
            account = input("Default account (optional):")
            default_partition = input("Default partition (optional):")
            remote_path = input(f"Remote path (default to slurmpilot/):")

            config_cluster_path = config_path / "clusters" / f"{cluster}.yaml"
            print(f"Saving cluster configuration {cluster} to {config_cluster_path}")
            config = ClusterConfig(host=hostname, remote_path=remote_path, account=account, user=username, default_partition=default_partition)
            print(config)

            with open(config_path / "clusters" / f"{cluster}.yaml", "w") as f:
                dict_without_none = {k: v for k, v in config.__dict__.items() if v}
                yaml.dump(dict_without_none, f)

            try:
                print(f"Testing configuration {cluster} with ssh.")
                SlurmWrapper(config=load_config(), clusters=[cluster])
                print(f"✅ Could connect to ssh, cluster successfully installed.")
            except ValueError as e:
                print(f"⚠️ Could not connect to ssh, you can remove the file {config_cluster_path} or rerun this script")
                # config_cluster_path.unlink()


if __name__ == '__main__':
    main()
