import argparse

from slurmpilot.config import load_config
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

    args = parser.parse_args()
    is_command_requiring_jobname = any(
        [args.log, args.download, args.status, args.stop]
    )
    if (
        not is_command_requiring_jobname
        and not args.test_ssh_connections
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
        elif args.list_jobs:
            n_jobs = args.list_jobs
            SlurmWrapper(check_connection=False, config=load_config()).print_jobs(
                n_jobs=n_jobs
            )


if __name__ == "__main__":
    main()
