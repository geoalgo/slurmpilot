## Dev setup

```
pip install -e ".[dev]"
pre-commit install 
pre-commit autoupdate
```

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
* set environment variables
* stop all jobs
* support passing path to local configs
* subfolders
* allow to share common folders to avoid sending code lots of times?
* sync artefact of a job
* remove/replace sfree
* local configurations to allow clean repo, could be located in ~/slurmpilot/config
* test generation of slurm script/package to be sent
* able to see logs of latest job

**DONE**
* able to create jobs
* run ssh command to remote host
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

