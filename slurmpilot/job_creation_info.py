import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)


@dataclass
class JobCreationInfo:
    jobname: str
    entrypoint: str | None = None

    bash_setup_command: str | None = (
        None  # if specified a bash command that gets executed before the main script
    )
    src_dir: str | None = None
    remote_dir: str | None = None  # directory to write slurmpilot file in remote cluster, default to what is configured in your cluster configuration
    exp_id: str | None = None

    sbatch_arguments: str | None = None  # argument to be passed to sbatch

    # python
    python_binary: str | None = None
    # arguments to be passed to python script, if dictionary then arguments
    # are converted to string with `--key=value` for all key, values of the dictionary
    python_args: str | dict | None = None
    # path existing remotely to be included in PYTHONPATH so that they can be imported in python
    python_paths: list[str] | None = None
    # python libraries existing locally to be sent to the remote and added to the PYTHONPATH
    python_libraries: list[str] | None = None

    # ressources
    cluster: str = None
    partition: str = None
    n_cpus: int = 1  # number of cores
    n_gpus: int = None  # number of gpus per node
    mem: int = None  # memory pool for each core in MB
    max_runtime_minutes: int = 60  # max runtime in minutes
    account: str = None
    env: dict = None
    nodes: int = None  # number of nodes for this job
    nodelist: str = None
    entrypoint_template: str | None = None
    # Used when the bash file provided is a "template", i.e., it has keywords which should should be replaced.
    # It is inferred in post and does not have to specified by the user.
    template_data: dict | None = None  # dictionary with the keywords and the strings to replace them with in the template file
    
    def __post_init__(self):
        if self.python_args:
            if self.python_binary is None:
                logging.warning(
                    f"Python binary not set but passing `python_args`: {self.python_args}."
                )
        if self.python_binary is not None:
            assert (
                Path(self.entrypoint).suffix == ".py"
            ), f"Must provide a python script ending with .py when using `python_binary` but got {self.entrypoint}."
        if self.src_dir is None:
            self.src_dir = "./"

        # TODO: A bit hacky, this. But I think that naming the bash file with an explicit "_template.sh"
        # is the safest way to ensure that the user doesn't accidentally use a non template as a template
        # or vice-a-versa.
        if self.entrypoint.endswith("_template.sh"):
            self.entrypoint_template = self.entrypoint
            self.entrypoint = self.entrypoint[:-len("_template.sh")]
        else:
            self.entrypoint_template = None

    def check_path(self):
        assert Path(
            self.src_dir
        ).exists(), f"The src_dir path {self.src_dir} is missing."

        file_name = self.entrypoint if self.entrypoint_template is None else self.entrypoint_template
        entrypoint_path = Path(self.src_dir) / file_name

        assert(
            entrypoint_path.exists()
        ), f"The entrypoint template could not be found at {entrypoint_path}."

    def sbatch_preamble(self) -> str:
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
