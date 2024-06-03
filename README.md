## Dev setup

```
pip install -e ".[dev]"  # TODO update with github
pre-commit install 
pre-commit autoupdate
```

## Scheduling a job

### Adding a cluster
First, you will need to add a cluster by specifying a configuration.

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

Alternatively, you can specify configurations in `SLURMPILOT_SRC_DIR/config` where SLURMPILOT_SRC_DIR would replace
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

### Workflow
When scheduling a job, the files required to run it are first copied to `~/slurmpilot/your_job_name` and then
send to the remote host to `~/slurmpilot/your_job_name` (those defaults paths are modifiable).

In particular, the following files are generated locally under `~/slurmpilot/your_job_name`:
* metadata.json: contains metadata such as time and the configuration of the job that was scheduled
* jobid.json: contains the slurm jobid obtained when scheduling the job, if this step was successful
* slurm_script.sh: a slurm script automatically generated from your options that is executed on the remote node with sbatch
* src_dir: the folder containing the entrypoint
* src_dir/entrypoint: the entrypoint to be executed

On the remote host, the logs are written under `logs/stderr` and `logs/stdout` and the current working dir is `~/slurmpilot/your_job_name`.

### Job file structure




**TODOs**
* test "jobs/" new folder structure
* make script execution independent of cwd and dump variable to enforce reproducibility
* allow to pass variable to remote scripts
* sp --sync job-name  / sync artefact of a job
* when creating job, show command that can be copy-pasted to display log, status, sync artifact
* remove logging info ssh
* add interface for log querying and other functionalities
* subfolders
* support setting local configs path via environment variables
* stop all jobs
* allow to share common folders to avoid sending code lots of times
* lazy load connections of clusters
* chain of jobs

**DONE**
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
