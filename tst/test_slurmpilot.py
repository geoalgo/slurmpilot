"""Tests for SlurmPilot using the mock cluster."""
import sys
from pathlib import Path

import pytest

from slurmpilot.config import Config
from slurmpilot.job_creation_info import JobCreationInfo
from slurmpilot import SlurmPilot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(tmp_path: Path) -> Config:
    return Config(local_path=tmp_path)


def make_bash_src(directory: Path, filename: str = "main.sh", body: str = "echo hello") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(f"#!/bin/bash\n{body}\n")
    return directory


def make_python_src(directory: Path, filename: str = "main.py", body: str = "print('hello')") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(body + "\n")
    return directory


def bash_job(tmp_path, name="job", src_subdir="src", body="echo hello") -> JobCreationInfo:
    src = make_bash_src(tmp_path / src_subdir, body=body)
    return JobCreationInfo(jobname=name, entrypoint="main.sh", src_dir=str(src), cluster="mock")


def _wait(slurm: SlurmPilot, jobid: int):
    slurm._mock_slurms["mock"].wait(jobid)


# ---------------------------------------------------------------------------
# schedule_job — file structure
# ---------------------------------------------------------------------------

class TestScheduleJobStructure:
    def test_returns_positive_int_jobid(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path))
        _wait(slurm, jobid)
        assert isinstance(jobid, int) and jobid > 0

    def test_creates_job_directory(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, name="myjob"))
        _wait(slurm, jobid)
        assert (tmp_path / "jobs" / "myjob").is_dir()

    def test_slurm_script_written(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, name="myjob"))
        _wait(slurm, jobid)
        assert (tmp_path / "jobs" / "myjob" / "slurm_script.sh").exists()

    def test_metadata_json_written(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, name="myjob"))
        _wait(slurm, jobid)
        assert (tmp_path / "jobs" / "myjob" / "metadata.json").exists()

    def test_jobid_json_written(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, name="myjob"))
        _wait(slurm, jobid)
        assert (tmp_path / "jobs" / "myjob" / "jobid.json").exists()

    def test_src_dir_copied_into_job_folder(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, name="myjob"))
        _wait(slurm, jobid)
        assert (tmp_path / "jobs" / "myjob" / "src" / "main.sh").exists()

    def test_nested_jobname_creates_nested_directory(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = bash_job(tmp_path, name="group/experiment1")
        jobid = slurm.schedule_job(job)
        _wait(slurm, jobid)
        assert (tmp_path / "jobs" / "group" / "experiment1").is_dir()


# ---------------------------------------------------------------------------
# schedule_job — dryrun
# ---------------------------------------------------------------------------

class TestDryrun:
    def test_dryrun_returns_none(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        result = slurm.schedule_job(bash_job(tmp_path), dryrun=True)
        assert result is None

    def test_dryrun_creates_script_and_metadata(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        slurm.schedule_job(bash_job(tmp_path, name="myjob"), dryrun=True)
        assert (tmp_path / "jobs" / "myjob" / "slurm_script.sh").exists()
        assert (tmp_path / "jobs" / "myjob" / "metadata.json").exists()

    def test_dryrun_does_not_write_jobid(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        slurm.schedule_job(bash_job(tmp_path, name="myjob"), dryrun=True)
        assert not (tmp_path / "jobs" / "myjob" / "jobid.json").exists()


# ---------------------------------------------------------------------------
# schedule_job — validation
# ---------------------------------------------------------------------------

class TestScheduleJobValidation:
    def test_duplicate_jobname_raises(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = bash_job(tmp_path)
        jobid = slurm.schedule_job(job)
        _wait(slurm, jobid)
        with pytest.raises(ValueError, match="already exists"):
            slurm.schedule_job(job)

    def test_missing_src_dir_raises(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = JobCreationInfo(jobname="j", entrypoint="x.sh", src_dir="/no/such/dir", cluster="mock")
        with pytest.raises(AssertionError):
            slurm.schedule_job(job)

    def test_missing_entrypoint_raises(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        src = make_bash_src(tmp_path / "src")
        job = JobCreationInfo(jobname="j", entrypoint="missing.sh", src_dir=str(src), cluster="mock")
        with pytest.raises(AssertionError):
            slurm.schedule_job(job)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_completed(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, body="echo done"))
        _wait(slurm, jobid)
        assert slurm.status(["job"]) == ["COMPLETED"]

    def test_failed(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, body="exit 1"))
        _wait(slurm, jobid)
        assert slurm.status(["job"]) == ["FAILED"]

    def test_running(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, body="sleep 60"))
        try:
            assert slurm.status(["job"]) == ["RUNNING"]
        finally:
            slurm._mock_slurms["mock"].scancel(jobid)
            _wait(slurm, jobid)

    def test_none_when_jobid_missing(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        slurm.schedule_job(bash_job(tmp_path), dryrun=True)
        assert slurm.status(["job"]) == [None]

    def test_multiple_jobs(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        id1 = slurm.schedule_job(bash_job(tmp_path, name="j1", src_subdir="s1", body="echo ok"))
        id2 = slurm.schedule_job(bash_job(tmp_path, name="j2", src_subdir="s2", body="exit 1"))
        _wait(slurm, id1)
        _wait(slurm, id2)
        assert slurm.status(["j1", "j2"]) == ["COMPLETED", "FAILED"]


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------

class TestLog:
    def test_stdout_content(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, body="echo hello_world"))
        _wait(slurm, jobid)
        stdout, _ = slurm.log("job")
        assert "hello_world" in stdout

    def test_stderr_content(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        jobid = slurm.schedule_job(bash_job(tmp_path, body="echo error_line >&2"))
        _wait(slurm, jobid)
        _, stderr = slurm.log("job")
        assert "error_line" in stderr

    def test_empty_before_job_runs(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        slurm.schedule_job(bash_job(tmp_path), dryrun=True)
        stdout, stderr = slurm.log("job")
        assert stdout == "" and stderr == ""

    def test_python_entrypoint(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        src = make_python_src(tmp_path / "src", body="print('python_hello')")
        job = JobCreationInfo(
            jobname="pyjob",
            entrypoint="main.py",
            src_dir=str(src),
            cluster="mock",
            python_binary=sys.executable,
        )
        jobid = slurm.schedule_job(job)
        _wait(slurm, jobid)
        stdout, _ = slurm.log("pyjob")
        assert "python_hello" in stdout
        assert slurm.status(["pyjob"]) == ["COMPLETED"]

    def test_python_entrypoint_with_dict_args(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        src = make_python_src(
            tmp_path / "src",
            body=(
                "import argparse\n"
                "p = argparse.ArgumentParser()\n"
                "p.add_argument('--greeting')\n"
                "args = p.parse_args()\n"
                "print(args.greeting)\n"
            ),
        )
        job = JobCreationInfo(
            jobname="argsjob",
            entrypoint="main.py",
            src_dir=str(src),
            cluster="mock",
            python_binary=sys.executable,
            python_args={"greeting": "bonjour"},
        )
        jobid = slurm.schedule_job(job)
        _wait(slurm, jobid)
        stdout, _ = slurm.log("argsjob")
        assert "bonjour" in stdout

    def test_bash_setup_command_runs(self, tmp_path):
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = bash_job(tmp_path, body="echo $MY_VAR")
        job.bash_setup_command = "export MY_VAR=setup_ran"
        jobid = slurm.schedule_job(job)
        _wait(slurm, jobid)
        stdout, _ = slurm.log("job")
        assert "setup_ran" in stdout


# ---------------------------------------------------------------------------
# python_libraries — file copying and PYTHONPATH
# ---------------------------------------------------------------------------

def make_custom_lib(lib_root: Path, lib_name: str = "mylib") -> Path:
    """Create a minimal Python package at lib_root/lib_name/."""
    lib_dir = lib_root / lib_name
    lib_dir.mkdir(parents=True)
    (lib_dir / "__init__.py").write_text("")
    (lib_dir / "values.py").write_text("ANSWER = 42\n")
    return lib_dir


def make_python_src_using_lib(src_root: Path, lib_name: str = "mylib") -> Path:
    src_root.mkdir(parents=True, exist_ok=True)
    (src_root / "main.py").write_text(
        f"from {lib_name}.values import ANSWER\nprint(f'answer={{ANSWER}}')\n"
    )
    return src_root


class TestPythonLibraries:
    def test_library_copied_to_job_folder_mock(self, tmp_path):
        """python_libraries are copied into the job folder for mock backend."""
        lib_dir = make_custom_lib(tmp_path / "libs")
        src = make_python_src_using_lib(tmp_path / "src")
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = JobCreationInfo(
            jobname="libjob",
            entrypoint="main.py",
            src_dir=str(src),
            cluster="mock",
            python_binary=sys.executable,
            python_libraries=[str(lib_dir)],
        )
        slurm.schedule_job(job, dryrun=True)
        assert (tmp_path / "jobs" / "libjob" / "mylib").is_dir()
        assert (tmp_path / "jobs" / "libjob" / "mylib" / "values.py").exists()

    def test_pythonpath_in_slurm_script_mock(self, tmp_path):
        """Slurm script must export PYTHONPATH including the job dir and lib subdir."""
        lib_dir = make_custom_lib(tmp_path / "libs")
        src = make_python_src_using_lib(tmp_path / "src")
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = JobCreationInfo(
            jobname="libjob",
            entrypoint="main.py",
            src_dir=str(src),
            cluster="mock",
            python_binary=sys.executable,
            python_libraries=[str(lib_dir)],
        )
        slurm.schedule_job(job, dryrun=True)
        script = (tmp_path / "jobs" / "libjob" / "slurm_script.sh").read_text()
        job_dir = str(tmp_path / "jobs" / "libjob")
        assert "PYTHONPATH" in script
        assert job_dir in script
        assert "mylib" in script

    def test_library_importable_end_to_end_mock(self, tmp_path):
        """End-to-end: mock job can import from a copied python_library."""
        lib_dir = make_custom_lib(tmp_path / "libs")
        src = make_python_src_using_lib(tmp_path / "src")
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = JobCreationInfo(
            jobname="libjob",
            entrypoint="main.py",
            src_dir=str(src),
            cluster="mock",
            python_binary=sys.executable,
            python_libraries=[str(lib_dir)],
        )
        jobid = slurm.schedule_job(job)
        _wait(slurm, jobid)
        stdout, stderr = slurm.log("libjob")
        assert "answer=42" in stdout
        assert slurm.status(["libjob"]) == ["COMPLETED"]

    def test_missing_python_library_raises(self, tmp_path):
        """A nonexistent python_libraries path raises AssertionError."""
        src = make_bash_src(tmp_path / "src")
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = JobCreationInfo(
            jobname="badjob",
            entrypoint="main.sh",
            src_dir=str(src),
            cluster="mock",
            python_libraries=["/no/such/lib"],
        )
        with pytest.raises(AssertionError, match="python_library not found"):
            slurm.schedule_job(job)


# ---------------------------------------------------------------------------
# Job arrays (python_args as list)
# ---------------------------------------------------------------------------

class TestJobArray:
    def _array_job(self, tmp_path, args, name="arrayjob", n_concurrent_jobs=None) -> JobCreationInfo:
        src = make_python_src(
            tmp_path / "src",
            body=(
                "import argparse\n"
                "p = argparse.ArgumentParser()\n"
                "p.add_argument('--value')\n"
                "args = p.parse_args()\n"
                "print(args.value)\n"
            ),
        )
        return JobCreationInfo(
            jobname=name,
            entrypoint="main.py",
            src_dir=str(src),
            cluster="mock",
            python_binary=sys.executable,
            python_args=args,
            n_concurrent_jobs=n_concurrent_jobs,
        )

    def test_python_args_txt_written(self, tmp_path):
        """python-args.txt is created with one line per element."""
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = self._array_job(tmp_path, ["--value=a", "--value=b", "--value=c"])
        slurm.schedule_job(job, dryrun=True)
        args_file = tmp_path / "jobs" / "arrayjob" / "python-args.txt"
        assert args_file.exists()
        lines = args_file.read_text().splitlines()
        assert lines == ["--value=a", "--value=b", "--value=c"]

    def test_python_args_txt_dict_entries(self, tmp_path):
        """Dict entries in python_args list are serialised to --key=value format."""
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = self._array_job(tmp_path, [{"value": "x"}, {"value": "y"}])
        slurm.schedule_job(job, dryrun=True)
        lines = (tmp_path / "jobs" / "arrayjob" / "python-args.txt").read_text().splitlines()
        assert lines == ["--value=x", "--value=y"]

    def test_array_directive_in_script(self, tmp_path):
        """Slurm script contains #SBATCH --array=0-N for a list of N+1 args."""
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = self._array_job(tmp_path, ["--value=a", "--value=b", "--value=c"])
        slurm.schedule_job(job, dryrun=True)
        script = (tmp_path / "jobs" / "arrayjob" / "slurm_script.sh").read_text()
        assert "#SBATCH --array=0-2" in script

    def test_array_directive_with_n_concurrent_jobs(self, tmp_path):
        """n_concurrent_jobs appends %N to the --array directive."""
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = self._array_job(tmp_path, ["--value=a", "--value=b", "--value=c"], n_concurrent_jobs=1)
        slurm.schedule_job(job, dryrun=True)
        script = (tmp_path / "jobs" / "arrayjob" / "slurm_script.sh").read_text()
        assert "#SBATCH --array=0-2%1" in script

    def test_sed_lookup_in_script(self, tmp_path):
        """Slurm script reads the task argument from python-args.txt via sed."""
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = self._array_job(tmp_path, ["--value=a", "--value=b"])
        slurm.schedule_job(job, dryrun=True)
        script = (tmp_path / "jobs" / "arrayjob" / "slurm_script.sh").read_text()
        assert "python-args.txt" in script
        assert "SLURM_ARRAY_TASK_ID" in script
        assert "$argument" in script

    def test_end_to_end_array_task_0(self, tmp_path):
        """Mock runs task 0: SLURM_ARRAY_TASK_ID=0 → reads first line → correct output."""
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = self._array_job(tmp_path, ["--value=hello", "--value=world"])
        # Inject SLURM_ARRAY_TASK_ID=0 so the mock process reads line 1
        job.env = {"SLURM_ARRAY_TASK_ID": "0"}
        jobid = slurm.schedule_job(job)
        _wait(slurm, jobid)
        stdout, _ = slurm.log("arrayjob")
        assert "hello" in stdout
        assert slurm.status(["arrayjob"]) == ["COMPLETED"]

    def test_end_to_end_array_task_1(self, tmp_path):
        """Mock runs task 1: SLURM_ARRAY_TASK_ID=1 → reads second line → correct output."""
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        job = self._array_job(tmp_path, ["--value=hello", "--value=world"], name="arrayjob2")
        job.env = {"SLURM_ARRAY_TASK_ID": "1"}
        jobid = slurm.schedule_job(job)
        _wait(slurm, jobid)
        stdout, _ = slurm.log("arrayjob2")
        assert "world" in stdout

    def test_n_concurrent_jobs_without_list_raises(self, tmp_path):
        """n_concurrent_jobs requires python_args to be a list."""
        src = make_python_src(tmp_path / "src")
        job = JobCreationInfo(
            jobname="j",
            entrypoint="main.py",
            src_dir=str(src),
            cluster="mock",
            python_binary=sys.executable,
            python_args="--foo=bar",
            n_concurrent_jobs=2,
        )
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        with pytest.raises(AssertionError, match="n_concurrent_jobs"):
            slurm.schedule_job(job)


# ---------------------------------------------------------------------------
# remote_path override
# ---------------------------------------------------------------------------

class TestRemotePath:
    def test_remote_root_uses_job_remote_path(self, tmp_path):
        """_remote_root returns job_info.remote_path when set."""
        slurm = SlurmPilot(config=make_config(tmp_path), clusters=["mock"])
        src = make_bash_src(tmp_path / "src")
        job = JobCreationInfo(
            jobname="rjob",
            entrypoint="main.sh",
            src_dir=str(src),
            cluster="mock",
            remote_path="/custom/remote/root",
        )
        root = slurm._remote_root(job)
        assert root == Path("/custom/remote/root")

    def test_remote_root_falls_back_to_cluster_config(self, tmp_path):
        """_remote_root falls back to cluster config when remote_path is None."""
        from slurmpilot.config import ClusterConfig
        config = Config(
            local_path=tmp_path,
            cluster_configs={"mycluster": ClusterConfig(host="h", remote_path="/cluster/default")},
        )
        slurm = SlurmPilot(config=config, clusters=["mock"])
        src = make_bash_src(tmp_path / "src")
        job = JobCreationInfo(
            jobname="rjob",
            entrypoint="main.sh",
            src_dir=str(src),
            cluster="mycluster",
        )
        root = slurm._remote_root(job)
        assert root == Path("/cluster/default")

    def test_job_run_dir_uses_remote_path(self, tmp_path):
        """_job_run_dir embeds remote_path into the script working directory."""
        from slurmpilot.config import ClusterConfig
        config = Config(
            local_path=tmp_path,
            cluster_configs={"mycluster": ClusterConfig(host="h", remote_path="/default")},
        )
        slurm = SlurmPilot(config=config, clusters=["mock"])
        src = make_bash_src(tmp_path / "src")
        job = JobCreationInfo(
            jobname="myjob",
            entrypoint="main.sh",
            src_dir=str(src),
            cluster="mycluster",
            remote_path="/custom/root",
        )
        from slurmpilot.job_path import JobPath
        local = JobPath(jobname="myjob", root=config.local_slurmpilot_path())
        run_dir = slurm._job_run_dir("mycluster", local, job)
        assert str(run_dir).startswith("/custom/root")

    def test_slurm_script_pythonpath_uses_remote_path(self, tmp_path):
        """For Python jobs, PYTHONPATH in the slurm script reflects remote_path."""
        from slurmpilot.config import ClusterConfig
        config = Config(
            local_path=tmp_path,
            cluster_configs={"mycluster": ClusterConfig(host="h", remote_path="/default")},
        )
        slurm = SlurmPilot(config=config, clusters=["mock"])
        src = make_python_src(tmp_path / "src")
        job = JobCreationInfo(
            jobname="myjob",
            entrypoint="main.py",
            src_dir=str(src),
            cluster="mycluster",
            python_binary=sys.executable,
            remote_path="/custom/root",
        )
        slurm.schedule_job(job, dryrun=True)
        script = (tmp_path / "jobs" / "myjob" / "slurm_script.sh").read_text()
        assert "PYTHONPATH" in script
        assert "/custom/root" in script
