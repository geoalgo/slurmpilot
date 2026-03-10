import io
from pathlib import Path

from .job_creation_info import JobCreationInfo


def generate_slurm_script(
    job_info: JobCreationInfo,
    entrypoint_from_cwd: Path,
    job_run_dir: Path | None = None,
) -> str:
    """Generate a bash script suitable for submission with sbatch.

    :param job_info: job configuration.
    :param entrypoint_from_cwd: path to the entrypoint relative to the job
        directory (the working directory when the script executes).
    :param job_run_dir: absolute path of the job directory on the execution
        host. Used to set PYTHONPATH in python mode so that shipped libraries
        are importable. Pass the remote path for SSH clusters, the local path
        for mock.
    """
    with io.StringIO() as f:
        f.write("#!/bin/bash\n")
        _write_preamble(f, job_info)
        _write_body(f, job_info, entrypoint_from_cwd, job_run_dir)
        f.seek(0)
        return f.read()


def _write_preamble(f: io.StringIO, job_info: JobCreationInfo) -> None:
    def sbatch(opt: str) -> None:
        f.write(f"#SBATCH {opt}\n")

    sbatch(f"--job-name={job_info.jobname}")
    sbatch("--output=logs/stdout")
    sbatch("--error=logs/stderr")
    sbatch(f"--cpus-per-task={job_info.n_cpus}")
    if isinstance(job_info.python_args, list):
        n_tasks = len(job_info.python_args) - 1
        array_spec = f"0-{n_tasks}"
        if job_info.n_concurrent_jobs is not None:
            array_spec += f"%{job_info.n_concurrent_jobs}"
        sbatch(f"--array={array_spec}")
    if job_info.partition:
        sbatch(f"--partition={job_info.partition}")
    if job_info.mem:
        sbatch(f"--mem={job_info.mem}")
    if job_info.n_gpus and job_info.n_gpus > 0:
        sbatch(f"--gres=gpu:{job_info.n_gpus}")
    if job_info.account:
        sbatch(f"--account={job_info.account}")
    if job_info.max_runtime_minutes:
        sbatch(f"--time={job_info.max_runtime_minutes}")


def _write_body(
    f: io.StringIO,
    job_info: JobCreationInfo,
    entrypoint_from_cwd: Path,
    job_run_dir: Path | None,
) -> None:
    if job_info.bash_setup_command:
        f.write(job_info.bash_setup_command + "\n")

    if job_info.python_binary:
        if job_run_dir is not None:
            pythonpath_entries = [str(job_run_dir)]
            if job_info.python_libraries:
                for lib in job_info.python_libraries:
                    pythonpath_entries.append(str(job_run_dir / Path(lib).name))
            f.write(f'export PYTHONPATH=$PYTHONPATH:{":".join(pythonpath_entries)}\n')
        if isinstance(job_info.python_args, list):
            f.write('argument=$(sed -n "$(( SLURM_ARRAY_TASK_ID + 1 ))p" python-args.txt)\n')
            f.write(f"{job_info.python_binary} {entrypoint_from_cwd} $argument\n")
        else:
            args = _format_python_args(job_info.python_args)
            f.write(f"{job_info.python_binary} {entrypoint_from_cwd} {args}\n".rstrip() + "\n")
    else:
        f.write(f"bash {entrypoint_from_cwd}\n")


def _format_python_args(python_args: str | dict | None) -> str:
    if python_args is None:
        return ""
    if isinstance(python_args, str):
        return python_args
    if isinstance(python_args, dict):
        return " ".join(f"--{k}={v}" for k, v in python_args.items())
    raise TypeError(f"python_args must be str, dict, or None; got {type(python_args)}")
