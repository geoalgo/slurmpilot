"""
* tool to display logs/status from terminal
  * (sp added by concatenating to path, suggestion made in setup.py)
  * sp --help
  * sp --log  # show last log
  * sp --log job-name
  * sp --status 10  # show status of last 10 jobs (list pulled from local files)
  * sp --status job-name
  * sp --sync job-name  # sync artifacts
"""

import argparse
from pathlib import Path

from slurmpilot_freiburg import load_config
from slurm_wrapper import SlurmWrapper

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='Slurmpilot CLI',
        # description='What the program does',
        # epilog='Text at the bottom of help'
    )
    parser.add_argument('job', help="Jobname to be queried, leave empty to use the last one", nargs='?')
    parser.add_argument('--log', help="Show log for the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--download', help="Download data for the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--status', help="Show status for the specified job", action=argparse.BooleanOptionalAction)
    parser.add_argument('--sync', help="Retrieve job folder locally for the specified job", action=argparse.BooleanOptionalAction)

    args = parser.parse_args()

    # TODO allow to change config
    config_path = Path(__file__).parent.parent.parent / "config"

    # cluster = "meta"
    # partition = "ml_gpu-rtx2080"
    # account = None

    slurm = SlurmWrapper(config=load_config())

    if args.job:
        job = args.job
    else:
        # TODO retrieve last job if possible
        job = slurm.latest_job()
        print(f"No jobs specified, retrieved the latest one: {job}")
    if not(any([args.log, args.status, args.sync])):
        print("No action specifed, run sp YOURJOB --log to display the log, or use --status, --sync for other actions.")
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
