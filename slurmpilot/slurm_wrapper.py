import json
import logging
import os
import re
import shutil
import time
import traceback
from _socket import gaierror
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
import paramiko
from paramiko.ssh_exception import AuthenticationException

from slurmpilot.callback import SlurmSchedulerCallback
from slurmpilot.config import Config, load_config
from slurmpilot.job_creation_info import JobCreationInfo
from slurmpilot.job_metadata import JobMetadata
from slurmpilot.jobpath import JobPathLogic
from slurmpilot.remote_command import (
    RemoteCommandExecutionFabrik,
    RemoteExecution,
)
from slurmpilot.slurm_job_status import SlurmJobStatus

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)


class SlurmWrapper:
    def __init__(
        self,
        config: Config | None = None,
        clusters: List[str] | None = None,
        check_connection: bool = True,
        display_loaded_configuration: bool = False,
    ):
        if config is not None:
            self.config = config
        else:
            self.config = load_config()
        if clusters is None:
            clusters = list(self.config.cluster_configs.keys())
        for cluster in clusters:
            assert cluster in self.config.cluster_configs, (
                f"config not found for cluster {cluster}, "
                f"available clusters: {self.config.cluster_configs.keys()}"
            )
        self.clusters = clusters
        self.job_scheduling_callback = SlurmSchedulerCallback()

        if display_loaded_configuration:
            self.job_scheduling_callback.on_config_loaded(self.config)
        self.connections = {}

        # dictionary from cluster name to home dir
        self.home_dir = {}
        for cluster, config in self.config.cluster_configs.items():
            if cluster in clusters:
                self.connections[cluster] = RemoteCommandExecutionFabrik(
                    master=config.host,
                    user=config.user,
                    prompt_for_login_password=config.prompt_for_login_password,
                    prompt_for_login_passphrase=config.prompt_for_login_passphrase,
                )
                if check_connection:
                    try:
                        logger.debug(f"Try sending command to {cluster}.")
                        self.job_scheduling_callback.on_establishing_connection(
                            cluster=cluster
                        )
                        home_res = self.connections[cluster].run("echo $HOME")
                        self.home_dir[cluster] = Path(home_res.stdout.strip("\n"))
                    except (gaierror, AuthenticationException) as e:
                        traceback.print_exc()
                        raise ValueError(
                            f"Cannot connect to cluster {cluster}. Verify your ssh access. Error: {str(e)}"
                        )

    def list_clusters(self, cluster: str | None = None) -> List[str]:
        # return a list consisting of the provided cluster if not None or all the clusters if None
        return [cluster] if cluster else self.clusters

    def schedule_job(
        self, job_info: JobCreationInfo, dryrun: bool = False
    ) -> int | None:
        """
        remote location {slurmpilot_remote}/{jobname} stores:
        * stderr/
        * stdout/
        * slurm_command.sh
        * possible artifacts written by script
        * source dir provided in job_info
        :param dryrun: whether to run a dry run mode which only sends the source remotely but does
        not schedule the job on slurm
        :return: slurm job id if successful and not running in `dry_run` mode
        """
        job_info.check_path()
        cluster_connection = self.connections[job_info.cluster]
        home_dir = self.home_dir[job_info.cluster]
        self.job_scheduling_callback.on_job_scheduled_start(
            cluster=job_info.cluster, jobname=job_info.jobname
        )

        # generate slurm launcher script in slurmpilot dir
        local_job_paths = self._generate_local_folder(job_info)

        # tar and send slurmpilot dir
        remote_job_paths = self.remote_path(
            job_info, root_path=str(home_dir / "slurmpilot")
        )
        self.job_scheduling_callback.on_sending_artifact(
            localpath=str(local_job_paths.resolve_path()),
            remotepath=str(remote_job_paths.resolve_path()),
            cluster=job_info.cluster,
            # f"Preparing local folder at {local_job_paths.resolve_path()}"
        )

        cluster_connection.upload_folder(
            local_job_paths.job_path(), remote_job_paths.job_path().parent
        )

        # call sbatch remotely
        if not dryrun:
            jobid = self._call_sbatch_remotely(
                cluster_connection=cluster_connection,
                local_job_paths=local_job_paths,
                remote_job_path=remote_job_paths,
                job_info=job_info,
                sbatch_env=job_info.env if job_info.env else {},
                sbatch_arg=job_info.sbatch_arguments,
            )
            self.job_scheduling_callback.on_job_submitted_to_slurm(
                jobname=job_info.jobname, jobid=jobid
            )
            return jobid
        else:
            return None

    def stop_job(self, jobname: str):
        metadata = self.job_creation_metadata(jobname)
        jobid = self.jobid_from_jobname(jobname)
        self.connections[metadata.cluster].run(f"scancel {jobid}")

    def wait_completion(
        self,
        jobname: str,
        max_seconds: int = 60,
    ) -> str:
        """
        :param max_seconds: waits for the given number of seconds if defined else waits for status COMPLETED or FAILED
        :return: final status polled
        """
        self.job_scheduling_callback.on_suggest_command_before_wait_completion(
            jobname=jobname
        )
        from rich.live import Live
        from rich.text import Text
        from rich.spinner import Spinner

        starttime = time.time()
        spinner_name = "dots"
        current_status = self.status([jobname])[0]
        wait_interval = 1
        i = 0
        while current_status is None and wait_interval * i < max_seconds:
            time.sleep(wait_interval)
            current_status = self.status([jobname])[0]
            i += 1

        text = f"Waiting job to finish, current status {current_status}"
        with Live(
            Spinner(spinner_name, text=Text(text)),
        ) as live:
            i = 0
            while (
                current_status in [SlurmJobStatus.pending, SlurmJobStatus.running]
                and wait_interval * i < max_seconds
            ):
                current_status = self.status([jobname])[0]
                text = (
                    f"Waiting job to finish, current status {current_status} (updated every {wait_interval}s, "
                    f"waited for {int(time.time() - starttime)}s)"
                )
                live.renderable.update(text=Text(text))
                time.sleep(
                    wait_interval
                )  # todo exponential backoff to avoid QOS issues
                i += 1
        return current_status

    def _call_sbatch_remotely(
        self,
        job_info: JobCreationInfo,
        cluster_connection: RemoteExecution,
        local_job_paths: JobPathLogic,
        remote_job_path: JobPathLogic,
        sbatch_env: dict,
        sbatch_arg: str | None,
    ) -> int:
        if not sbatch_env:
            sbatch_env = {}
        # TODO design and document SP env that are passed
        sbatch_env["SP_JOBNAME"] = job_info.jobname
        # call sbatch remotely and returns slurm job id if successful
        if sbatch_env:
            # pass environment variable to sbatch in the following form:
            # sbatch --export=REPS=500,X='test' slurm_script.sh
            export_env = "--export=ALL,"
            export_env += ",".join(
                f"{var_name}={var_value}" for var_name, var_value in sbatch_env.items()
            )
        try:
            # TODO make those idempotent,
            #  running `sbatch slurm_script.sh` or `sbatch path_to_script/slurm_script.sh`
            #  should work no matter the directory and variables should be saved for easier reproducibility
            if sbatch_arg is None:
                sbatch_arg = ""
            res = cluster_connection.run(
                f"cd {remote_job_path.job_path()}; mkdir -p logs/; sbatch {sbatch_arg} {export_env} slurm_script.sh",
                env={
                    "SLURMPILOT_PATH": remote_job_path.slurmpilot_path(),
                    "SLURMPILOT_JOBPATH": remote_job_path.resolve_path(),
                },
                retries=3,
            )
        except Exception as e:
            raise ValueError(
                "Could not execute sbatch on the remote host, error:" + str(e)
            )
        if res.failed:
            raise ValueError(
                f"Could not submit job, got the following error:\n{res.stderr}"
            )
        elif len(res.stderr) > 0:
            raise ValueError(
                f"Could not submit job, got the following error:\n{res.stderr}"
            )
        else:
            # should be something like 'Submitted batch job 11301013'
            stdout = res.stdout
            slurm_submitted_msg = "Submitted batch job "
            if stdout.startswith(slurm_submitted_msg):
                matches = re.match(slurm_submitted_msg + r"(\d*)", stdout)
                logging.debug(stdout)
                jobid = int(matches.groups()[0])
                # Save the jobid locally so that we can later maps jobname to jobid for slurm query
                # We do not save it remotely as it does not seem necessary but we could if needed
                self._save_jobid(local_job_paths, jobid)
                return jobid
            else:
                raise ValueError(
                    f"Job scheduled without error but could not parse slurm output: {stdout}"
                )

    def remote_path(self, job_info: JobCreationInfo, root_path: str | None = None):
        return JobPathLogic(
            jobname=job_info.jobname,
            entrypoint=job_info.entrypoint,
            src_dir_name=Path(job_info.src_dir).name if job_info.src_dir else None,
            root_path=(
                root_path
                if root_path
                else self.config.remote_slurmpilot_path(job_info.cluster)
            ),
        )

    def _generate_local_folder(self, job_info: JobCreationInfo):
        local_job_paths = JobPathLogic(
            jobname=job_info.jobname,
            entrypoint=job_info.entrypoint,
            src_dir_name=Path(job_info.src_dir).resolve().name,
            root_path=str(self.config.local_slurmpilot_path()),
        )
        assert (
            not local_job_paths.job_path().exists()
        ), f"jobname {job_info.jobname} has already been used, jobnames must be unique please use another one"
        # copy source, generate main slurm script and metadata
        # TODO, option to keep only python files
        shutil.copytree(src=job_info.src_dir, dst=local_job_paths.src_path())
        if job_info.python_libraries:
            for python_library in job_info.python_libraries:
                assert Path(
                    python_library
                ).exists(), (
                    f"Python library specified {python_library} does not exists."
                )
                shutil.copytree(
                    src=python_library,
                    dst=local_job_paths.resolve_path(Path(python_library).name),
                )
        self._generate_main_slurm_script(local_job_paths, job_info)
        self._generate_metadata(local_job_paths, job_info)
        return local_job_paths

    def _generate_main_slurm_script(
        self, local_job_paths: JobPathLogic, job_info: JobCreationInfo
    ):
        with open(local_job_paths.slurm_entrypoint_path(), "w") as f:
            f.write("#!/bin/bash\n")
            f.write(job_info.sbatch_preamble())
            # Add path containing the library to the PYTHONPATH so that they can be imported without requiring
            # the user to add `PYTHONPATH=.` before running scripts, e.g. instead of having to do
            # `PYTHONPATH=. python main.py`, users can simply do `python main.py`
            if job_info.bash_setup_command:
                f.write(job_info.bash_setup_command + "\n")

            # add library to PYTHONPATH
            libraries = [str(local_job_paths.resolve_path())]
            if job_info.python_paths is not None:
                libraries += job_info.python_paths
            if job_info.python_libraries:
                libraries += job_info.python_libraries
            f.write(f'export PYTHONPATH=$PYTHONPATH:{":".join(libraries)}\n')
            if job_info.python_binary is None:
                f.write(f"bash {local_job_paths.entrypoint_path_from_cwd()}\n")
            else:
                python_args = (
                    job_info.python_args if job_info.python_args is not None else ""
                )
                if isinstance(python_args, dict):
                    python_args = " ".join(
                        f"--{key}={value}" for key, value in python_args.items()
                    )
                f.write(
                    f"{job_info.python_binary} {local_job_paths.entrypoint_path_from_cwd()} {python_args}\n"
                )

    def _save_jobid(self, local_job_paths: JobPathLogic, jobid: int):
        metadata = {
            "jobid": jobid,
        }
        with open(local_job_paths.jobid_path(), "w") as f:
            f.write(json.dumps(metadata))

    def log(self, jobname: str, cluster: str | None = None):
        if cluster is None:
            cluster = self.cluster(jobname)
        local_path = JobPathLogic(jobname=jobname)
        self._download_logs(local_path, cluster=cluster, jobname=jobname)
        if local_path.stderr_path().exists():
            with open(local_path.stderr_path()) as f:
                stderr = "".join(f.readlines())
        else:
            stderr = None
        if local_path.stdout_path().exists():
            with open(local_path.stdout_path()) as f:
                stdout = "".join(f.readlines())
        else:
            stdout = None
        return stdout, stderr

    def print_log(self, jobname: str | None = None):
        """
        :param jobname: if not specified uses the last job
        :return: print log of specified job
        """
        if jobname is None:
            jobname = self.latest_job(self.config).jobname
            print(f"No jobname was passed, showing log of latest job {jobname}")
        cluster = self.cluster(jobname)
        stderr, stdout = self.log(jobname=jobname, cluster=cluster)
        if stderr:
            print(f"stderr:\n{stderr}")
        if stdout:
            print(f"stdout:\n{stdout}")

    @staticmethod
    def latest_job(
        config: Config | None = None, pattern: str | None = None
    ) -> JobMetadata:
        """
        :param config:
        :param pattern: if passed, then consider only jobs whose name contains `pattern`
        :return:
        """
        if config is None:
            config = load_config()
        files = list(
            (config.local_slurmpilot_path() / "jobs")
            .expanduser()
            .rglob("metadata.json")
        )
        if pattern is not None:
            # Search for job that matches the patter given
            files = [x for x in files if pattern in str(x)]
        if len(files) > 0:
            latest_file = max(files, key=lambda item: item.stat().st_ctime)
            with open(latest_file, "r") as f:
                return JobMetadata.from_json(f.read())
        raise ValueError(f"No job was found at {config.local_slurmpilot_path()}")

    def cluster(self, jobname: str):
        """
        :param jobname:
        :return: retrieves the cluster where `jobname` was launched by querying local files
        """
        job_metadata = self.job_creation_metadata(jobname=jobname)
        return job_metadata.cluster

    def list_jobs(self, n_jobs: int) -> List[JobMetadata]:
        files = sorted(
            (self.config.local_slurmpilot_path() / "jobs")
            .expanduser()
            .rglob("metadata.json"),
            key=lambda item: item.stat().st_ctime,
            reverse=True,
        )
        jobs = []
        files = list(files)
        files = files[:n_jobs]
        for file in files:
            with open(file, "r") as f:
                try:
                    jobs.append(JobMetadata.from_json(f.read()))
                except json.decoder.JSONDecodeError:
                    pass
        return jobs

    def status(self, jobnames: list[str]) -> list[str | None]:
        if not isinstance(jobnames, list):
            assert isinstance(jobnames, str)
            jobnames = [jobnames]
        jobnames_statuses = {}
        jobid_mapping = {}
        clusters = defaultdict(list)
        # first, we build a dictionary mapping clusters to job informations
        for jobname in jobnames:
            # TODO support having this one missing (
            jobid = self.jobid_from_jobname(jobname)
            jobid_mapping[jobid] = jobname
            job_metadata = self.job_creation_metadata(jobname)
            cluster = job_metadata.cluster
            clusters[cluster].append((jobid, job_metadata))

        # second we call sacct on each clusters with the corresponding jobs
        for cluster in clusters.keys():
            try:
                job_clusters = clusters[cluster]
                # filter jobs with missing jobid
                query_jobids = [
                    str(jobid)
                    for (jobid, job_metadata) in job_clusters
                    if jobid is not None
                ]
                sacct_format = "JobID,Elapsed,start,State"

                # call sacct...
                res = self.connections[cluster].run(
                    f'sacct --format="{sacct_format}" -X -p --jobs={",".join(query_jobids)}'
                )

                # ...and parse output
                lines = res.stdout.split("\n")
                keys = lines[0].split("|")[:-1]
                for line in lines[1:]:
                    if line:
                        try:
                            status_dict = dict(zip(keys, line.split("|")[:-1]))
                            # TODO elapsed time is probably useful too
                            jobnames_statuses[
                                jobid_mapping[int(status_dict["JobID"])]
                            ] = status_dict.get("State", "missing")
                        except Exception as e:
                            print(line, str(e))
                            continue
            # TODO abstract it
            except paramiko.ssh_exception.AuthenticationException as e:
                logging.warning(
                    f"Could not connect to cluster {cluster}, make sure your ssh connection works."
                )
                continue
        return [jobnames_statuses.get(jobname) for jobname in jobnames]

    def print_jobs(
        self, n_jobs: int = 10, max_colwidth: int = 50, status_verbose: bool = True
    ):
        rows = []
        jobs = self.list_jobs(n_jobs)
        statuses = self.status(jobnames=[job.jobname for job in jobs])
        for job, status in zip(jobs, statuses):
            # TODO status when missing jobid.json => error at launching
            if status is None:
                status_symbol = "Unknown slurm status 🏝"
            else:
                status_mapping = {
                    SlurmJobStatus.out_of_memory: "OOM 🤯",
                    SlurmJobStatus.failed: "Slurm job failed ❌",
                    SlurmJobStatus.pending: "Pending ⏳",
                    SlurmJobStatus.running: "️Running 🏃",
                    SlurmJobStatus.completed: "Completed ✅",
                    SlurmJobStatus.cancelled: "Canceled ⚠️",
                }
                if "CANCELLED" in status:
                    status_symbol = "Cancelled ⚠️"
                else:
                    status_symbol = status_mapping.get(
                        status, f"Unknown state: {status}"
                    )

            rows.append(
                {
                    "job": Path(job.jobname).name,
                    "date": pd.to_datetime(job.date).strftime("%d/%m/%y-%H:%M"),
                    "cluster": job.job_creation_info.cluster,
                    "status": (
                        f"{status_symbol} "
                        if status_verbose
                        else f"{status_symbol[-1:]} "
                    ),
                    "full jobname": job.jobname,
                }
            )
        df = pd.DataFrame(rows)
        print(
            df.to_string(
                index=False,
                max_colwidth=max_colwidth,
            )
        )

    def download_job(self, jobname: str | None = None):
        if jobname is None:
            jobname = self.latest_job(self.config).jobname
        cluster = self.cluster(jobname)
        local_path = JobPathLogic(jobname=jobname)
        remote_path = JobPathLogic.from_jobname(
            jobname=jobname,
            root_path=self.config.remote_slurmpilot_path(cluster),
        )
        self.connections[cluster].download_folder(
            remote_path.resolve_path(),
            local_path.resolve_path(),
        )

    def _download_logs(self, local_path, cluster: str, jobname: str):
        # 1) download log from remote file
        # 2) show in console
        # we could also consider streaming
        remote_path = JobPathLogic.from_jobname(
            jobname=jobname,
            root_path=self.config.remote_slurmpilot_path(cluster),
        )
        try:
            self.connections[cluster].download_file(
                remote_path.stderr_path(), local_path.stderr_path()
            )
            self.connections[cluster].download_file(
                remote_path.stdout_path(), local_path.stdout_path()
            )
        except FileNotFoundError:
            return ""

    def jobid_from_jobname(self, jobname: str) -> int | None:
        # several options are possible:
        # 1) store info in jobname folder
        # 2) runs sacct -X --format=jobname%30,jobid remotely and parse output
        # 3) store mapping locally in DB
        # We choose here the first one because it avoids a remote/call parsing or to setup a DB

        # Option 2)
        # res = self.connection.run(f"sacct -X --format=jobname%30,jobid  | grep {jobname} | tail -n 1")
        # # "example-j+ 11301527" -> 11301527
        # return int(res.stdout.split(" ")[-1])
        local_path = JobPathLogic(jobname=jobname)
        if local_path.jobid_path().exists():
            with open(local_path.jobid_path(), "r") as f:
                return json.load(f)["jobid"]
        else:
            return None

    @staticmethod
    def job_creation_metadata(jobname: str) -> JobMetadata:
        local_path = JobPathLogic(jobname=jobname)
        with open(local_path.metadata_path(), "r") as f:
            return JobMetadata.from_json(f.read())

    def _generate_metadata(self, local_path: JobPathLogic, job_info: JobCreationInfo):
        metadata = JobMetadata(
            user=os.getenv("USER"),
            date=str(datetime.now()),
            job_creation_info=job_info,
            cluster=job_info.cluster,
        )
        with open(local_path.metadata_path(), "w") as f:
            f.write(metadata.to_json())

    def format_string_jobname(self, message: str, jobname: str) -> str:
        return self.job_scheduling_callback.format_string_jobname(message, jobname)
