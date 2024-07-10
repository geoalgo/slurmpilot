# Slurmpilot

## Installing

To install, run the following:
```bash
git clone ...
pip install -e "."  
```

## Adding a cluster
Before you can schedule a job, you will need to add a cluster by specifying a configuration.

You can specify a configuration by adding it to `~/slurmpilot/config/clusters/YOUR_CLUSTER.yaml`, for instance a configuration could 
be like this:
```yaml
host: your-gpu-cluster.com
# optional, specify the path where files will be written by slurmpilot on the remote machine, default to ~/slurmpilot
remote_path: "/home/username2/foo/slurmpilot/"
# optional, only specify if the user on the cluster is different than on your local machine
user: username2  
# optional, specify a slurm account if needed
account: "AN_ACCOUNT"  
```

## Scheduling a job
TODO Add Hellocluster example in main repo.

### Workflow
When scheduling a job, the files required to run it are first copied to `~/slurmpilot/jobs/YOUR_JOB_NAME` and then
send to the remote host to `~/slurmpilot/jobs/YOUR_JOB_NAME` (those defaults paths are modifiable).

In particular, the following files are generated locally under `~/slurmpilot/jobs/YOUR_JOB_NAME`:
* `metadata.json: contains metadata such as time and the configuration of the job that was scheduled
* jobid.json: contains the slurm jobid obtained when scheduling the job, if this step was successful
* slurm_script.sh: a slurm script automatically generated from your options that is executed on the remote node with sbatch
* src_dir: the folder containing the entrypoint
* ${src_dir}/entrypoint: the entrypoint to be executed

On the remote host, the logs are written under `logs/stderr` and `logs/stdout` and the current working dir is also 
`~/slurmpilot/jobs/YOUR_JOB_NAME` unless overwritten in `general.yaml` config (see `Other ways to specify configurations` section).

## FAQ/misc

*Developer setup.*
If you want to develop features, run the following:
```bash
pip install -e ".[dev]"  # TODO update with github
```

*Other ways to specify configurations.*
You can also specify configurations in `SLURMPILOT_SRC_DIR/config` where SLURMPILOT_SRC_DIR would replace
where the source code of slurmpilot is installed.
In case multiple configurations can be defined, the configurations in `~/slurmpilot` will override the one defined 
in `SLURMPILOT_SRC_DIR`.

You can also specify global properties by writing `~/slurmpilot/general.yaml` (or `SLURMPILOT_SRC_DIR/general.yaml`)
and edit the following:
```
# where files are written locally on your machine for job status, logs and artifacts
local_path: "~/slurmpilot"  

# default path where slurmpilot job files are generated on the remote machine, Note: "~" cannot be used
remote_path: "slurmpilot/"
```

**TODOs**
* high: handle python dependencies
* high: explain examples in readme
* high: add unit test actions
* high: sp --sync job-name  / sync artefact of a job
* medium: allow to copy only python files (or as skypilot keep only files .gitignore)
* medium: dont make ssh connection to every cluster in cli, requires small refactor to avoid needing SlurmWrapper to get last jobname
* medium: make script execution independent of cwd and dump variable to enforce reproducibility
* medium: allow to pass variable to remote scripts, right now only env variable can be used
* medium/low: subfolders
* medium: stop all jobs
* low: remove logging info ssh
* low: allow to share common folders to avoid sending code lots of times, probably do a doc example
* TBD: chain of jobs
* allow to submit list of jobs until all executed

**DONE**
* high: add example in main repo
* medium: add option to stop in the CLI 
* high: push in github 
* high: allow to fetch info from local folders in list_jobs
* when creating job, show command that can be copy-pasted to display log, status, sync artifact
* support setting local configs path via local files
* test "jobs/" new folder structure
* tool to display logs/status from terminal
* make sp installed in pip (add it to setup)
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


## North star / ideas
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
* support diff experiment folders
* support numerating suffix "-1", "-2" instead of random names
