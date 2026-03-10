"""Unit tests for the CLI commands."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cli import (
    _resolve_jobname,
    cmd_list_jobs,
    cmd_log,
    cmd_metadata,
    cmd_path,
    cmd_slurm_script,
    cmd_status,
    cmd_stop,
    cmd_stop_all,
    cmd_test_ssh,
)
from config import Config
from job_metadata import JobMetadata
from job_path import JobPath

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLUSTER = "mock"
JOBNAME = "test/job-2026-01-01"
JOBID = 42


@pytest.fixture()
def config(tmp_path):
    return Config(local_path=tmp_path)


@pytest.fixture()
def job(config):
    """Create a minimal on-disk job directory and return its JobPath."""
    jp = JobPath(jobname=JOBNAME, root=config.local_slurmpilot_path())
    jp.job_dir.mkdir(parents=True)
    jp.metadata.write_text(
        JobMetadata(jobname=JOBNAME, cluster=CLUSTER, date="2026-01-01").to_json()
    )
    jp.jobid_file.write_text(json.dumps({"jobid": JOBID}))
    jp.log_dir.mkdir()
    jp.stdout.write_text("hello stdout\n")
    jp.stderr.write_text("hello stderr\n")
    jp.slurm_script.write_text("#!/bin/bash\n#SBATCH --job-name=test\nbash run.sh\n")
    return jp


def _args(jobname: str = JOBNAME) -> argparse.Namespace:
    return argparse.Namespace(jobname=jobname)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_cmd_log_prints_stdout_and_stderr(job, config, capsys):
    cmd_log(_args(), config)
    out = capsys.readouterr()
    assert "hello stdout" in out.out
    assert "hello stderr" in out.err


def test_cmd_log_empty_when_no_logs(job, config, capsys):
    job.stdout.unlink()
    job.stderr.unlink()
    cmd_log(_args(), config)
    out = capsys.readouterr()
    assert "no logs available yet" in out.out


def test_cmd_metadata_prints_fields(job, config, capsys):
    cmd_metadata(_args(), config)
    out = capsys.readouterr().out
    assert JOBNAME in out
    assert CLUSTER in out
    assert "2026-01-01" in out


def test_cmd_metadata_missing_job_exits(config):
    with pytest.raises(SystemExit):
        cmd_metadata(_args("nonexistent/job"), config)


def _mock_sp():
    from unittest.mock import MagicMock
    return MagicMock()


def test_cmd_status_prints_state(job, config, capsys):
    sp = _mock_sp()
    sp.status.return_value = ["COMPLETED"]
    with patch("cli._make_sp", return_value=(sp, JOBNAME)):
        cmd_status(_args(), config)
    assert "COMPLETED" in capsys.readouterr().out


def test_cmd_status_prints_unknown_when_none(job, config, capsys):
    sp = _mock_sp()
    sp.status.return_value = [None]
    with patch("cli._make_sp", return_value=(sp, JOBNAME)):
        cmd_status(_args(), config)
    assert "unknown" in capsys.readouterr().out


def test_cmd_stop_calls_stop_job(job, config, capsys):
    sp = _mock_sp()
    with patch("cli._make_sp", return_value=(sp, JOBNAME)):
        cmd_stop(_args(), config)
    sp.stop_job.assert_called_once_with(JOBNAME)
    assert JOBNAME in capsys.readouterr().out


def test_cmd_path_shows_local_path(job, config, capsys):
    cmd_path(_args(), config)
    out = capsys.readouterr().out
    assert str(config.local_slurmpilot_path()) in out


def test_cmd_path_no_remote_for_mock(job, config, capsys):
    cmd_path(_args(), config)
    assert "remote :" not in capsys.readouterr().out


def test_cmd_path_shows_remote_for_ssh_cluster(job, config, capsys):
    sp = _mock_sp()
    sp.local_job_path.return_value = Path("/local/path")
    sp.remote_job_path.return_value = Path("~/slurmpilot/jobs/test/job")
    with patch("cli._make_sp", return_value=(sp, JOBNAME)):
        cmd_path(_args(), config)
    out = capsys.readouterr().out
    assert "local" in out
    assert "remote" in out


def test_cmd_slurm_script_prints_script(job, config, capsys):
    cmd_slurm_script(_args(), config)
    out = capsys.readouterr().out
    assert "#!/bin/bash" in out
    assert "#SBATCH --job-name=test" in out


def test_cmd_slurm_script_missing_job_exits(config):
    with pytest.raises(SystemExit):
        cmd_slurm_script(_args("nonexistent/job"), config)


# ---------------------------------------------------------------------------
# Partial matching
# ---------------------------------------------------------------------------

def test_resolve_jobname_exact_match(job, config):
    meta = _resolve_jobname(JOBNAME, config)
    assert meta.jobname == JOBNAME


def test_resolve_jobname_partial_match(job, config):
    # Only the last segment of the jobname
    partial = JOBNAME.split("/")[-1]
    meta = _resolve_jobname(partial, config)
    assert meta.jobname == JOBNAME


def test_resolve_jobname_no_match_exits(config):
    with pytest.raises(SystemExit):
        _resolve_jobname("does-not-exist-anywhere", config)


def test_resolve_jobname_none_returns_latest(job, config):
    meta = _resolve_jobname(None, config)
    assert meta.jobname == JOBNAME


def test_resolve_jobname_none_exits_when_no_jobs(config):
    with pytest.raises(SystemExit):
        _resolve_jobname(None, config)


# ---------------------------------------------------------------------------
# list-jobs
# ---------------------------------------------------------------------------

_MOCK_SACCT_INFO = [{
    "jobname":  JOBNAME,
    "jobid":    str(JOBID),
    "task_id":  None,
    "cluster":  CLUSTER,
    "creation": "2026-01-01 00:00:00",
    "elapsed":  "00:05:00",
    "state":    "COMPLETED",
    "nodelist": "node01",
}]


def test_cmd_list_jobs_shows_table(job, config, capsys):
    args = argparse.Namespace(n=10, clusters=None, collapse_job_array=False)
    with patch("cli.SlurmPilot") as MockSP:
        MockSP.return_value.sacct_info.return_value = _MOCK_SACCT_INFO
        cmd_list_jobs(args, config)
    out = capsys.readouterr().out
    assert "job-2026-01-01" in out
    assert CLUSTER in out
    assert "✅" in out
    assert "5.0" in out       # elapsed minutes
    assert "node01" in out


def test_cmd_list_jobs_filters_by_cluster(job, config, capsys):
    args = argparse.Namespace(n=10, clusters=["other-cluster"], collapse_job_array=False)
    cmd_list_jobs(args, config)
    assert "No jobs found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# test-ssh
# ---------------------------------------------------------------------------

def test_cmd_test_ssh_success(config, capsys):
    args = argparse.Namespace(clusters=["mock"])
    with patch("cli.SlurmPilot") as MockSP:
        MockSP.return_value.test_ssh.return_value = True
        cmd_test_ssh(args, config)
    assert "✅" in capsys.readouterr().out


def test_cmd_test_ssh_failure(config, capsys):
    args = argparse.Namespace(clusters=["badhost"])
    with patch("cli.SlurmPilot") as MockSP:
        MockSP.return_value.test_ssh.return_value = False
        cmd_test_ssh(args, config)
    assert "❌" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# stop-all
# ---------------------------------------------------------------------------

def test_cmd_stop_all_cancels_jobs(job, config, capsys):
    args = argparse.Namespace(clusters=[CLUSTER])
    with patch("cli.SlurmPilot") as MockSP:
        MockSP.return_value.stop_all_jobs.return_value = [JOBNAME]
        cmd_stop_all(args, config)
    out = capsys.readouterr().out
    assert "🛑" in out
    assert "1 job(s) stopped" in out


def test_cmd_stop_all_no_jobs(config, capsys):
    args = argparse.Namespace(clusters=[CLUSTER])
    with patch("cli.SlurmPilot") as MockSP:
        MockSP.return_value.stop_all_jobs.return_value = []
        cmd_stop_all(args, config)
    assert "No jobs to stop" in capsys.readouterr().out


def test_cmd_list_jobs_no_jobs(config, capsys):
    args = argparse.Namespace(n=10, clusters=None, collapse_job_array=False)
    cmd_list_jobs(args, config)
    assert "No jobs found" in capsys.readouterr().out
