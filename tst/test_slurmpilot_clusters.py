"""Tests for SlurmPilot with local and SSH clusters.

SSH tests use a FakeConnection injected into slurm._connections so no real
SSH session or Slurm installation is required.

Local-cluster tests mock subprocess so they also run without Slurm installed.
"""
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config import ClusterConfig, Config
from job_creation_info import JobCreationInfo
from remote_command import CommandResult, RemoteExecution
from slurmpilot import SlurmPilot

# ---------------------------------------------------------------------------
# Helpers shared across all cluster types
# ---------------------------------------------------------------------------

def make_config(tmp_path: Path, cluster_configs: dict | None = None) -> Config:
    return Config(local_path=tmp_path, cluster_configs=cluster_configs or {})


def make_bash_src(directory: Path, body: str = "echo hello") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "main.sh").write_text(f"#!/bin/bash\n{body}\n")
    return directory


def bash_job(tmp_path: Path, cluster: str, name: str = "job", body: str = "echo hello") -> JobCreationInfo:
    src = make_bash_src(tmp_path / "src", body=body)
    return JobCreationInfo(jobname=name, entrypoint="main.sh", src_dir=str(src), cluster=cluster)


# ---------------------------------------------------------------------------
# FakeConnection — a RemoteExecution that records calls and returns canned output
# ---------------------------------------------------------------------------

class FakeConnection(RemoteExecution):
    """Simulates a RemoteExecution for testing without real SSH or Slurm."""

    def __init__(self, sbatch_jobid: int = 42, sacct_state: str = "COMPLETED"):
        self.sbatch_jobid = sbatch_jobid
        self.sacct_state = sacct_state
        self.commands: list[str] = []
        self.uploaded: list[tuple[Path, Path]] = []
        self.downloaded: list[tuple[Path, Path]] = []

    def run(self, command: str, env: dict | None = None, retries: int = 0) -> CommandResult:
        self.commands.append(command)
        if "sbatch" in command:
            return CommandResult(
                command=command,
                stdout=f"Submitted batch job {self.sbatch_jobid}",
                stderr="",
                return_code=0,
            )
        if "sacct" in command:
            header = "JobID|Elapsed|Start|State|NodeList|"
            row = f"{self.sbatch_jobid}|00:00:05|2024-01-01T10:00:00|{self.sacct_state}|node1|"
            return CommandResult(command=command, stdout=f"{header}\n{row}", stderr="", return_code=0)
        if "scancel" in command:
            return CommandResult(command=command, stdout="", stderr="", return_code=0)
        return CommandResult(command=command, stdout="", stderr="", return_code=0)

    def upload_folder(self, local_path: Path, remote_path: Path) -> None:
        self.uploaded.append((local_path, remote_path))

    def download_folder(self, remote_path: Path, local_path: Path) -> None:
        self.downloaded.append((remote_path, local_path))
        # Simulate the download by copying from local if the src exists.
        if remote_path.exists():
            dest = local_path / remote_path.name
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(remote_path, dest, dirs_exist_ok=True)


# ---------------------------------------------------------------------------
# "local" cluster — calls real sbatch/sacct/scancel locally
# ---------------------------------------------------------------------------

