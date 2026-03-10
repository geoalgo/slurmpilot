from pathlib import Path


class JobPath:
    """Path bookkeeping for a single job directory.

    The layout under ``root`` is::

        root/
          jobs/
            {jobname}/
              slurm_script.sh
              metadata.json
              jobid.json
              logs/
                stdout
                stderr
              {src_dir_name}/     <- copied source directory
                {entrypoint}
    """

    def __init__(self, jobname: str, root: Path, src_dir_name: str | None = None):
        self.jobname = jobname
        self.root = Path(root)
        self._src_dir_name = src_dir_name

    @property
    def job_dir(self) -> Path:
        return self.root / "jobs" / self.jobname

    @property
    def slurm_script(self) -> Path:
        return self.job_dir / "slurm_script.sh"

    @property
    def metadata(self) -> Path:
        return self.job_dir / "metadata.json"

    @property
    def jobid_file(self) -> Path:
        return self.job_dir / "jobid.json"

    @property
    def log_dir(self) -> Path:
        return self.job_dir / "logs"

    @property
    def stdout(self) -> Path:
        return self.log_dir / "stdout"

    @property
    def stderr(self) -> Path:
        return self.log_dir / "stderr"

    @property
    def src(self) -> Path:
        assert self._src_dir_name is not None, "src_dir_name was not provided"
        return self.job_dir / self._src_dir_name

    def entrypoint_from_cwd(self, entrypoint: str) -> Path:
        """Return the entrypoint path relative to job_dir (used as cwd at runtime)."""
        assert self._src_dir_name is not None, "src_dir_name was not provided"
        return Path(self._src_dir_name) / entrypoint
