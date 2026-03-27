<h1 align="center">Slurmpilot 🚀</h1>

<p align="center">
  <strong>Effortlessly launch experiments on Slurm clusters from your local machine.</strong>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python version">
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

Clone and install in editable mode:

```bash
git clone https://github.com/geoalgo/slurmpilot.git
cd slurmpilot
pip install -e .
```

### 2. Configure Your First Cluster

In case you want to schedule job from your machine, you need to first configure ssh by
creating a cluster config file at `~/slurmpilot/config/clusters/YOUR_CLUSTER.yaml`:

```yaml
host: your-cluster-hostname
user: your-username          # optional, defaults to current user
remote_path: ~/slurmpilot    # optional, where files are stored on the cluster
default_partition: gpu       # optional, used when partition is not specified
account: your-account        # optional, Slurm account to charge
```

Optionally create `~/slurmpilot/config/general.yaml` for global settings:

```yaml
local_path: ~/slurmpilot        # where job files are stored locally
default_cluster: YOUR_CLUSTER   # used when cluster is not specified
```

Verify your SSH connection:

```bash
sp test-ssh YOUR_CLUSTER
```

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

where `YOURCLUSTER` should be reachable with `sp test-ssh YOUR_CLUSTER`.

### Local mode

Alternatively, you can use `cluster="local"` if you are running Slurmpilot directly from a Slurm login node:

```python
slurm = SlurmPilot(clusters=["local"])

job_info = JobCreationInfo(
    cluster="local",
    partition="gpu",
    jobname=unify("my-job", method="date"),
    entrypoint="train.py",
    python_binary="python",
    n_cpus=4,
    n_gpus=1,
)

job_id = slurm.schedule_job(job_info)
```

Job files are still written to `~/slurmpilot/jobs/` locally; no SSH connection is opened.

 

### Schedule a Python Script

```python
job_info = JobCreationInfo(
    cluster="YOURCLUSTER",
    partition="YOURPARTITION",
    jobname=unify("python-job", method="date"),
    entrypoint="main.py",
    python_binary="~/miniconda3/bin/python",
    python_args="--data /path/to/data --epochs 10",
    n_cpus=2,
    n_gpus=1,
    mem=16000,
    env={"API_TOKEN": "your-token"},
)

job_id = slurm.schedule_job(job_info)
```

`bash_setup_command` lets you run commands before the entrypoint (e.g. activate conda, start a server):

```python
job_info = JobCreationInfo(
    ...
    bash_setup_command="source ~/miniconda3/etc/profile.d/conda.sh && conda activate myenv",
)
```

### Job Arrays

Pass a **list** to `python_args` to submit a job array — one task per element:

```python
job_info = JobCreationInfo(
    ...
    python_args=[
        {"lr": 0.001, "batch": 32},
        {"lr": 0.01,  "batch": 16},
    ],
    n_concurrent_jobs=4,   # optional: limit to 4 running at once
)
```

When calling the entrypoint, each dict is converted to CLI arguments, e.g. `--lr 0.001`,  for the corresponding array task.

### Local Python Libraries

Ship additional local packages alongside your code with `python_libraries`:


```python
job_info = JobCreationInfo(
    ...
    python_libraries=["./mylib"],   # library is copied to the job path and added to PYTHONPATH
)
```

### Mock mode

Use `cluster="mock"` to run jobs as plain local processes — no Slurm installation required. `MockSlurm` intercepts `sbatch`, `sacct`, and `scancel` calls, running the generated bash script as a subprocess and using its PID as the job ID.

This is the recommended mode for **unit tests**:

```python
slurm = SlurmPilot(clusters=["mock"])

job_info = JobCreationInfo(
    cluster="mock",
    jobname="test/my-job",
    entrypoint="run.sh",
    src_dir="./tests/fixtures",
)

job_id = slurm.schedule_job(job_info)
slurm.wait_completion(job_info.jobname, max_seconds=30)
stdout, stderr = slurm.log(job_info.jobname)
```

`sacct` returns `RUNNING` while the process is alive, then `COMPLETED` / `FAILED` / `CANCELLED` based on its exit code. No cluster config file is needed.

## ⌨️ Command-Line Interface (CLI)

All job commands accept an optional job name (defaults to the most recently submitted job).

### Job commands

| Command | Description |
|---|---|
| `sp log [JOBNAME]` | Print stdout/stderr of a job |
| `sp status [JOBNAME]` | Print current Slurm state of a job |
| `sp metadata [JOBNAME]` | Print job metadata (cluster, date, …) |
| `sp path [JOBNAME]` | Show local and remote paths for a job |
| `sp slurm-script [JOBNAME]` | Print the generated Slurm script |
| `sp download [JOBNAME]` | Download the job folder from the cluster |
| `sp stop [JOBNAME]` | Cancel a running job |
| `sp queue-status [JOBNAME]` | Show queue position and priority of a pending job |

