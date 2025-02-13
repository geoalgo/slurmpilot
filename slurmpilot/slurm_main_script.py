import io
from pathlib import Path

from slurmpilot import JobCreationInfo
from slurmpilot.jobpath import JobPathLogic


def _python_args_sbatch_string(job_info: JobCreationInfo) -> str | tuple[str, str]:
    """
    :return: In the case of a single job, returns python arguments. In the case of a job-array returns Sbatch preamble
    and python arguments. TODO split into two functions.
    """
    if isinstance(job_info.python_args, dict):
        # the argument is a dictionary we convert it to argparse arguments,
        return "", " ".join(
            f"--{key}={value}" for key, value in job_info.python_args.items()
        )
    elif isinstance(job_info.python_args, list):
        # TODO make sure that at $SLURM_ARRAY_TASK_ID is lower than the number of lines in python-args.txt
        lines = [""]
        lines.append(
            "# checks that at least $SLURM_ARRAY_TASK_ID lines exists in python arguments."
        )
        lines.append(
            '[ "$(wc -l < python-args.txt)" -lt "$SLURM_ARRAY_TASK_ID" ] && { echo "Error: python-args.txt has fewer lines than \$max_num_line ($max_num_line)."; echo "ERROR"; exit 1; }'
        )
        lines.append("")
        argument = r'`sed -n "$(( $SLURM_ARRAY_TASK_ID + 1 ))p" python-args.txt`'
        preamble = "\n".join(lines) + "\n"
        return preamble, argument
    elif isinstance(job_info.python_args, str):
        return "", job_info.python_args
    elif job_info.python_args is None:
        return "", ""
    else:
        raise ValueError("Got unexpected type for python args")


def _generate_python_slurm_script(
    job_info: JobCreationInfo,
    entrypoint_path_from_cwd: Path,
    jobpath: Path,
) -> str:
    """
    Given information of a job, returns the slurm script to execute for a python job.
    :param job_info:
    :param entrypoint_path_from_cwd:
    :param jobpath:
    :return:
    """
    with io.StringIO() as f:
        # TODO streamline this code, make separate function
        # set python_args as environment variable to be passed to python script
        # handles case where python_args is None, a string, a dict (must then be converted), a list (must then
        # fetched the right argument in python_args.json)
        if isinstance(job_info.python_args, list):
            # if the arguments are passed as a list, then we generated the sbatch array preamble
            # we also fetch the SLURM_ARRAY_TASK_ID-th element from python-args.json, set it to $PYTHON_ARGS
            # and use "$PYTHON_ARGS" as `python_args_sbatch`
            n_jobs = len(job_info.python_args) - 1
            n_concurrent_jobs = (
                job_info.n_concurrent_jobs if job_info.n_concurrent_jobs else 1
            )
            f.write(f"#SBATCH --array=0-{n_jobs}%{n_concurrent_jobs}\n")
        # TODO need to set bash_setup_command in case we need the sbatch directive for job-array
        if job_info.bash_setup_command:
            f.write(job_info.bash_setup_command + "\n")

        # add library to PYTHONPATH when using python mode
        libraries = [str(jobpath)]
        if job_info.python_paths is not None:
            libraries += job_info.python_paths
        if job_info.python_libraries:
            libraries += job_info.python_libraries
        f.write(f'export PYTHONPATH=$PYTHONPATH:{":".join(libraries)}\n')

        preamble, pythonargs = _python_args_sbatch_string(job_info)
        if len(preamble) > 0:
            f.write(preamble)

        # write the line to call python with the provided binary, entrypoint, and arguments
        f.write(f"{job_info.python_binary} {entrypoint_path_from_cwd} {pythonargs}\n")
        f.seek(0)
        return f.read()


def generate_main_slurm_script(
    job_info: JobCreationInfo,
    entrypoint_path_from_cwd: Path,
    remote_jobpath: Path,
) -> str:
    """
    Generates a sbatch script for the given job information.
    Two modes are supported where in the simplest case, we call just a bash entrypoint script and in the second case
    we call a python entrypoint. In the python case, we make sure that the PYTHONPATH is updated with the current
    directory and possibly libraries that were sent.
    In the python case, if `python_args` is a list, then we generate a jobarray to run all arguments. This works
    by reading the `SLURM_ARRAY_TASK_ID`-th line of python-args.txt and passing it as an argument to the python script.
    :param job_info:
    :param entrypoint_path_from_cwd:
    :param remote_jobpath: path on the remote node of the job
    :return:
    """
    is_job_array = isinstance(job_info.python_args, list)
    # check that job_info.entrypoint extension is ".py"
    is_python_mode = not job_info.python_binary is None
    with io.StringIO() as f:
        f.write("#!/bin/bash\n")
        f.write(job_info.sbatch_preamble(is_job_array=is_job_array))
        # Add path containing the library to the PYTHONPATH so that they can be imported without requiring
        # the user to add `PYTHONPATH=.` before running scripts, e.g. instead of having to do
        # `PYTHONPATH=. python main.py`, users can simply do `python main.py`

        if is_python_mode:
            f.write(
                _generate_python_slurm_script(
                    job_info, entrypoint_path_from_cwd, remote_jobpath
                )
            )
        else:
            if job_info.bash_setup_command:
                f.write(job_info.bash_setup_command + "\n")
            f.write(f"bash {entrypoint_path_from_cwd}\n")

        f.seek(0)
        return f.read()
