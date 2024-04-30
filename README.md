## Dev setup

```
pip install -e ".[dev]"
pre-commit install 
pre-commit autoupdate
```

## Scheduling a job
### Workflow
When scheduling a job, the files required to run it are first copied to `~/slurmpilot/your_job_name` and then
send to the remote host to `~/slurmpilot/your_job_name` (those defaults paths are modifiable).

In particular, the following files are generated locally under `~/slurmpilot/your_job_name`:
* metadata.json: contains metadata such as time and the configuration of the job that was scheduled
* jobid.json: contains the slurm jobid obtained when scheduling the job, if this step was successful
* slurm_script.sh: a slurm script automatically generated from your options that is executed on the remote node with sbatch
* src_dir: the folder containing the entrypoint
* src_dir/entrypoing: the entrypoint to be executed

On the remote host, the logs are written under `logs/stderr` and `logs/stdout` and the current working dir is `~/slurmpilot/your_job_name`.

### Job file structure


## FAQ

**Writing common setup files.**
Use SLURMPILOT_PATH, see XX as an example.

## North star
Support similar configs as skypilot, also 
https://github.com/skypilot-org/skypilot/blob/master/examples/huggingface_glue_imdb_app.yaml

e.g. would need to support:
* sky launch cluster.yaml
* sky status
* sky down XXX
* ssh XXX
* sky queue XXX "ls"

* evaluating from python from instance cmd="python run_glue.py --learning_rate=1e-3"
Mid-term: 
* support workspace/subfolder
* example to run GLUE fine tuning

## Tasks

**TODOs**
* tool to display logs/status from terminal
  * (sp added by concatenating to path, suggestion made in setup.py)
  * sp --help
  * sp --log  # show last log
  * sp --log job-name
  * sp --status 10  # show status of last 10 jobs (list pulled from local files)
  * sp --status job-name
  * sp --sync job-name  # sync artifacts
* when creating job, show command that can be copy-pasted to display log, status, sync artifact
* subfolders
* support setting local configs path via environment variables
* stop all jobs
* allow to share common folders to avoid sending code lots of times?
* sync artefact of a job

**DONE**
* local configurations to allow clean repo, could be located in ~/slurmpilot/config
* set environment variables
* able to create jobs
* able to see logs of latest job
* run ssh command to remote host
* test generation of slurm script/package to be sent
* run sfree on remote cluster
* able to see logs of one job
* local path rather that current dir
* test path logic
* able to see status of jobs
* list all jobs and see their status
* enable multiple configurations
* "integration" tests that runs sinfo and lightweight operations 
* option to wait until complete or failed
* stop job

