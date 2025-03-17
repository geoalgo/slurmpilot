# Slurmpilot

Slurmpilot is a python library to launch experiments in Slurm on any cluster from the comfort of your local machine.
The library aims to take care of things such as sending remote code for execution, calling slurm,
finding good places to write logs and accessing status from your jobs.

The key features are:

* simplify job creation, improve reproducibility and allow launching slurm jobs from your machine
* allows to easily list experiments, logs or show status and stop jobs
* easy switch between cluster by just providing different config files

Essentially we want to make it much easier and faster for user to run experiments on Slurm and reach the quality of
cloud usage.

**Important note:** Right now, the library is very much work in progress and the API has not been frozen yet. If you use it, please consider providing your feedback!  

See this [link](notes/features.md)  for a table of features supported.

**What about other tools?**

If you are familiar with tools, you may know the great [Skypilot](https://github.com/skypilot-org/skypilot) which allows
to run experiments seamlessly between different cloud providers.
The goal of this project is to ultimately provide a similar high-quality user experience for academics who are running
on slurm and not cloud machines.
Extending skypilot to support seems hard given the different nature of slurm and cloud (for instance not all slurm
cluster could run docker) and hence this library was made rather than just contributing to skypilot.
This library is also influenced by [Sagemaker python API](https://sagemaker.readthedocs.io/en/stable/) and you may find
some similarities.

On the Slurm world, a similar library is [Submit](https://github.com/facebookincubator/submitit).
Compared to Submit, we support launching on any cluster from your local machine and also aim
at having more features for easy experimenting such as sending source files, or CLI job 
launching and access to logs or job information. We also deliberately avoid serialization and rather send source files
which can avoid issues such as [import problems](https://github.com/facebookincubator/submitit/blob/main/docs/tips.md)
requiring to structure your code in a specific way. 

## Installing

To install, run the following:

```bash
pip install "slurmpilot[extra] @ git+https://github.com/geoalgo/slurmpilot.git"
```

## Adding a cluster

Before you can schedule a job, you will need to provide information about a cluster by specifying a configuration.

You can run the following command:

```bash 
sp-add-cluster --cluster YOUR_CLUSTER --host YOUR_HOST --user YOUR_USER --check-ssh-connection
```

you can also configure the ssh key to use, whether to keep the ssh connection alive, see `sp-add-cluster --help`
to get the full list of options.

After adding those information, if you passed `--check-ssh-connection`a ssh connection will be made with the provided
information to check if the connection can be made. 

You can also directly create/edit the cluster configuration at
`~/slurmpilot/config/clusters/YOUR_CLUSTER.yaml`, see FAQ on editing configurations for more details.

## Scheduling a job

You are now ready to schedule jobs. Let us have a look at `launch_hellocluster.py`, in particular, you can call the
following to schedule a job:

```python
from slurmpilot import SlurmPilot, JobCreationInfo, unify

cluster = "YOURCLUSTER"
partition = "YOURPARTITION"
slurm = SlurmPilot(clusters=[cluster])

jobinfo = JobCreationInfo(
    cluster=cluster,
    partition=partition,
    jobname=unify("examples/hello-cluster", method="coolname"),  # gets a unique jobname by appending a coolname
    entrypoint="hellocluster_script.sh",
    src_dir="./",
    n_cpus=1,
    max_runtime_minutes=60,    
)
jobid = slurm.schedule_job(jobinfo)
```

Here we created a job in the default cluster and partition. A couple of points:

* `cluster`: you can use any cluster `YOURCLUSTER` as long as the file `~/slurmpilot/config/clusters/YOUR_CLUSTER.yaml`
exists, that the hostname is reachable through ssh and that Slurm is installed on the host. 
* `jobname` must be unique, we use `unify` which appends a unique suffix to ensure unicity even if the scripts is
  launched multiple times. Nested folders can be used, in this case, files will be written under `~
  /slurmpilot/jobs/examples/hello-cluster/`
* `entrypoint` is the script we want to launched and should be present in `{src_dir}/{entrypoint}`
* `n_cpus` is the number of CPUs, we can control other slurm arguments such as number of GPUs, number of nodes etc
* `env` allows to pass environment variable to the script that is being remotely executed

### Workflow

When scheduling a job, the files required to run it are first copied to `~/slurmpilot/jobs/YOUR_JOB_NAME` and then
sent to the remote host to `~/slurmpilot/jobs/YOUR_JOB_NAME`.

In particular, the following files are generated locally under `~/slurmpilot/jobs/YOUR_JOB_NAME`:

* `slurm_script.sh`: a slurm script automatically generated from your options that is executed on the remote node with
  sbatch
* `metadata.json`: contains metadata such as time and the configuration of the job that was scheduled
* `jobid.json`: contains the slurm jobid obtained when scheduling the job, if this step was successful
* `src_dir`: the folder containing the entrypoint
* `{src_dir}/entrypoint`: the entrypoint to be executed

On the remote host, the logs are written under `logs/stderr` and `logs/stdout` and the current working dir is also
`~/slurmpilot/jobs/YOUR_JOB_NAME` unless overwritten in `general.yaml` config (
see `Other ways to specify configurations` section).

### Scheduling python jobs

If you want to schedule directly a Python job, you can also do:

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

If you pass a **list of arguments**, SlurmPilot will create a job-array with one job per argument.

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

To see the utilisation you made of a cluster, run:

```sp-usage --cluster YOUR_CLUSTER```
which will show an output like this one:

```
Total number of jobs submitted: 1187.
Total number of hours (only GPU): 841.77

Number of GPU hours per type of configuration
NNodes  n-gpu
1       1        134.951389
        2          1.022222
        4        705.794444
```

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

```yaml
# default path where slurmpilot job files are generated
local_path: "~/slurmpilot"

# default path where slurmpilot job files are generated on the remote machine, Note: "~" cannot be used
remote_path: "slurmpilot/"

# optional, cluster that is being used by default
default_cluster: "YOUR_CLUSTER"
```


**Cluster configuration(s).**

You can create/edit a cluster configuration directly in `~/slurmpilot/config/clusters/YOUR_CLUSTER.yaml`,
for instance a configuration could be like this:

```yaml
# connecting to this host via ssh should work as Slurmpilot relies on ssh
host: name
# optional, specify the path where files will be written by slurmpilot on the remote machine, default to ~/slurmpilot
remote_path: "/home/username2/foo/slurmpilot/"
# optional, specify a slurm account if needed (passed with --acount to slurm)
account: "AN_ACCOUNT"
# optional, allow to avoid the need to specify the partition
default_partition: "NAME_OF_PARTITION_TO_BE_USED_BY_DEFAULT"
# optional (default to false), whether you should be prompted to use a login password for ssh
```

**Why do you rely on SSH?**
A typical workflow for Slurm user is to send their code to a remote machine and call sbatch there. We rather
work with ssh from a machine (typically the developer) machine because we want to be able to switch to several cluster
without hassle.

**Why don't you rely on docker?**
Docker is a great option and is being used in similar tools built for the cloud such as Skypilot, SageMaker, ...
However, running docker in Slurm is often not an option due to difficulties to run without root privileges.