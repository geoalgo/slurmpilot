import argparse

from slurmpilot.callback import format_jobname
from slurmpilot.config import load_config
from slurmpilot.job_metadata import list_metadatas, JobMetadata
from slurmpilot import SlurmPilot


def jobname_from_cli_args_or_take_latest(config, args):
    if args.job:
        try:
            return JobMetadata.from_jobname(args.job)
        except FileNotFoundError as e:
            print(
                f"Jobname passed not found, searching for a jobname which contains {format_jobname(args.job)}."
            )
            metadatas = list_metadatas(
                root=config.local_slurmpilot_path() / "jobs",
            )
            matches = [m for m in metadatas if args.job in m.jobname]
            if len(matches) > 0:
                print(f"Found {len(matches)} matches, using the first one.")
                return matches[0]

            print(
                f"Could not find any jobnames which contain {format_jobname(args.job)}"
            )
            return None
    else:
        job_metadata = SlurmPilot.latest_job()
        print(
            f"No jobs specified, retrieved the latest one: {format_jobname(job_metadata.jobname)}"
        )
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
        "--cluster",
        help="Cluster to consider, consider all clusters by default.",
        type=str,
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
    config = load_config()

    if is_command_requiring_jobname or args.job:
        job = jobname_from_cli_args_or_take_latest(config, args)

        if job is None:
            return

        slurm = SlurmPilot(config=config, clusters=[job.cluster])
        match args:
            case args if args.log:
                print(
                    slurm.format_string_jobname("Displaying log for job", job.jobname)
                )
                slurm.print_log(jobname=job.jobname)
            case args if args.download:
                print(slurm.format_string_jobname("Downloading job", job.jobname))
                slurm.download_job(jobname=job.jobname)
            case args if args.status:
                print(
                    slurm.format_string_jobname(
                        "Displaying status for job", job.jobname
                    )
                )
                print(slurm.status(jobnames=[job.jobname])[0])
            case args if args.stop:
                print(slurm.format_string_jobname("Stopping job", job.jobname))
                slurm.stop_job(jobname=job.jobname)
            case _:
                print(
                    slurm.format_string_jobname(
                        "Displaying status for job", job.jobname
                    )
                )
                print(slurm.status(jobnames=[job.jobname])[0])
    else:
        if args.test_ssh_connections:
            slurm = SlurmPilot(config=config)
            print(
                f"Could load successfully ssh connections from {list(slurm.connections.keys())} clusters."
            )
            # TODO print a table with ✅❌ symbols
        elif args.list_jobs:
            n_jobs = args.list_jobs
            clusters = [args.cluster] if args.cluster is not None else None
            SlurmPilot(clusters=clusters, config=config).print_jobs(n_jobs=n_jobs)


if __name__ == "__main__":
    main()
