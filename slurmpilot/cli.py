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
from slurmpilot.slurm_wrapper import SlurmWrapper

def jobname_from_cli_args_or_take_latest(slurm, args):
    if args.job:
        job = args.job
    else:
        job = slurm.latest_job()
        print(f"No jobs specified, retrieved the latest one: {job}")
    return job

def main():
    parser = argparse.ArgumentParser(
        prog='Slurmpilot CLI',
        # description='What the program does',
        # epilog='Text at the bottom of help'
    )
    # TODO list all local jobs and all remote jobs
    parser.add_argument('job', help="Jobname to be queried, leave empty to use the last one", nargs='?')
    parser.add_argument('--log', help="Show log for the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--download', help="Download data for the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--status', help="Show status for the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--sync', help="Retrieve job folder locally for the specified job",
                        action=argparse.BooleanOptionalAction)
    parser.add_argument('--test-ssh-connections', help="Test ssh connections", action=argparse.BooleanOptionalAction)


    args = parser.parse_args()


    is_command_requiring_jobname = any([args.log, args.download, args.status, args.sync])
    if not is_command_requiring_jobname and not args.test_ssh_connections:
        print("No action specifed, run slurmpilot YOURJOB --log to display the log, or use --status, --sync for other actions.")

    if is_command_requiring_jobname:
        slurm = SlurmWrapper()
        job = jobname_from_cli_args_or_take_latest(slurm, args)
        # TODO use match
        if args.log:
            print(f"Displaying log for job {job}.")
            slurm.print_log(jobname=job)
        if args.download:
            print(f"Downloading job {job}.")
            slurm.download_job(jobname=job)
        if args.status:
            print(f"Displaying status for job {job}.")
            print(slurm.status(jobname=job))
        if args.sync:
            print(f"Pulling folder locally for job {job}.")
            raise NotImplementedError("TODO implement me.")
    else:
        if args.test_ssh_connections:
            slurm = SlurmWrapper(config=load_config())
            print(f"Could load succesfully ssh connections from {list(slurm.connections.keys())} clusters.")

if __name__ == '__main__':
    main()
