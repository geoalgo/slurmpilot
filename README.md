# Slurmpilot

Slurmpilot is a python library to launch experiments in Slurm on any cluster from the comfort of your local machine.
The library aims to take care of things such as sending remote code for execution, calling slurm, 
finding good places to write logs and accessing status from your jobs.

The key features are:
* simplify job creation, improve reproducibility and allow launching slurm jobs from your machine
* allows to easily list experiments, logs or show status and stop jobs 
* easy switch between cluster by just providing different config files

Essentially we want to make it much easier and faster for user to run experiments on Slurm and reach the quality of cloud usage.

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
* `slurm_script.sh`: a slurm script automatically generated from your options that is executed on the remote node with sbatch
* `metadata.json`: contains metadata such as time and the configuration of the job that was scheduled
* `jobid.json`: contains the slurm jobid obtained when scheduling the job, if this step was successful
* `src_dir`: the folder containing the entrypoint
* `{src_dir}/entrypoint`: the entrypoint to be executed

On the remote host, the logs are written under `logs/stderr` and `logs/stdout` and the current working dir is also 
`~/slurmpilot/jobs/YOUR_JOB_NAME` unless overwritten in `general.yaml` config (see `Other ways to specify configurations` section).


### Scheduling python jobs

If you want to schedule directly a Python jobs, you can also do:

```python
jobinfo = JobCreationInfo(
    cluster=cluster,
    partition=partition,
    jobname=jobname,
    entrypoint="main_hello_cluster.py",
    python_args="--argument1 dummy",
    python_binary="~/miniconda3/bin/python",
    n_cpus=1,
    max_runtime_minutes=60,
    # Shows how to pass an environment variable to the running script
    env={"API_TOKEN": "DUMMY"},
)
jobid = slurm.schedule_job(jobinfo)
```

This will create a sbatch script as in the previous example but this time, it will call directly your python script
with the binary and the arguments provided, you can see the full example
[launch_hellocluster_python.py](examples%2Fhellocluster-python%2Flaunch_hellocluster_python.py). 
Note that you can also set `bash_setup_command` which allows to run some command before 
calling your python script (for instance to setup the environment, activate conda, setup a server ...).

### CLI

Slurmpilot provides a CLI which allows to:
* display log of a job
* list information about a list of jobs in a table
* stop a job
* download the artifact of a job locally
* show the status of a particular job
* add a cluster
* test ssh connection of the list of configured clusters

After installing slurmpilot, you can run the following to get help on how to use those commands.

```bash
sp --help
```
For instance, running `sp --list-jobs 5` will display informations of the past 5 jobs as follows:
```
                                         job           date    cluster                 status                                       full jobname
    v2-loop-judge-option-2024-09-24-16-47-36 24/09/24-16:47   clusterX    Pending ⏳           judge-tuning-v0/v2-loop-judge-option-2024-09-24...
    v2-loop-judge-option-2024-09-24-16-47-30 24/09/24-16:47   clusterX    Pending ⏳           judge-tuning-v0/v2-loop-judge-option-2024-09-24...
job-arboreal-foxhound-of-splendid-domination 24/09/24-12:54   clusterY    Completed ✅         examples/hello-cluster-python/job-arboreal-foxh...
    v2-loop-judge-option-2024-09-23-18-01-36 23/09/24-18:01   clusterX    CANCELLED by 975941  judge-tuning-v0/v2-loop-judge-option-2024-09-23...
    v2-loop-judge-option-2024-09-23-18-00-49 23/09/24-18:00   clusterZ    Slurm job failed ❌  judge-tuning-v0/v2-loop-judge-option-2024-09-23...
```

Note that listing jobs requires the ssh connection to work with every cluster since Slurm will be queried to know the
current status, if cluster is unavailable because the ssh credentials expired for instance then a place holder status 
will be shown.


## FAQ/misc

**Developer setup.**
If you want to develop features, run the following:
```bash
git clone https://github.com/geoalgo/slurmpilot.git
cd slurmpilot
pip install -e ".[dev]"
pre-commit install 
pre-commit autoupdate 
```

**Global configuration.**
You can specify global properties by writing `~/slurmpilot/config/general.yaml`
and edit the following:
```
# where files are written locally on your machine for job status, logs and artifacts
local_path: "~/slurmpilot"  

# default path where slurmpilot job files are generated on the remote machine, Note: "~" cannot be used
remote_path: "slurmpilot/"
```

**Why do you rely on SSH?**
A typical workflow for Slurm user is to send their code to a remote machine and call sbatch there. We rather
work with ssh from a machine (typically the developer) machine because we want to be able to switch to several cluster
without hassle.

**Why don't you rely on docker?** 
Docker is a great option and is being used in similar tools built for the cloud such as Skypilot, SageMaker, ...
However, running docker in Slurm is often not an option due to difficulties to run without root privileges.

**TODOs**
* high: explain examples in readme
* high: better support to launch series of experiments
* medium: suppress connection print output of fabrik (happens at connection, not when running commands)
* medium: discuss getting out of your way philosophy of the tool
* medium: make script execution independent of cwd and dump variable to enforce reproducibility
* medium: support local execution, see `notes/running_locally.md`
* medium: allow to copy only python files (or as skypilot keep only files .gitignore)
* medium: generates animation of demo in readme.md
* medium: allow to stop all jobs in CLI
* medium: allow to submit list of jobs until all executed
* medium: rename SlurmWrapper to SlurmPilot
* medium: rerun/restart job (useful in case of transient error)
* medium: download in batch
* low: support numerating suffix "-1", "-2" instead of random names
* low: doc for handling python dependencies
* low: remove logging info ssh
* low: allow to share common folders to avoid sending code lots of times, probably do a doc example
* TBD: chain of jobs

**DONE**
* high: add description of CLI in readme.md
* high: add unit test actions
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


