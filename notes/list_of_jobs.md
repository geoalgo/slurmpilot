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

We could also expose a specific function to schedule a list of jobs:

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

This would allow to configure specifically array of jobs, for instance
* handling errors
* log naming
* ...


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
* log structure? likely jobname/logs/std-%a where %a is the array jobid
* how to handle list-job CLI?

## Proposal
Add `schedule_jobs` to SlurmWrapper class.
```python
jobid = SlurmWrapper(clusters=[cluster]).schedule_jobs(jobinfo)
```

Update logic so that arguments are sent via a file and loaded in python mode.

TODOs:
* test
* adapt CLI, status job etc
Done:
* writes corresponding slurm job array
* read args.json in `_generate_main_slurm_script` for python mode
* add `schedule_jobs` which:
  * writes args.json for python_args which contains a list of arguments


## CLI

We discuss here how the CLI will behave after the change.
For single job, we want the CLI to be unchanged.

For job-array, we need to discuss `--log`, `--download`, `--status`, `--stop` and `--list-jobs`.
WLOG, assume we have 3 jobs with a base jobname `job-array`.

* `sp --log`: assuming job-array is the last job, log `job-array_N` 
* `sp --log job-array`: logs the last job in the array
* `sp --log job-array_N`:  logs the N-th job in the array
=> mainly impact the logic of the mapping between the string passed in CLI and what is fetched.

*status.* change, similar case as list-jobs
*stop.* does not change if we stop only the parent job
*download.* does not change?

* `sp --list--jobs`:  
```
                         job           date cluster       status                         full jobname
job-array_2 05/12/24-09:13 kis  ️Running 🏃  ktabpfn/job-array_2
job-array_1 04/12/24-13:49 kis Completed ✅  ktabpfn/job-array_1
job-array_0 04/12/24-13:49 kis Completed ✅  ktabpfn/job-array_0
scalarjob   04/12/24-13:49 kis Completed ✅  dummy/scalarjob
```

Done:
* list-jobs
* download
* log
* stop