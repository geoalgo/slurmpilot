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

It would be nice to be able to restart failed jobs from a list (in case of transient errors).

We could also expose another function to schedule a list of jobs.