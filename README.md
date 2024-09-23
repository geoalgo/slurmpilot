# Slurmpilot

Slurmpilot is a python library to launch experiments in Slurm from the comfort of your local machine.
The library aims to take care of things such as sending remote code for execution, calling slurm, finding good places to write logs and accessing status from your jobs.

The key features are:
* simplify job creation, improve reproducibility and allow launching slurm jobs from your machine
* allows to easily list experiments, logs or show status and stop jobs 
* easy switch between cluster by just providing different config files

Essentially we want to make it **much** easier and faster for user to run experiments on Slurm and reach the quality of cloud usage.

Important note: Right now, the library is very much work in progress. It is usable (I am using it for all my experiments) but the documentation is yet to be made and API has not been frozen yet.

**What about other tools?**

If you are familiar with tools, you may know the great [Skypilot](https://github.com/skypilot-org/skypilot) which allows to run experiments seamlessly between different cloud providers.
The goal of this project is to ultimately provide a similar high-quality user experience for academics who are running on slurm and not cloud machines.
Extending skypilot to support seems hard given the different nature of slurm and cloud (for instance not all slurm cluster could run docker) and hence this library was made rather than just contributing to skypilot.

This library is also influenced by [Sagemaker python API](https://sagemaker.readthedocs.io/en/stable/) and you may find some similarities. 

## Installing

To install, run the following:
```bash
pip install "slurmpilot[extra] @ git+https://github.com/geoalgo/slurmpilot.git"
```

## Adding a cluster
Before you can schedule a job, you will need to provide information about a cluster by specifying a configuration.

You can run the following command:
```bash 
slurmpilot --add-cluster
```
which will ask you for the name of the cluster, the hostname, your username etc. After adding those information, a ssh
connection will be made with the provided information to check if the connection can be made.

Alternatively, you can specify/edit configuration directly in `~/slurmpilot/config/clusters/YOUR_CLUSTER.yaml`, 
for instance a configuration could be like this:
```yaml
# connecting to this host via ssh should work as Slurmpilot relies on ssh
host: your-gpu-cluster.com
# optional, specify the path where files will be written by slurmpilot on the remote machine, default to ~/slurmpilot
remote_path: "/home/username2/foo/slurmpilot/"
# optional, only specify if the user on the cluster is different than on your local machine
user: username2  
# optional, specify a slurm account if needed
account: "AN_ACCOUNT"  
# optional, allow to avoid the need to specify the partition
default_partition: "NAME_OF_PARTITION_TO_BE_USED_BY_DEFAULT"
```

In addition, you can configure `~/slurmpilot/config/general.yaml` with the following:

```yaml
# default path where slurmpilot job files are generated
local_path: "~/slurmpilot"

# default path where slurmpilot job files are generated on the remote machine, Note: "~" cannot be used
remote_path: "slurmpilot/"

# optional, cluster that is being used by default
default_cluster: "YOUR_CLUSTER"
```

## Scheduling a job
You are now ready to schedule jobs! Let us have a look at `launch_hellocluster.py`, in particular, you can call the following to schedule a job:

```python
config = load_config()
cluster, partition = default_cluster_and_partition()
jobname = unify("examples/hello-cluster", method="coolname")  # make the jobname unique by appending a coolname
slurm = SlurmWrapper(config=config, clusters=[cluster])
max_runtime_minutes = 60
jobinfo = JobCreationInfo(
    cluster=cluster,
    partition=partition,
    jobname=jobname,
    entrypoint="hellocluster_script.sh",
    src_dir="./",
    n_cpus=1,
    max_runtime_minutes=max_runtime_minutes,
    # Shows how to pass an environment variable to the running script
    env={"API_TOKEN": "DUMMY"},
)
jobid = slurm.schedule_job(jobinfo)
```

Here we created a job in the default cluster and partition. A couple of points:
* `cluster`: you can use any cluster `YOURCLUSTER` as long as the file `config/clusters/YOURCLUSTER.yaml` exists, that the hostname is reachable through ssh and that Slurm is installed on the host.
* `jobname` must be unique, we use `unify` which appends a unique suffix to ensure unicity even if the scripts is launched multiple times. Nested folders can be used, in this case, files will be written under "~/slurmpilot/jobs/examples/hello-cluster..."
* `entrypoint` is the script we want to launched and should be present in `{src_dir}/{entrypoint}`
* `n_cpus` is the number of CPUs, we can control other slurm arguments such as number of GPUs, number of nodes etc
* `env` allows to pass environment variable to the script that is being remotely executed

### Workflow
When scheduling a job, the files required to run it are first copied to `~/slurmpilot/jobs/YOUR_JOB_NAME` and then
sent to the remote host to `~/slurmpilot/jobs/YOUR_JOB_NAME` (those defaults paths are modifiable).

In particular, the following files are generated locally under `~/slurmpilot/jobs/YOUR_JOB_NAME`:
* `metadata.json`: contains metadata such as time and the configuration of the job that was scheduled
* `jobid.json`: contains the slurm jobid obtained when scheduling the job, if this step was successful
* `slurm_script.sh`: a slurm script automatically generated from your options that is executed on the remote node with sbatch
* `src_dir`: the folder containing the entrypoint
* `{src_dir}/entrypoint`: the entrypoint to be executed

On the remote host, the logs are written under `logs/stderr` and `logs/stdout` and the current working dir is also 
`~/slurmpilot/jobs/YOUR_JOB_NAME` unless overwritten in `general.yaml` config (see `Other ways to specify configurations` section).

## FAQ/misc

*Developer setup.*
If you want to develop features, run the following:
```bash
git clone https://github.com/geoalgo/slurmpilot.git
cd slurmpilot
pip install -e ".[dev]" 
```

*Global configuration.*

You can specify global properties by writing `~/slurmpilot/config/general.yaml`
and edit the following:
```
# where files are written locally on your machine for job status, logs and artifacts
local_path: "~/slurmpilot"  

# default path where slurmpilot job files are generated on the remote machine, Note: "~" cannot be used
remote_path: "slurmpilot/"
```

**TODOs**
* high: explain examples in readme
* high: add unit test actions
* medium: suppress connection print output of fabrik (happens at connection, not when running commands)
* medium: discuss getting out of your way philosophy of the tool
* medium: make script execution independent of cwd and dump variable to enforce reproducibility
* medium: support local execution, see `notes/running_locally.md`
* medium: allow to copy only python files (or as skypilot keep only files .gitignore)
* medium: generates animation of demo in readme.md
* medium: allow to stop all jobs in CLI
* medium: allow to submit list of jobs until all executed
* medium: support numerating suffix "-1", "-2" instead of random names
* medium: rename SlurmWrapper to SlurmPilot
* low: doc for handling python dependencies
* low: remove logging info ssh
* low: allow to share common folders to avoid sending code lots of times, probably do a doc example
* TBD: chain of jobs

**DONE**
* high: support python wrapper
* medium/high: list jobs
* high: support subfolders for experiment files
* medium: add support to add cluster from CLI
* medium/high: script to install cluster (ask username, hostname etc)
* high: support defining cluster as env variable, would allow to run example and make it easier to explain examples in README.md
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
