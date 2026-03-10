from dataclasses import dataclass
from pathlib import Path


@dataclass
class JobCreationInfo:
    """Describes everything needed to submit a Slurm job.

    Attributes:
        jobname: Unique name for the job (may contain subfolders, e.g. "group/run1").
        entrypoint: Script to run, relative to `src_dir`.
        cluster: Target cluster name (e.g. "mock", "local", or a hostname alias from config).
        src_dir: Local directory to ship to the cluster. Defaults to current directory.
        bash_setup_command: Shell command run before the entrypoint (e.g. conda activate).
        python_binary: If set, use this Python interpreter instead of bare bash.
        python_args: Arguments forwarded to the Python entrypoint. A dict is converted to
            ``--key=value`` flags. Ignored in bash mode.
        partition: Slurm partition to use.
        n_cpus: CPUs per task.
        n_gpus: GPUs per node.
        mem: Memory per node in MB.
        max_runtime_minutes: Wall-clock time limit.
        account: Slurm account to charge.
        env: Extra environment variables injected via ``--export``.
        sbatch_arguments: Raw extra flags passed verbatim to sbatch.
    """

    jobname: str
    entrypoint: str
    cluster: str
    src_dir: str | None = None
    bash_setup_command: str | None = None
    python_binary: str | None = None
    python_args: str | dict | list[str] | list[dict] | None = None
    n_concurrent_jobs: int | None = None
    python_libraries: list[str] | None = None
    partition: str | None = None
    n_cpus: int = 1
    n_gpus: int | None = None
    mem: int | None = None
    max_runtime_minutes: int = 60
    account: str | None = None
    env: dict | None = None
    sbatch_arguments: str | None = None

    def __post_init__(self):
        if self.src_dir is None:
            self.src_dir = "./"

    def check_path(self):
        assert Path(self.src_dir).exists(), f"src_dir not found: {self.src_dir}"
        ep = Path(self.src_dir) / self.entrypoint
        assert ep.exists(), f"entrypoint not found: {ep}"
        if self.python_libraries:
            for lib in self.python_libraries:
                assert Path(lib).exists(), f"python_library not found: {lib}"
        if self.n_concurrent_jobs is not None:
            assert isinstance(self.python_args, list), (
                "n_concurrent_jobs can only be used when python_args is a list."
            )
