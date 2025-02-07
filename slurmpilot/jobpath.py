from pathlib import Path


def slurmpilot():
    res = Path("~/slurmpilot").expanduser()
    res.mkdir(exist_ok=True)
    return res


class JobPathLogic:
    # Could also pass a JobCreationInfo, we dont do it here as it contains other stuff related to ressources etc not
    # relevant here
    def __init__(
        self,
        jobname: str,
        entrypoint: str | None = None,
        src_dir_name: str | None = None,
        root_path: str | None = None,
    ):
        f"""
        performs bookeeping path logic, valid both locally and remotely.
        :param root_path: path where slurmpilot is available
        :param jobname: name of the job, can nest subfolders, for instance "group_experiment_1/experiment2" is allowed 
        and the folder of the job will then be "~/slurmpilot/jobs/group_experiment_1/experiment2".
        :param src_dir_name: directory where the entrypoint is found
        :param entrypoint: path to the entrypoint starting at `src_dir_name`, e.g. f"{src_dir_name}/{entrypoint}" 
        should exists
        """
        self.root_path = root_path if root_path else str(slurmpilot())
        self.jobname = jobname
        self.entrypoint = entrypoint
        self.src_dir_name = src_dir_name

    @classmethod
    def from_jobname(cls, jobname: str, root_path: Path = None):
        return cls(
            jobname=jobname,
            root_path=root_path,
        )

    def job_path(self) -> Path:
        return self.resolve_path()

    def resolve_path(self, path: Path | str | None = None) -> Path:
        if path is not None:
            return Path(self.root_path) / "jobs" / self.jobname / path
        else:
            return Path(self.root_path) / "jobs" / self.jobname

    def slurmpilot_path(self) -> Path:
        return Path(self.root_path)

    def metadata_path(self) -> Path:
        return self.resolve_path("metadata.json")

    def jobid_path(self):
        return self.resolve_path("jobid.json")

    def log_path(self) -> Path:
        return self.resolve_path("logs")

    def stderr_path(self: str) -> Path:
        # TODO case of jobarray
        return self.log_path() / "stderr"

    def stdout_path(self) -> Path:
        # TODO case of jobarray
        return self.log_path() / "stdout"

    def src_path(self) -> Path:
        return self.resolve_path(self.src_dir_name)

    def slurm_entrypoint_path(self) -> Path:
        return self.resolve_path() / "slurm_script.sh"

    def entrypoint_path_from_cwd(self):
        # TODO ugly name, can we avoid it?
        return Path(self.src_path().name) / self.entrypoint
