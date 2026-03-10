from pathlib import Path

import pytest

from mock_slurm import MockSlurm

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_script(directory: Path, commands: list[str]) -> Path:
    """Write a minimal sbatch script with log directives into `directory`."""
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "slurm_script.sh"
    lines = [
        "#!/bin/bash",
        "#SBATCH --job-name=test",
        "#SBATCH --output=logs/stdout",
        "#SBATCH --error=logs/stderr",
    ] + commands
    script.write_text("\n".join(lines) + "\n")
    return script


# ---------------------------------------------------------------------------
# sbatch
# ---------------------------------------------------------------------------

class TestSbatch:
    def setup_method(self):
        self.slurm = MockSlurm()

    def test_returns_positive_integer_jobid(self, tmp_path):
        script = write_script(tmp_path, ["echo hello"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        assert isinstance(jobid, int) and jobid > 0
        self.slurm.wait(jobid)

    def test_different_jobs_get_different_ids(self, tmp_path):
        s1 = write_script(tmp_path / "j1", ["echo a"])
        s2 = write_script(tmp_path / "j2", ["echo b"])
        id1 = self.slurm.sbatch(s1, cwd=tmp_path / "j1")
        id2 = self.slurm.sbatch(s2, cwd=tmp_path / "j2")
        self.slurm.wait(id1)
        self.slurm.wait(id2)
        assert id1 != id2

    def test_stdout_written_to_parsed_path(self, tmp_path):
        script = write_script(tmp_path, ["echo hello_world"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        assert (tmp_path / "logs" / "stdout").read_text().strip() == "hello_world"

    def test_stderr_written_to_parsed_path(self, tmp_path):
        script = write_script(tmp_path, ["echo error_line >&2"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        assert (tmp_path / "logs" / "stderr").read_text().strip() == "error_line"

    def test_log_directories_created_automatically(self, tmp_path):
        script = write_script(tmp_path, ["echo hi"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        assert (tmp_path / "logs").is_dir()

    def test_env_vars_available_in_script(self, tmp_path):
        script = write_script(tmp_path, ["echo $MY_VAR"])
        import os
        env = {**os.environ, "MY_VAR": "from_env"}
        jobid = self.slurm.sbatch(script, cwd=tmp_path, env=env)
        self.slurm.wait(jobid)
        assert (tmp_path / "logs" / "stdout").read_text().strip() == "from_env"

    def test_script_without_log_directives_does_not_crash(self, tmp_path):
        script = tmp_path / "bare.sh"
        script.write_text("#!/bin/bash\necho hi\n")
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)  # just must not raise


# ---------------------------------------------------------------------------
# scancel
# ---------------------------------------------------------------------------

class TestScancel:
    def setup_method(self):
        self.slurm = MockSlurm()

    def test_scancel_terminates_running_job(self, tmp_path):
        script = write_script(tmp_path, ["sleep 60"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.scancel(jobid)
        exit_code = self.slurm.wait(jobid)
        assert exit_code != 0  # killed by signal → negative exit code

    def test_scancel_unknown_jobid_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown job id"):
            self.slurm.scancel(999999)

    def test_scancel_already_finished_job_does_not_raise(self, tmp_path):
        script = write_script(tmp_path, ["echo done"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        # Should not raise even though process is gone
        self.slurm.scancel(jobid)


# ---------------------------------------------------------------------------
# sacct
# ---------------------------------------------------------------------------

class TestSacct:
    def setup_method(self):
        self.slurm = MockSlurm()

    def _parse_sacct(self, output: str) -> list[dict]:
        lines = output.strip().split("\n")
        keys = lines[0].rstrip("|").split("|")
        rows = []
        for line in lines[1:]:
            if line:
                values = line.rstrip("|").split("|")
                rows.append(dict(zip(keys, values)))
        return rows

    def test_header_format(self, tmp_path):
        script = write_script(tmp_path, ["echo hi"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        output = self.slurm.sacct([jobid])
        assert output.startswith("JobID|Elapsed|Start|State|NodeList|")

    def test_completed_state(self, tmp_path):
        script = write_script(tmp_path, ["echo hi"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        rows = self._parse_sacct(self.slurm.sacct([jobid]))
        assert rows[0]["State"] == "COMPLETED"

    def test_failed_state(self, tmp_path):
        script = write_script(tmp_path, ["exit 1"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        rows = self._parse_sacct(self.slurm.sacct([jobid]))
        assert rows[0]["State"] == "FAILED"

    def test_running_state(self, tmp_path):
        script = write_script(tmp_path, ["sleep 60"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        try:
            rows = self._parse_sacct(self.slurm.sacct([jobid]))
            assert rows[0]["State"] == "RUNNING"
        finally:
            self.slurm.scancel(jobid)
            self.slurm.wait(jobid)

    def test_cancelled_state(self, tmp_path):
        script = write_script(tmp_path, ["sleep 60"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.scancel(jobid)
        self.slurm.wait(jobid)
        rows = self._parse_sacct(self.slurm.sacct([jobid]))
        assert rows[0]["State"] == "CANCELLED"

    def test_nodelist_is_local(self, tmp_path):
        script = write_script(tmp_path, ["echo hi"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        rows = self._parse_sacct(self.slurm.sacct([jobid]))
        assert rows[0]["NodeList"] == "local"

    def test_jobid_in_row(self, tmp_path):
        script = write_script(tmp_path, ["echo hi"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        rows = self._parse_sacct(self.slurm.sacct([jobid]))
        assert rows[0]["JobID"] == str(jobid)

    def test_start_time_is_parseable(self, tmp_path):
        from datetime import datetime
        script = write_script(tmp_path, ["echo hi"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        rows = self._parse_sacct(self.slurm.sacct([jobid]))
        # Should not raise
        dt = datetime.strptime(rows[0]["Start"], "%Y-%m-%dT%H:%M:%S")
        assert dt.year >= 2024

    def test_elapsed_format(self, tmp_path):
        import re
        script = write_script(tmp_path, ["echo hi"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        rows = self._parse_sacct(self.slurm.sacct([jobid]))
        assert re.match(r"\d{2}:\d{2}:\d{2}", rows[0]["Elapsed"])

    def test_multiple_jobs_in_one_sacct_call(self, tmp_path):
        id1 = self.slurm.sbatch(write_script(tmp_path / "j1", ["echo a"]), cwd=tmp_path / "j1")
        id2 = self.slurm.sbatch(write_script(tmp_path / "j2", ["exit 1"]), cwd=tmp_path / "j2")
        self.slurm.wait(id1)
        self.slurm.wait(id2)
        rows = self._parse_sacct(self.slurm.sacct([id1, id2]))
        assert len(rows) == 2
        states = {r["JobID"]: r["State"] for r in rows}
        assert states[str(id1)] == "COMPLETED"
        assert states[str(id2)] == "FAILED"

    def test_unknown_jobid_omitted_from_output(self, tmp_path):
        script = write_script(tmp_path, ["echo hi"])
        jobid = self.slurm.sbatch(script, cwd=tmp_path)
        self.slurm.wait(jobid)
        rows = self._parse_sacct(self.slurm.sacct([jobid, 999999]))
        assert len(rows) == 1
