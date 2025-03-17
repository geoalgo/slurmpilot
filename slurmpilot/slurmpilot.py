import json
import logging
import os
import re
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import List

from slurmpilot.callback import SlurmSchedulerCallback, format_highlight
from slurmpilot.config import Config, load_config
from slurmpilot.job_creation_info import JobCreationInfo
from slurmpilot.job_metadata import JobMetadata, list_metadatas
from slurmpilot.jobpath import JobPathLogic
from slurmpilot.remote_command import (
    RemoteExecution,
    RemoteCommandExecutionSubprocess,
)
from slurmpilot.slurm_job_status import (
    SlurmJobStatus,
    print_jobs,
    job_infos,
)
from slurmpilot.slurm_main_script import generate_main_slurm_script

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)


class SlurmPilot:
    def __init__(
        self,
        config: Config | None = None,
        clusters: List[str] | None = None,
        check_connection: bool = True,
        display_loaded_configuration: bool = False,
        ssh_engine: str | None = None,
    ):
        """
        :param config: general and cluster configurations
        :param clusters: list of clusters to be used
        :param check_connection: whether to check the connection of clusters
        :param display_loaded_configuration: whether to display the list of loaded configuration
        :param ssh_engine: one of "ssh" or "paramiko". "ssh" requires a unix machine and will use directly ssh
        from the unix machine, "paramiko" will use an intermediate python library.
        """
        if ssh_engine is None:
            #  right now we use RemoteCommandExecutionSubprocess as it is more bullet proof than paramiko which
            #  causes sometimes weird authentication issues (which dont happen with native ssh).
            ssh_engine = "ssh"
        else:
            assert ssh_engine in ["ssh", "paramiko"]
        self.ssh_engine = ssh_engine
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
        for cluster, config in self.config.cluster_configs.items():
            if cluster in clusters:
                if self.ssh_engine == "ssh":
                    self.connections[cluster] = RemoteCommandExecutionSubprocess(
                        master=config.host,
                        user=config.user,
                    )
                else:
                    from slurmpilot.remote_command import (
                        RemoteCommandExecutionFabrik,
                    )

                    self.connections[cluster] = RemoteCommandExecutionFabrik(
                        master=config.host,
                        user=config.user,
                    )
                if check_connection:
                    try:
                        logger.debug(f"Try sending command to {cluster}.")
                        self.job_scheduling_callback.on_establishing_connection(
                            cluster=cluster
                        )
                        self.connections[cluster].run("echo $HOME")
                    # except (gaierror, AuthenticationException) as e:
                    except Exception as e:
                        logger.info(
                            f"Cannot connect to cluster {cluster}. Verify your ssh access. Error: {str(e)}, removing cluster {cluster}."
                        )
                        traceback.print_exc()
                        self.connections.pop(cluster)
                        # raise ValueError(
                        #     f"Cannot connect to cluster {cluster}. Verify your ssh access. Error: {str(e)}"
                        # )

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

        if job_info.remote_dir is None:
            root_path = self.config.remote_slurmpilot_path(job_info.cluster)
        else:
            root_path = job_info.remote_dir

        self.job_scheduling_callback.on_job_scheduled_start(
            cluster=job_info.cluster, jobname=job_info.jobname
        )

        # generate slurm launcher script in slurmpilot dir
        local_job_paths = self._generate_local_folder(job_info)

        # tar and send slurmpilot dir
        remote_job_paths = self.remote_path(job_info, root_path=root_path)
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
        metadata = JobMetadata.from_jobname(jobname)
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
                    f"Waiting job to finish, current status {format_highlight(current_status)} (updated every "
                    f"{wait_interval}s, waited for {int(time.time() - starttime)}s)"
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
                f"Could not submit job, got the following error:\n{res.stderr}\n{res.stdout}"
            )
        else:
            # should be something like 'Submitted batch job 11301013'
            stdout = res.stdout
            stderr = res.stderr
            slurm_submitted_msg = "Submitted batch job "
            if stdout.startswith(slurm_submitted_msg):
                matches = re.match(slurm_submitted_msg + r"(\d*)", stdout)
                logging.debug(stdout)
                jobid = int(matches.groups()[0])
                # Save the jobid locally so that we can later map jobname to jobid for future slurm query
                self._save_jobid(local_job_paths, jobid)
                return jobid
            else:
                raise ValueError(
                    f"Job scheduled without error but could not parse slurm output: \nstdout:\n{stdout}\nstderr:\n{stderr}"
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
        is_job_array = isinstance(job_info.python_args, list)
        if is_job_array:
            # For a job array, we write down the list of arguments in a file that is then read
            # in the entrypoint script and the $SLURM_ARRAY_TASK_ID-th argument is evaluated for each task.
            with open(local_job_paths.job_path() / "python-args.txt", "w") as f:
                for x in job_info.python_args:
                    if isinstance(x, dict):
                        x = " ".join(f"--{k}={v}" for k, v in x.items())
                    f.write(x + "\n")
        with open(local_job_paths.slurm_entrypoint_path(), "w") as f:
            remote_path = JobPathLogic.from_jobname(
                jobname=job_info.jobname,
                root_path=self.config.remote_slurmpilot_path(job_info.cluster),
            )
            slurm_script = generate_main_slurm_script(
                job_info=job_info,
                entrypoint_path_from_cwd=local_job_paths.entrypoint_path_from_cwd(),
                remote_jobpath=remote_path.resolve_path(),
            )
            f.write(slurm_script)

        self._generate_metadata(local_job_paths, job_info)
        return local_job_paths

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
        stderrs = []
        for filename in local_path.log_path().glob("*stderr"):
            with open(str(filename), "r") as f:
                stderrs.append("".join(f.readlines()))
        stdouts = []
        for filename in local_path.log_path().glob("*stdout"):
            with open(str(filename), "r") as f:
                stdouts.append("".join(f.readlines()))
        if len(stderrs) > 1 or len(stdouts) > 1:
            print(
                "Found several logs, assuming a jobarray was ran and returning only the last log."
            )
        stdout = stdouts[-1] if stdouts else "No log yet."
        stderr = stderrs[-1] if stderrs else "No log yet."
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
        config: Config | None = None,
    ) -> JobMetadata:
        """
        :param config:
        :return:
        """
        if config is None:
            config = load_config()
        metadatas = list_metadatas(
            root=config.local_slurmpilot_path() / "jobs", n_jobs=1
        )
        if len(metadatas) > 0:
            return metadatas[0]
        raise ValueError(f"No job was found at {config.local_slurmpilot_path()}")

    def cluster(self, jobname: str):
        """
        :param jobname:
        :return: retrieves the cluster where `jobname` was launched by querying local files
        """
        job_metadata = JobMetadata.from_jobname(jobname=jobname)
        return job_metadata.cluster

    def list_metadatas(self, n_jobs: int):
        root = (self.config.local_slurmpilot_path() / "jobs").expanduser()
        return list_metadatas(root=root, n_jobs=n_jobs)

    def status(self, jobnames: list[str]) -> list[str | None]:
        # TODO handle case of status missing
        jobinfos = job_infos(
            jobid_from_jobname=self.jobid_from_jobname,
            jobnames=jobnames,
            connections=self.connections,
        )
        return [jobinfo.State for jobinfo in jobinfos]

    def print_jobs(
        self, n_jobs: int = 10, max_colwidth: int = 50, status_verbose: bool = True
    ):
        jobs = self.list_metadatas(n_jobs)
        print("Calling remote sacct on remote nodes to get status.")
        jobinfos = job_infos(
            jobid_from_jobname=self.jobid_from_jobname,
            jobnames=[job.jobname for job in jobs],
            connections=self.connections,
        )
        print_jobs(
            jobinfos=jobinfos,
            n_jobs=n_jobs,
            max_colwidth=max_colwidth,
            status_verbose=status_verbose,
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
        print(f"Downloading logs into {format_highlight(local_path.log_path())}")
        remote_path = JobPathLogic.from_jobname(
            jobname=jobname,
            root_path=self.config.remote_slurmpilot_path(cluster),
        )
        try:
            self.connections[cluster].download_folder(
                remote_path.log_path(), local_path.log_path()
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
    def job_creation_metadata(jobname: str) -> JobMetadata | None:
        return JobMetadata.from_jobname(jobname)

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
