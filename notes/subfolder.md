# Subfolder

Currently, all jobs are stored under `~/slurmpilot/jobs/{jobname}`. 
A desirable feature would be to be able to save to `~/slurmpilot/jobs/{expid}/{jobname}` or
`~/slurmpilot/jobs/{experiment_group}/{expid}/{jobname}`.

We could support both by adding:
```python
jobinfo = JobCreationInfo(
    jobname=jobname,
    expid=f"{experiment_group}/{expid}",
    **kwargs,
)
jobid = SlurmWrapper().schedule_job(jobinfo)
```

which would create jobs under `~/slurmpilot/jobs/{experiment_group}/{expid}/{JOBID}`.

The advantage of this is that this would be backward compatible. 

We may want to also set expid by default. This would allow to avoid flooding
`~/slurmpilot/jobs/` directory but this would be backward incompatible.