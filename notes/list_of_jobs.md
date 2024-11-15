# List of jobs

Supporting list of jobs is a features that have been asked by several people already as being quite important.

We would like to support slurm array, but also makes the interface more convenient to schedule list and group them.

It would be probably best to iterate first on the low hanging fruits and make the experience better with products
before going to more advanced options such as job arrays.

For instance, a typical way to launch experiments now is to loop over a list and send multiple jobs:

```python
for learning_rate in [1e-3, 1e-2, 1e-1]:
    jobinfo = JobCreationInfo(
        python_args=f"--learning_rate {learning_rate} --batch_size 32",
        python_libraries=[str(root_dir / "custom_library")],
        src_dir="./",
        ...
    )
    jobid = SlurmWrapper(clusters=[cluster]).schedule_job(jobinfo)
```

This is suboptimal because:
* we send the libraries and source dir for each job instead of once
* the naming is not going to trace well the iteration

We could improve it by allowing to do something like this:
```python
jobinfo = JobCreationInfo(
    python_args=[f"--learning_rate {learning_rate} --batch_size 32" for learning_rate in [1e-3, 1e-2, 1e-1]],
    python_libraries=[str(root_dir / "custom_library")],
    src_dir="./",
    jobname="fine-tune-mlp",
    ...
)
jobid = SlurmWrapper(clusters=[cluster]).schedule_job(jobinfo)
```
The following should:
* send the code only once
* use a naming grouping strategy so that jobs are either called: "fine-tune-mlp-1", "fine-tune-mlp-2", ... or "fine-tune-mlp/1", "fine-tune-mlp/2", ...

The type of `JobCreationInfo.python_args` would be `Union[str, list[str]]`.
It would be nice to be able to restart failed jobs from a list (in case of transient errors).

We could also expose another function to schedule a list of jobs which would avoid to have a union for `python_args`.

```
jobinfo = JobCreationInfo(
    python_args=[f"--learning_rate {learning_rate} --batch_size 32" for learning_rate in [1e-3, 1e-2, 1e-1]],
    python_libraries=[str(root_dir / "custom_library")],
    src_dir="./",
    jobname="fine-tune-mlp",
    ...
)
jobid = SlurmWrapper(clusters=[cluster]).schedule_jobs(jobinfo)
```


## Code

currently, scheduling looks like this 
```
def schedule_job():
    _prepare_local_data()
    _send_local_data()
    _call_sbatch()   
```

the question is how could we factor shared code, ideally we would like to do

```
def schedule_jobs(args):
    _prepare_local_data()
    _send_local_data()
    for arg in args:
        _call_sbatch(arg)   
```

or we could send the argument instead and associate it to the job index:
```
def schedule_jobs(args):
    _prepare_local_data()
    _send_local_data()
    for i, arg in enumerate(args):
        _send_arg(arg, i)
        _call_sbatch()   
```

This would need to refactor `_send_local_data()` so that sending python arg is decoupled.


## Jobarray

```
#!/bin/bash
#SBATCH --job-name=arrayjob
#SBATCH --array=1-10

# Specify the path to the config file depending on the array task id
config_path=config-$SLURM_ARRAY_TASK_ID.txt
```

Options:
* dump python args and load $SLURM_ARRAY_TASK_ID-th element
* the API should then be something like:
* `def schedule_jobs(jobinfo: JobInfo, python_args: list[dict|str], num_max_concurrent_jobs: int)`

Currently:
```
#!/bin/bash
#SBATCH --job-name=judge-tuning-v14
{bash_setup_command}
export PYTHONPATH=...
python script/evaluate_fidelity.py --expid=v14-loop-v2-chatbot-arena --model=Meta-Llama-3.1-8B-Instruct 
```

Proposed:
```
#!/bin/bash
#SBATCH --job-name=judge-tuning-v14
# TODO depends on the number of arguments, 
# 10 is the number of arguments, 3 the max number of jobs to run at the same time
#SBATCH --array=1-10%3   
{bash_setup_command}
export PYTHONPATH=$PYTHONPATH:...
python_args=load_args($SLURM_ARRAY_TASK_ID)  # return the SLURM_ARRAY_TASK_ID-th argument 
python script/evaluate_fidelity.py $python_args
```

Question:
* jobid and jobname in slurmpilot
* log structure? jobname/logs/std-%a where %a is the array jobid?