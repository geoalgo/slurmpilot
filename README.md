# Slurmpilot

Slurmpilot is a python library to launch experiments in Slurm from the confort of your local machine.
The library aims to take care of things such as sending remote code for execution, calling slurm, finding good places to write logs and accessing status from your jobs.

The key features are:
* simplify job creation, improve reproducibility and allow launching slurm jobs from your machine
* allows to easily list experiments, logs or show status and stop jobs 
* easy switch between cluster by just providing different config files

Essentially we want to make it **much** easier and faster for user to run experiments on Slurm and reach the quality of cloud usage.

Important note: Right now, the library is very much work in progress. It is usable (I am using it for all my experiments) but the documentation is yet to be made and API has not been frozen yet.

**What about other tools?**

If you are familiar with tools, you may know the great [Skypilot](https://github.com/skypilot-org/skypilot) which allows to run experiments seamlessly between different cloud providers.
The goal of this project is to ultimately provide a similar high-quality user experience for academic who are running on slurm and not cloud machines.
Extending skypilot to support seems hard given the different nature of slurm and cloud (for instance not all slurm cluster could run docker) and hence this library was made rather than just contributing to skypilot.

This library is also influenced by [Sagemaker python API](https://sagemaker.readthedocs.io/en/stable/) and you may find some similarities. 

## Installing

To install, run the following:
```bash
git clone https://github.com/geoalgo/slurmpilot.git
pip install -e "."  
```

## Adding a cluster
Before you can schedule a job, you will need to add a cluster by specifying a configuration.

You can specify a configuration by adding it to `~/slurmpilot/config/clusters/YOUR_CLUSTER.yaml`, for instance a configuration could 
be like this:
```yaml
host: your-gpu-cluster.com
# optional, specify the path where files will be written by slurmpilot on the remote machine, default to ~/slurmpilot
remote_path: "/home/YOURCLUSTERUSERNAME/foo/slurmpilot/"
# optional, only specify if the user on the cluster is different than on your local machine
user: YOURCLUSTERUSERNAME  
# optional, specify a slurm account if needed
account: "AN_ACCOUNT"  
```

## Scheduling a job
TODO Add Hellocluster example in main repo.


## FAQ/misc

**What happens when I schedule a job on my local machine?**
When scheduling a job, the files required to run it are first copied to `~/slurmpilot/jobs/YOUR_JOB_NAME` and then
sent to the remote host to `~/slurmpilot/jobs/YOUR_JOB_NAME` (those defaults paths are modifiable) then Slurm is called to start your job.

In particular, the following files are generated locally under `~/slurmpilot/jobs/YOUR_JOB_NAME`:
* `metadata.json: contains metadata such as time and the configuration of the job that was scheduled
* jobid.json: contains the slurm jobid obtained when scheduling the job, if this step was successful
* slurm_script.sh: a slurm script automatically generated from your options that is executed on the remote node with sbatch
* src_dir: the folder containing the entrypoint
* ${src_dir}/entrypoint: the entrypoint to be executed

On the remote host, the logs are written under `logs/stderr` and `logs/stdout` and the current working dir is also 
`~/slurmpilot/jobs/YOUR_JOB_NAME` unless overwritten in `general.yaml` config (see `Other ways to specify configurations` section).


**Developer setup.**
If you want to develop features, run the following:
```bash
pip install -e ".[dev]"  # TODO update with github
```

**Other ways to specify configurations.**
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
* high: support defining cluster as env variable, would allow to run example and make it easier to explain examples in README.md
* high: explain examples in readme
* high: add unit test actions
* high: sp --sync job-name  / sync artefact of a job
* high: support subfolders for experiment files
* medium: support local execution, see `notes/running_locally.md`
* medium: generates animation of demo in readme.md
* medium: allow to copy only python files (or as skypilot keep only files .gitignore)
* medium: make script execution independent of cwd and dump variable to enforce reproducibility
* medium: allow to pass variable to remote scripts, right now only env variable can be used
* medium: allow to stop all jobs in CLI
* medium: allow to submit list of jobs until all executed
* medium: support numerating suffix "-1", "-2" instead of random names
* low: doc for handling python dependencies
* low: remove logging info ssh
* low: allow to share common folders to avoid sending code lots of times, probably do a doc example
* TBD: chain of jobs

**DONE**
* medium: dont make ssh connection to every cluster in cli, requires small refactor to avoid needing SlurmWrapper to get last jobname
* high: handle python code dependencies
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