class TestLocalCluster:
    """These tests mock subprocess so they run without Slurm installed."""

    def _slurm(self, tmp_path: Path) -> SlurmPilot:
        return SlurmPilot(config=make_config(tmp_path), clusters=["local"])

    def _fake_run(self, jobid: int = 99, state: str = "COMPLETED"):
        """Return a mock for subprocess.run that handles sbatch/sacct output."""
        def side_effect(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "sbatch" in cmd:
                m.stdout = f"Submitted batch job {jobid}\n"
                m.stderr = ""
            elif "sacct" in cmd:
                header = "JobID|Elapsed|Start|State|NodeList|"
                row = f"{jobid}|00:00:01|2024-01-01T10:00:00|{state}|local|"
                m.stdout = f"{header}\n{row}\n"
                m.stderr = ""
            else:
                m.stdout = ""
                m.stderr = ""
            return m
        return side_effect

    @patch("remote_command.subprocess.run")
    def test_schedule_job_calls_sbatch(self, mock_run, tmp_path):
        mock_run.side_effect = self._fake_run(jobid=77)
        slurm = self._slurm(tmp_path)
        jobid = slurm.schedule_job(bash_job(tmp_path, "local"))
        assert jobid == 77
        sbatch_calls = [c for c in [call[0][0] for call in mock_run.call_args_list] if "sbatch" in c]
        assert len(sbatch_calls) == 1
        assert "slurm_script.sh" in sbatch_calls[0]

    @patch("remote_command.subprocess.run")
    def test_schedule_job_writes_jobid_json(self, mock_run, tmp_path):
        mock_run.side_effect = self._fake_run(jobid=55)
        slurm = self._slurm(tmp_path)
        slurm.schedule_job(bash_job(tmp_path, "local"))
        jobid_file = tmp_path / "jobs" / "job" / "jobid.json"
        assert jobid_file.exists()
        import json
        assert json.loads(jobid_file.read_text())["jobid"] == 55

    @patch("remote_command.subprocess.run")
    def test_sbatch_command_contains_cd_to_job_dir(self, mock_run, tmp_path):
        mock_run.side_effect = self._fake_run()
        slurm = self._slurm(tmp_path)
        slurm.schedule_job(bash_job(tmp_path, "local", name="myjob"))
        sbatch_cmd = next(
            c[0][0] for c in mock_run.call_args_list if "sbatch" in c[0][0]
        )
        assert "myjob" in sbatch_cmd
        assert "cd" in sbatch_cmd

    @patch("remote_command.subprocess.run")
    def test_status_completed(self, mock_run, tmp_path):
        mock_run.side_effect = self._fake_run(jobid=10, state="COMPLETED")
        slurm = self._slurm(tmp_path)
        slurm.schedule_job(bash_job(tmp_path, "local"))
        assert slurm.status(["job"]) == ["COMPLETED"]

    @patch("remote_command.subprocess.run")
    def test_status_running(self, mock_run, tmp_path):
        mock_run.side_effect = self._fake_run(jobid=10, state="RUNNING")
        slurm = self._slurm(tmp_path)
        slurm.schedule_job(bash_job(tmp_path, "local"))
        assert slurm.status(["job"]) == ["RUNNING"]

    @patch("remote_command.subprocess.run")
    def test_log_reads_local_files(self, mock_run, tmp_path):
        mock_run.side_effect = self._fake_run()
        slurm = self._slurm(tmp_path)
        slurm.schedule_job(bash_job(tmp_path, "local"))
        # Write fake log files as if sbatch had run.
        log_dir = tmp_path / "jobs" / "job" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "stdout").write_text("local output\n")
        (log_dir / "stderr").write_text("")
        stdout, stderr = slurm.log("job")
        assert "local output" in stdout

    @patch("remote_command.subprocess.run")
    def test_no_upload_for_local_cluster(self, mock_run, tmp_path):
        """Local cluster must not call upload_folder — files are already there."""
        mock_run.side_effect = self._fake_run()
        slurm = self._slurm(tmp_path)
        # Replace the LocalExecution with a FakeConnection to track upload calls.
        fake = FakeConnection()
        slurm._connections["local"] = fake
        slurm.schedule_job(bash_job(tmp_path, "local"))
        assert fake.uploaded == [], "local cluster should not upload files"

    def test_sbatch_failure_raises(self, tmp_path):
        slurm = self._slurm(tmp_path)
        fake = FakeConnection()
        # Make sbatch return a failure.
        fake.run = lambda cmd, **kw: CommandResult(
            command=cmd, stdout="", stderr="disk quota exceeded", return_code=1
        )
        slurm._connections["local"] = fake
        with pytest.raises(RuntimeError, match="sbatch failed"):
            slurm.schedule_job(bash_job(tmp_path, "local"))

    @patch("remote_command.subprocess.run")
    def test_python_library_copied_to_job_folder_local(self, mock_run, tmp_path):
        """python_libraries are copied into the local job folder for the local backend."""
        mock_run.side_effect = self._fake_run()
        lib_dir = tmp_path / "libs" / "mylib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "__init__.py").write_text("")
        (lib_dir / "values.py").write_text("ANSWER = 42\n")

        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("from mylib.values import ANSWER\nprint(ANSWER)\n")

        import sys
        slurm = self._slurm(tmp_path)
        job = JobCreationInfo(
            jobname="libjob",
            entrypoint="main.py",
            src_dir=str(src),
            cluster="local",
            python_binary=sys.executable,
            python_libraries=[str(lib_dir)],
        )
        slurm.schedule_job(job)
        assert (tmp_path / "jobs" / "libjob" / "mylib").is_dir()
        assert (tmp_path / "jobs" / "libjob" / "mylib" / "values.py").exists()

    @patch("remote_command.subprocess.run")
    def test_pythonpath_in_slurm_script_local(self, mock_run, tmp_path):
        """Slurm script for local backend contains PYTHONPATH with job_dir and lib paths."""
        mock_run.side_effect = self._fake_run()
        lib_dir = tmp_path / "libs" / "mylib"
        lib_dir.mkdir(parents=True)
        (lib_dir / "__init__.py").write_text("")

        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("print('hi')\n")

        import sys
        slurm = self._slurm(tmp_path)
        job = JobCreationInfo(
            jobname="libjob",
            entrypoint="main.py",
            src_dir=str(src),
            cluster="local",
            python_binary=sys.executable,
            python_libraries=[str(lib_dir)],
        )
        slurm.schedule_job(job)
        script = (tmp_path / "jobs" / "libjob" / "slurm_script.sh").read_text()
        job_dir = str(tmp_path / "jobs" / "libjob")
        assert "PYTHONPATH" in script
        assert job_dir in script
        assert "mylib" in script


