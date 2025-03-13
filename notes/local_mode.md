# Local mode

Goal: allow to run Slurmpilot when logged in a node with Slurm access without requiring SSH access from laptop.

```python
from slurmpilot import JobCreationInfo, SlurmWrapper
jobinfo = JobCreationInfo(
    python_args=f"--learning_rate 1e-3 --batch_size 32",
    python_libraries=["foo/custom_library"],
    src_dir="blah/src",
    entrypoint="main.py",
    cluster="local", 
    partition="h100-partition"
)
jobid = SlurmWrapper(clusters=['local']).schedule_job(jobinfo)
# copy files locally
# call sbatch locally
```

We would need for this:
1) add a local command execution (would be straightforward)
2) add a "local" mapping from clusters to local execution
3) make sure that configuration mechanism is still meaningful, for instance we could use `configs/cluster/local.yaml`