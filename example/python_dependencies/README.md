# Example: shipping a local Python library

This example shows how to send a local Python package alongside your script so it
can be imported on the cluster — without publishing it to PyPI or manually editing
`PYTHONPATH`.

## Directory layout

```
python_dependencies/
  job.yaml                          # sp launch config
  launch_python_dependencies.py     # Python API launcher
  script/
    main_using_custom_library.py    # job entrypoint
  custom_library/
    __init__.py
    speed_of_light.py               # the library being shipped
```

## What the job does

The entrypoint `script/main_using_custom_library.py` imports `custom_library`, which
lives in a sibling directory and is **not** installed in any environment on the cluster.

Slurmpilot handles this by:

1. Copying `custom_library/` into the job folder (next to `script/`).
2. Adding the job folder to `PYTHONPATH` in the generated Slurm script, so
   `from custom_library.speed_of_light import speed_of_light` resolves correctly.

Because `python_args` is a **list**, Slurmpilot automatically submits a **Slurm job
array** (`#SBATCH --array=0-1`) — one task per element.  The argument list is written
to `python-args.txt` in the job folder; at runtime each task reads its own line using
`$SLURM_ARRAY_TASK_ID` and passes it to the script.  This means both learning-rate
runs are submitted in a single `sbatch` call and can execute in parallel.

## How to launch

### Option 1 — CLI with YAML config

Edit `job.yaml` to set your cluster and partition, then:

```bash
# launch on the current machine, Slurm should be installed
sp launch --config example/python_dependencies/job.yaml --cluster local --partition YOURPARTITION

# launch on a remote machine, `ssh REMOTEHOST` should work
sp launch --config example/python_dependencies/job.yaml --cluster REMOTEHOST --partition YOURPARTITION

# launch on the current machine, emulating Slurm (to test the script)
sp launch --config example/python_dependencies/job.yaml --cluster REMOTEHOST --partition YOURPARTITION
```

You can also preview the generated Slurm script without submitting:

```bash
sp launch --config example/python_dependencies/job.yaml --dry-run
```

### Option 2 — Python API

See `example/python_dependencies/launch_python_dependencies.py` which you can run with
```bash
python example/python_dependencies/launch_python_dependencies.py
```

The script calls `default_cluster_and_partition()` to pick the cluster from your
config. 

## Expected output

After the job completes (`sp log <jobname>`) you should see one line per array task:

```
The speed of light is 299792458 m/s and the learning-rate passed was 0.01.
To get the speed of light number coming from the custom library,
Slurmpilot copied the custom library and added its path the PYTHONPATH. Life is beautiful ☀️.

The speed of light is 299792458 m/s and the learning-rate passed was 0.02.
To get the speed of light number coming from the custom library,
Slurmpilot copied the custom library and added its path the PYTHONPATH. Life is beautiful ☀️.
```

(Task 0 uses `--learning-rate 0.01`, task 1 uses `--learning-rate 0.02`.)