### Cluster commands

| Command | Description |
|---|---|
| `sp list-jobs [N] [--clusters C …]` | Print a table of the N most recent jobs (default 10) |
| `sp test-ssh CLUSTER …` | Test SSH connection to one or more clusters |
| `sp stop-all [--clusters C …]` | Cancel all tracked jobs on cluster(s) |

`--collapse-job-array` on `list-jobs` shows one row per job array instead of one per task.

`sp queue-status` runs two `squeue` calls on the remote cluster and reports the job's priority score, its rank among all `PENDING` jobs in the same partition, and the top priority score in that partition:

```
job       : my-experiment (id: 17026264)
partition : small-g
priority  : 5000  (top is 9999)
position  : 3 / 42 pending jobs
```

Returns a "not pending" message when the job has already started running or completed.

### Launch command

`sp launch` builds and submits a job from a YAML config file and/or inline CLI flags. CLI flags always override YAML values.

```bash
# Inline flags only
sp launch --entrypoint main.py --cluster mycluster --partition gpu --n-gpus 1

# From a YAML config (src_dir defaults to the YAML file's directory)
sp launch --config job.yaml

# YAML with a one-off override
sp launch --config job.yaml --cluster local --partition debug

# Preview the generated sbatch script without submitting
sp launch --config job.yaml --dry-run

# Submit and block until the job finishes, then print logs
sp launch --config job.yaml --wait
sp launch --config job.yaml --wait --max-wait-seconds 3600
```

A minimal `job.yaml`:

```yaml
cluster: mycluster
partition: gpu
entrypoint: train.py          # relative to the YAML file's directory

python_binary: python
python_args: "--epochs 10"
n_cpus: 4
n_gpus: 1
max_runtime_minutes: 120
```

For a job array, set `python_args` to a list:

```yaml
python_args:
  - lr: 0.001
    batch: 32
  - lr: 0.01
    batch: 16
```

`jobname` is auto-generated from the entrypoint stem via coolname if not provided (e.g. `train-charming-swift-otter-of-justice`).

Example output from `sp list-jobs 5`:

```
job                                          jobid   cluster  creation             min    status      nodelist
-------------------------------------------  ------  -------  -------------------  -----  ----------  --------
job-2026-01-01                               42      mock     2026-01-01 00:00:00  5.0    ✅ COMPLETED  node01
python-job-2026-01-01-12-00-00               43      gpu-c    2026-01-01 12:00:00  12.3   🏃 RUNNING    gpu01
```

## ⚙️ Configuration

### Config directory layout

```
~/slurmpilot/config/
  general.yaml            # optional global settings
  clusters/
    YOUR_CLUSTER.yaml     # one file per cluster
```

### `general.yaml`

```yaml
local_path: ~/slurmpilot      # where job files are stored locally
default_cluster: YOUR_CLUSTER
```

### `clusters/YOUR_CLUSTER.yaml`

```yaml
host: hostname-or-ip
user: your-username           # optional
remote_path: ~/slurmpilot     # optional
default_partition: gpu        # optional
account: slurm-account        # optional
```

## 🙌 Contributing

Contributions are welcome! If you have ideas for improvements or find a bug, please open an issue or submit a pull request.

To set up a development environment:

```bash
git clone https://github.com/geoalgo/slurmpilot.git
cd slurmpilot
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check slurmpilot tst
```

## FAQ

**How does it work?**

When scheduling a job, the files required to run it are copied to `~/slurmpilot/jobs/YOUR_JOB_NAME` locally, then synced to the remote cluster. The following files are generated:

* `slurm_script.sh` — sbatch script generated from your `JobCreationInfo`
* `metadata.json` — job metadata (cluster, date, config)
* `jobid.json` — Slurm job ID after successful submission
* `src/` — copy of your source files
* `logs/stdout`, `logs/stderr` — job output (populated after the job runs)

The working directory on the remote node is `~/slurmpilot/jobs/YOUR_JOB_NAME`.

**Why SSH and not a cluster login node?**

A typical workflow involves SSHing to a login node and calling sbatch there. Slurmpilot automates this so you can manage multiple clusters without ever leaving your local machine.

**Why not Docker?**

Docker is great for cloud tools (SkyPilot, SageMaker…) but is often unavailable on Slurm clusters due to root-privilege requirements. Slurmpilot sends source files directly, which is simpler and more portable.

**What are the dependencies?**

Only `pyyaml` is required at runtime. No pandas, no numpy.

```
slurmpilot
└── pyyaml
```

**What about other tools?**

[SkyPilot](https://github.com/skypilot-org/skypilot) is excellent for cloud providers. [Submitit](https://github.com/facebookincubator/submitit) is great for single-cluster Python-native workflows. Slurmpilot targets the multi-cluster academic use case: sending raw source files, no serialization, CLI-first management across clusters.
