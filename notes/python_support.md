# Python support

Here we discuss how we could support better python. We assume has a python main file called `main_python.py`.


## User experience
Currently, the user can only call bash script, two things need to happend as shown in `custom_library` example.

First he needs to have a bash script calling his python script:
```bash
#!/bin/bash
python main_python.py
```

Then he can call slurmpilot as follow:
```python
max_runtime_minutes = 60
root_dir = Path(__file__).parent
jobinfo = JobCreationInfo(
    cluster=cluster,
    jobname=jobname,
    entrypoint="main.sh",
    src_dir=str(root_dir / "script"),
    python_libraries=[str(root_dir / "custom_library")],
    partition=partition,
    n_cpus=1,
    max_runtime_minutes=max_runtime_minutes,
    # Shows how to pass an environment variable to the running script
    env={"API_TOKEN": "DUMMY"},
)
jobid = SlurmWrapper(clusters=[cluster]).schedule_job(jobinfo)
```

We would like instead to enable the user to call directly:

```python
jobinfo = JobCreationInfo(
    cluster=cluster,
    jobname=jobname,
    python_args="--learning_rate 1e-3 --batch_size 32",
    python_main=str(root_dir / "script" / "main_python.py"),
    python_bin="/home/XXX/YYY/bin/python",
    python_libraries=[str(root_dir / "custom_library")],
    partition=partition,
    n_cpus=1,
    max_runtime_minutes=max_runtime_minutes,
    # Shows how to pass an environment variable to the running script
    env={"API_TOKEN": "DUMMY"},
)
jobid = SlurmWrapper(clusters=[cluster]).schedule_job(jobinfo)
```

Note:
* we could also support passing a dictionary of arguments for `python_args`
* we could support passing a list of bash to be executed before the script (this could let the user source environments)

## How to make it happen

We need to generate a bash script that calls the main_python of the user, possibly also setting the python path correctly.

We could do it at the `SlurmWrapper` level and adapt the slurm script generated on the fly.

Maybe it can be done by just adapting `_generate_main_slurm_script`.