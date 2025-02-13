from pathlib import Path

from slurmpilot import JobCreationInfo
from slurmpilot.slurm_main_script import (
    generate_main_slurm_script,
)

entrypoint = "main.py"
entrypoint_path_from_cwd = f"dummy/{entrypoint}"
python_binary = "/bin/python"
python_args = {"learning-rate": 0.1, "batch-size": 32}
python_args_string = " ".join(f"--{k}={v}" for k, v in python_args.items())
jobpath = "/Users/foo/slurmpilot/jobs/test/dummy"
jobname = "test/dummy"


def show_first_difference(got, expected):
    for x, y in zip(got.split("\n"), expected.split("\n")):
        if x != y:
            print("line mismatch", x, y)
        break


def test_generate_main_slurm_script():
    expected = f"""\
#!/bin/bash
#SBATCH --job-name={jobname}
#SBATCH --output=logs/stdout
#SBATCH --error=logs/stderr
#SBATCH --cpus-per-task=1
#SBATCH --time=60
export PYTHONPATH=$PYTHONPATH:{jobpath}
{python_binary} {entrypoint_path_from_cwd} {python_args_string}
"""

    # TODO test each of job creation info argument
    got = generate_main_slurm_script(
        job_info=JobCreationInfo(
            jobname=jobname,
            entrypoint=entrypoint_path_from_cwd,
            python_binary=python_binary,
            python_args=python_args,
        ),
        entrypoint_path_from_cwd=Path(entrypoint_path_from_cwd),
        jobpath=Path(jobpath),
    )
    show_first_difference(got, expected)
    print(r"got: \n", got)
    print(r"expected: \n", expected)

    assert got == expected


def test_generate_main_slurm_script_array():
    n_jobs = 10
    n_concurrent_jobs = 2
    expected = f"""\
#!/bin/bash
#SBATCH --job-name={jobname}
#SBATCH --output=logs/%a.stdout
#SBATCH --error=logs/%a.stderr
#SBATCH --cpus-per-task=1
#SBATCH --time=60
#SBATCH --array=0-{n_jobs - 1}%{n_concurrent_jobs}
export PYTHONPATH=$PYTHONPATH:{jobpath}

# checks that at least $SLURM_ARRAY_TASK_ID lines exists in python arguments.
[ "$(wc -l < python-args.txt)" -lt "$SLURM_ARRAY_TASK_ID" ] && {{ echo "Error: python-args.txt has fewer lines than \$max_num_line ($max_num_line)."; echo "ERROR"; exit 1; }}

{python_binary} {entrypoint_path_from_cwd} `sed -n "$(( $SLURM_ARRAY_TASK_ID + 1 ))p" python-args.txt`
"""

    # TODO test each of job creation info argument
    got = generate_main_slurm_script(
        job_info=JobCreationInfo(
            jobname=jobname,
            entrypoint=entrypoint_path_from_cwd,
            python_binary=python_binary,
            python_args=[python_args] * 10,
            n_concurrent_jobs=2,
        ),
        entrypoint_path_from_cwd=Path(entrypoint_path_from_cwd),
        remote_jobpath=Path(jobpath),
    )
    show_first_difference(got, expected)
    print(r"got: \n", got)
    print(r"expected: \n", expected)

    assert got == expected
