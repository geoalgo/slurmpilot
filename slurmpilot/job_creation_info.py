import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)


@dataclass
class JobCreationInfo:
    """
    Dataclass to describes job creation information.
    Attributes:
        jobname (str): The name of the job.
        entrypoint (str): Path of the script to execute, relative to `src_dir`.
        cluster (str | None): Cluster to be used, should be a hostname that can be reached with ssh.
        bash_setup_command (str | None): A bash command that gets executed before the main `entrypoint` script.
        src_dir (str | None): Directory that is be shipped to slurm, default to current directory. Must contain the entrypoint script.
        remote_dir (str | None): Directory to write slurmpilot file in remote cluster, default to what is configured in your cluster configuration
        sbatch_arguments (str | None): Arguments to be passed to sbatch, use it in case an argument you want to use in Slurm is not yet supported, for instance: `--threads-per-core=1`.
        python_binary (str | None): Path to the binary used to evaluate the entrypoint script, if not passed, use `bash` to evaluate the entrypoint script.
        python_args (str | dict | list[str] | list[dict] | None): Arguments to be passed to python script. When using `str` or `dict`, arguments are for a single job and when using a dictionary, the arguments are converted to string with `--key=value` for all key and value of the dictionary. When using `list`, then slurmpilot will schedule one job each with a jobarray with a job for each argument.
        n_concurrent_jobs (int | None): Number of concurrent jobs, can only be used when `python_args` is a list, will generate a line like `#SBATCH --array=0-{n_jobs}%{n_concurrent_jobs}` where `n_jobs` is the length of `python_args`
        python_paths (list[str] | None): Path existing remotely to be included in PYTHONPATH so that they can be imported in python.
        python_libraries (list[str] | None): Python libraries existing locally to be sent to the remote and added to the PYTHONPATH
        partition (str): Partition to use
        n_cpus (int): Number of cores to use
        n_gpus (int): Number of GPUs per node to use
        nodes (int): Number of nodes for this job
        mem (int): Memory pool for each core in MB
        max_runtime_minutes (int): Max runtime in minutes
        account (str | None): Account to charge
        env (dict): Environment variables to use in the slurm script
        nodelist (str): List of nodes to consider, useful to exclude faulty nodes
    """

    jobname: str
    entrypoint: str
    cluster: str | None = None
    bash_setup_command: str | None = None  #
    src_dir: str | None = None
    remote_dir: str | None = None
    sbatch_arguments: str | None = None

    python_binary: str | None = None
    python_args: str | dict | list[str] | list[dict] | None = None
    n_concurrent_jobs: int | None = None
    python_paths: list[str] | None = None
    python_libraries: list[str] | None = None

    partition: str = None
    n_cpus: int = 1
    n_gpus: int = None
    mem: int = None  # memory pool for each core in MB
    max_runtime_minutes: int = 60  # max runtime in minutes
    account: str | None = None  # account to charge
    env: dict = None  # environment variable to use in the slurm script
    nodes: int = None  # number of nodes for this job
    nodelist: str = None  # list of nodes to consider

    def __post_init__(self):
        if self.python_args:
            if self.python_binary is None:
                logging.warning(
                    f"{self.jobname}: Python binary not set but passing `python_args`: {self.python_args}."
                )
        # if self.python_binary is not None:
        #     assert (
        #         Path(self.entrypoint).suffix == ".py"
        #     ), f"Must provide a python script ending with .py when using `python_binary` but got {self.entrypoint}."
        if self.src_dir is None:
            self.src_dir = "./"
        if self.n_concurrent_jobs is not None:
            assert isinstance(
                self.python_args, list
            ), "n_concurrent_jobs can only be used with a list of python_args."

    def check_path(self):
        assert Path(
            self.src_dir
        ).exists(), f"The src_dir path {self.src_dir} is missing."
        entrypoint_path = Path(self.src_dir) / self.entrypoint
        assert (
            entrypoint_path.exists()
        ), f"The entrypoint could not be found at {entrypoint_path}."

    def sbatch_preamble(self, is_job_array: bool = False) -> str:
        """
        Spits a preamble like this one valid for sbatch:
        #SBATCH -p {partition}
        #SBATCH --mem {mem}
        ...
        :return:
        """
        res = ""
        sbatch_line = lambda config: f"#SBATCH {config}\n"
        res += sbatch_line(f"--job-name={self.jobname}")
        if is_job_array:
            # %a is the task id corresponding to SLURM_ARRAY_TASK_ID env variable
            # e.g. we write the log as `logs/12.stdout` for the 12-th job.
            res += sbatch_line(f"--output=logs/%a.stdout")
            res += sbatch_line(f"--error=logs/%a.stderr")
        else:
            res += sbatch_line(f"--output=logs/stdout")
            res += sbatch_line(f"--error=logs/stderr")
        if self.n_cpus:
            res += sbatch_line(f"--cpus-per-task={self.n_cpus}")
        if self.partition:
            res += sbatch_line(f"--partition={self.partition}")
        if self.mem:
            res += sbatch_line(f"--mem={self.mem}")
        if self.n_gpus and self.n_gpus > 0:
            res += sbatch_line(f"--gres=gpu:{self.n_gpus}")
        if self.nodes:
            res += sbatch_line(f"--nodes={self.nodes}")
        if self.account:
            res += sbatch_line(f"--account={self.account}")
        if self.nodelist:
            res += sbatch_line(f"--nodelist={self.nodelist}")
        if self.max_runtime_minutes:
            assert isinstance(
                self.max_runtime_minutes, int
            ), "maxruntime must be an integer expressing the number of minutes"
            res += sbatch_line(f"--time={self.max_runtime_minutes}")
        # res += sbatch_line("--chdir .")
        return res
