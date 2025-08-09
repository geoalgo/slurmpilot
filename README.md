<h1 align="center">Slurmpilot 🚀</h1>

<p align="center">
  <strong>Effortlessly launch experiments on Slurm clusters from your local machine.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/slurmpilot/"><img src="https://badge.fury.io/py/slurmpilot.svg" alt="PyPI version"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/geoalgo/slurmpilot/actions/workflows/run-pytest.yml"><img src="https://github.com/geoalgo/slurmpilot/actions/workflows/run-pytest.yml/badge.svg" alt="Pytest"></a>
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python version">
</p>

---

**Slurmpilot** is a Python library designed to simplify launching experiments on Slurm clusters directly from your local machine. It automates code synchronization, job submission, and status tracking, letting you focus on your research.

## 🤔 Why Slurmpilot?

While tools like [SkyPilot](https://github.com/skypilot-org/skypilot) and [Submitit](https://github.com/facebookincubator/submitit) are excellent, Slurmpilot offers a more flexible, multi-cluster experience tailored for academic research environments where Docker might not be available. We focus on sending source files directly, avoiding serialization issues and providing a seamless CLI for managing your experiments.

## ✨ Core Features

*   **💻 Remote Job Submission:** Launch Slurm jobs on any cluster with SSH access from your local machine.
*   **🔁 Simplified Workflow:** Automatically handles code synchronization, log management, and job status tracking.
*   **🌐 Multi-Cluster Support:** Easily switch between different Slurm clusters.
*   **📝 Reproducibility:** Keep track of your experiments with automatically generated metadata.
*   **⌨️ Command-Line Interface (CLI):** Manage jobs, view logs, and check status with simple commands.

## 🚀 Getting Started

### 1. Installation

Install Slurmpilot from PyPI:

```bash
pip install slurmpilot
```

Or, for the latest version from GitHub:

```bash
pip install "slurmpilot[extra] @ git+https://github.com/geoalgo/slurmpilot.git"
```

### 2. Configure Your First Cluster

Set up a cluster interactively:

```bash
sp-add-cluster --cluster YOUR_CLUSTER --host YOUR_HOST --user YOUR_USER --check-ssh-connection
```

This command creates a configuration file at `~/slurmpilot/config/clusters/YOUR_CLUSTER.yaml` and verifies the SSH connection.

## 💡 Usage Examples

### Schedule a Shell Script

```python
from slurmpilot import SlurmPilot, JobCreationInfo, unify

# Initialize SlurmPilot for your cluster
slurm = SlurmPilot(clusters=["YOURCLUSTER"])

# Define the job
job_info = JobCreationInfo(
    cluster="YOURCLUSTER",
    partition="YOURPARTITION",
    jobname=unify("hello-cluster", method="coolname"),
    entrypoint="hellocluster_script.sh",
    src_dir="./",
    n_cpus=1,
    max_runtime_minutes=60,
)

# Launch the job
job_id = slurm.schedule_job(job_info)
print(f"Job {job_id} scheduled on {job_info.cluster}")
```
### Schedule a Python Script

```python
job_info = JobCreationInfo(
    cluster="YOURCLUSTER",
    partition="YOURPARTITION",
    jobname="python-job",
    entrypoint="main.py",
    python_args="--data /path/to/data",
    python_binary="~/miniconda3/bin/python",
    n_cpus=2,
    n_gpus=1,
    env={"API_TOKEN": "your-token"},
)

job_id = slurm.schedule_job(job_info)
```


This will create a sbatch script as in the previous example but this time, it will call directly your python script
with the binary and the arguments provided, you can see the full example
[launch_hellocluster_python.py](examples%2Fhellocluster-python%2Flaunch_hellocluster_python.py).

Note that you can also set `bash_setup_command` which allows to run some command before
calling your python script (for instance to setup the environment, activate conda, setup a server ...).

If you pass a **list of arguments**, SlurmPilot will create a job-array with one job per argument.

## ⌨️ Command-Line Interface (CLI)

Slurmpilot includes a powerful CLI for managing your jobs. Use `sp --help` for a full list of commands.

*   **List jobs:** `sp --list-jobs 5`
*   **Show job status:** `sp --status <JOB_NAME>`
*   **View logs:** `sp --log <JOB_NAME>`
*   **Stop a job:** `sp --stop <JOB_NAME>`
*   **Check cluster usage:** `sp-usage --cluster YOUR_CLUSTER`

Example output from `sp --list-jobs 5`:

```
                                         job           date    cluster                 status                                       full jobname
    v2-loop-judge-option-2024-09-24-16-47-36 24/09/24-16:47   clusterX    Pending ⏳           judge-tuning-v0/v2-loop-judge-option-2024-09-24...
    v2-loop-judge-option-2024-09-24-16-47-30 24/09/24-16:47   clusterX    Pending ⏳           judge-tuning-v0/v2-loop-judge-option-2024-09-24...
job-arboreal-foxhound-of-splendid-domination 24/09/24-12:54   clusterY    Completed ✅         examples/hello-cluster-python/job-arboreal-foxh...
    v2-loop-judge-option-2024-09-23-18-01-36 23/09/24-18:01   clusterX    CANCELLED by 975941  judge-tuning-v0/v2-loop-judge-option-2024-09-23...
    v2-loop-judge-option-2024-09-23-18-00-49 23/09/24-18:00   clusterZ    Slurm job failed ❌  judge-tuning-v0/v2-loop-judge-option-2024-09-23...
```

## ⚙️ Configuration

Customize Slurmpilot's behavior by editing the configuration files in `~/slurmpilot/config/`:

*   **Global settings:** `general.yaml`
*   **Cluster-specific settings:** `clusters/YOUR_CLUSTER.yaml`

You can add a configuration for every cluster which can allow to customize the cluster, eg what is the hostname, how the 
cluster is called, where files are written etc. See FAQ on editing configurations for more details.

## 🙌 Contributing

Contributions are welcome! If you have ideas for improvements or find a bug, please open an issue or submit a pull request on our [GitHub repository](https://github.com/geoalgo/slurmpilot).

To set up a development environment:

```bash
git clone https://github.com/geoalgo/slurmpilot.git
cd slurmpilot
pip install -e ".[dev]"
pre-commit install
```


## FAQ/misc

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

**How does it work?**

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


**Why do you rely on SSH?**
A typical workflow for Slurm user is to send their code to a remote machine and call sbatch there. We rather
work with ssh from a machine (typically the developer) machine because we want to be able to switch to several cluster
without hassle.

**Why don't you rely on docker?**
Docker is a great option and is being used in similar tools built for the cloud such as Skypilot, SageMaker, ...
However, running docker in Slurm is often not an option due to difficulties to run without root privileges.

**What about other tools?** If you are familiar with tools, you may know the great [Skypilot](https://github.com/skypilot-org/skypilot) which allows
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

One frequent approach taken is to use Slurm batch *templates* where environment variables are dynamically filled
(see examples from [Picotron](https://github.com/huggingface/picotron/blob/main/template/base_job.slurm) and [LAION](https://github.com/SLAMPAI/autoexperiment/tree/master/examples/full_example)).
This approach is great and lightweight, but it does not easily allow multi-cluster as SlurmPilot.


**What are the dependencies?**
Current dependencies are pandas and pyyaml to read configs, here is the dependency tree.
We intend to keep dependency to a minimum.
```
slurmpilot v0.1.5.dev0
├── pandas v2.2.3
│   ├── numpy v2.2.4
│   ├── python-dateutil v2.9.0.post0
│   │   └── six v1.17.0
│   ├── pytz v2025.1
│   └── tzdata v2025.1
├── pyyaml v6.0.2
```