# ---------------------------------------------------------------------------
# SSH cluster — remote host via FakeConnection
# ---------------------------------------------------------------------------

class TestSSHCluster:
    CLUSTER = "bigcluster"

    def _slurm(self, tmp_path: Path, fake: FakeConnection | None = None) -> tuple[SlurmPilot, FakeConnection]:
        cfg = ClusterConfig(host="login.bigcluster.example.com", user="alice", remote_path="~/slurmpilot")
        slurm = SlurmPilot(
            config=make_config(tmp_path, {self.CLUSTER: cfg}),
            clusters=[self.CLUSTER],
        )
        if fake is None:
            fake = FakeConnection()
        slurm._connections[self.CLUSTER] = fake
        return slurm, fake

    def test_schedule_job_uploads_job_folder(self, tmp_path):
        slurm, fake = self._slurm(tmp_path)
        slurm.schedule_job(bash_job(tmp_path, self.CLUSTER))
        assert len(fake.uploaded) == 1
        local_path, remote_path = fake.uploaded[0]
        assert local_path.name == "job"          # the job dir was uploaded
        assert "jobs" in str(remote_path)        # into the remote jobs/ parent

    def test_schedule_job_returns_jobid(self, tmp_path):
        slurm, fake = self._slurm(tmp_path, FakeConnection(sbatch_jobid=999))
        jobid = slurm.schedule_job(bash_job(tmp_path, self.CLUSTER))
        assert jobid == 999

    def test_schedule_job_writes_jobid_json(self, tmp_path):
        slurm, fake = self._slurm(tmp_path, FakeConnection(sbatch_jobid=123))
        slurm.schedule_job(bash_job(tmp_path, self.CLUSTER))
        import json
        data = json.loads((tmp_path / "jobs" / "job" / "jobid.json").read_text())
        assert data["jobid"] == 123

    def test_sbatch_command_uses_remote_job_dir(self, tmp_path):
        slurm, fake = self._slurm(tmp_path)
        slurm.schedule_job(bash_job(tmp_path, self.CLUSTER, name="exp1"))
        sbatch_cmd = next(c for c in fake.commands if "sbatch" in c)
        assert "exp1" in sbatch_cmd
        assert "slurmpilot" in sbatch_cmd  # remote path embedded

    def test_status_completed(self, tmp_path):
        slurm, fake = self._slurm(tmp_path, FakeConnection(sbatch_jobid=7, sacct_state="COMPLETED"))
        slurm.schedule_job(bash_job(tmp_path, self.CLUSTER))
        assert slurm.status(["job"]) == ["COMPLETED"]

    def test_status_failed(self, tmp_path):
        slurm, fake = self._slurm(tmp_path, FakeConnection(sbatch_jobid=7, sacct_state="FAILED"))
        slurm.schedule_job(bash_job(tmp_path, self.CLUSTER))
        assert slurm.status(["job"]) == ["FAILED"]

    def test_status_running(self, tmp_path):
        slurm, fake = self._slurm(tmp_path, FakeConnection(sbatch_jobid=7, sacct_state="RUNNING"))
        slurm.schedule_job(bash_job(tmp_path, self.CLUSTER))
        assert slurm.status(["job"]) == ["RUNNING"]

    def test_log_downloads_logs_before_reading(self, tmp_path):
        slurm, fake = self._slurm(tmp_path)
        slurm.schedule_job(bash_job(tmp_path, self.CLUSTER, name="myjob"))
        # Place log files in the local job dir to simulate a completed download.
        log_dir = tmp_path / "jobs" / "myjob" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "stdout").write_text("remote output\n")
        (log_dir / "stderr").write_text("")
        stdout, _ = slurm.log("myjob")
        assert len(fake.downloaded) >= 1   # download_folder was called
        assert "remote output" in stdout

    def test_log_calls_download_with_remote_log_path(self, tmp_path):
        slurm, fake = self._slurm(tmp_path)
        slurm.schedule_job(bash_job(tmp_path, self.CLUSTER, name="myjob"))
        slurm.log("myjob")
        remote_log_path, _ = fake.downloaded[0]
        assert "logs" in str(remote_log_path)
        assert "myjob" in str(remote_log_path)

    def test_hostname_without_config_uses_host_directly(self, tmp_path):
        """A cluster name not in cluster_configs is used as the SSH hostname."""
        slurm = SlurmPilot(
            config=make_config(tmp_path),
            clusters=["somehost.example.com"],
        )
        conn = slurm._connections["somehost.example.com"]
        assert conn.host == "somehost.example.com"
        assert conn.user is None

    def test_hostname_with_config_uses_host_and_user(self, tmp_path):
        cfg = ClusterConfig(host="login.hpc.org", user="bob")
        slurm = SlurmPilot(
            config=make_config(tmp_path, {"mycluster": cfg}),
            clusters=["mycluster"],
        )
        conn = slurm._connections["mycluster"]
        assert conn.host == "login.hpc.org"
        assert conn.user == "bob"

    def test_sbatch_parse_failure_raises(self, tmp_path):
        slurm, fake = self._slurm(tmp_path)
        fake.run = lambda cmd, **kw: CommandResult(
            command=cmd, stdout="unexpected output", stderr="", return_code=0
        )
        with pytest.raises(RuntimeError, match="Could not parse sbatch output"):
            slurm.schedule_job(bash_job(tmp_path, self.CLUSTER))

    def test_sacct_failure_returns_none_status(self, tmp_path):
        slurm, fake = self._slurm(tmp_path, FakeConnection(sbatch_jobid=5))
        slurm.schedule_job(bash_job(tmp_path, self.CLUSTER))
        # Make sacct fail.
        def run_sacct_fail(cmd, **kw):
            if "sacct" in cmd:
                return CommandResult(command=cmd, stdout="", stderr="error", return_code=1)
            return CommandResult(command=cmd, stdout="Submitted batch job 5", stderr="", return_code=0)
        fake.run = run_sacct_fail
        assert slurm.status(["job"]) == [None]
