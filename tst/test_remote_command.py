from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from slurmpilot.remote_command import CommandResult, LocalExecution, SSHExecution

# ---------------------------------------------------------------------------
# CommandResult
# ---------------------------------------------------------------------------

class TestCommandResult:
    def test_failed_when_nonzero_return_code(self):
        r = CommandResult(command="x", stdout="", stderr="", return_code=1)
        assert r.failed

    def test_not_failed_when_zero_return_code(self):
        r = CommandResult(command="x", stdout="", stderr="", return_code=0)
        assert not r.failed


# ---------------------------------------------------------------------------
# LocalExecution
# ---------------------------------------------------------------------------

class TestLocalExecution:
    def setup_method(self):
        self.exe = LocalExecution()

    def test_run_success(self):
        result = self.exe.run("echo hello")
        assert not result.failed
        assert "hello" in result.stdout

    def test_run_captures_stderr(self):
        result = self.exe.run("ls /nonexistent_xyz_path")
        assert result.failed
        assert result.stderr != ""

    def test_run_command_with_spaces_in_args(self):
        result = self.exe.run("echo hello world")
        assert "hello world" in result.stdout

    def test_upload_folder(self):
        with TemporaryDirectory() as src, TemporaryDirectory() as dst:
            src_path = Path(src)
            dst_path = Path(dst)
            (src_path / "file.txt").write_text("hello")
            self.exe.upload_folder(src_path, dst_path)
            assert (dst_path / src_path.name / "file.txt").read_text() == "hello"

    def test_upload_folder_creates_destination_if_missing(self):
        with TemporaryDirectory() as src, TemporaryDirectory() as base:
            src_path = Path(src)
            dst_path = Path(base) / "new" / "nested"
            (src_path / "file.txt").write_text("data")
            self.exe.upload_folder(src_path, dst_path)
            assert (dst_path / src_path.name / "file.txt").exists()

    def test_upload_folder_nested_files(self):
        with TemporaryDirectory() as src, TemporaryDirectory() as dst:
            src_path = Path(src)
            (src_path / "sub").mkdir()
            (src_path / "sub" / "deep.txt").write_text("deep")
            self.exe.upload_folder(src_path, Path(dst))
            assert (Path(dst) / src_path.name / "sub" / "deep.txt").exists()

    def test_download_folder(self):
        with TemporaryDirectory() as remote, TemporaryDirectory() as local:
            remote_path = Path(remote)
            local_path = Path(local)
            (remote_path / "result.txt").write_text("output")
            self.exe.download_folder(remote_path, local_path)
            assert (local_path / remote_path.name / "result.txt").read_text() == "output"

    def test_download_folder_creates_destination_if_missing(self):
        with TemporaryDirectory() as remote, TemporaryDirectory() as base:
            remote_path = Path(remote)
            local_path = Path(base) / "new" / "nested"
            (remote_path / "result.txt").write_text("output")
            self.exe.download_folder(remote_path, local_path)
            assert (local_path / remote_path.name / "result.txt").exists()


# ---------------------------------------------------------------------------
# SSHExecution
# ---------------------------------------------------------------------------

def _proc(stdout="", stderr="", returncode=0):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


class TestSSHExecution:
    def setup_method(self):
        self.exe = SSHExecution(host="cluster.example.com", user="alice")

    def test_remote_with_user(self):
        assert self.exe._remote == "alice@cluster.example.com"

    def test_remote_without_user(self):
        exe = SSHExecution(host="cluster.example.com")
        assert exe._remote == "cluster.example.com"

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_run_success(self, mock_run):
        mock_run.return_value = _proc(stdout="hello\n")
        result = self.exe.run("echo hello")
        assert not result.failed
        assert result.stdout == "hello"
        mock_run.assert_called_once_with(
            ["ssh", "alice@cluster.example.com", "echo hello"],
            capture_output=True,
            text=True,
        )

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_run_failure(self, mock_run):
        mock_run.return_value = _proc(stderr="no such file", returncode=1)
        result = self.exe.run("ls /bad")
        assert result.failed
        assert result.return_code == 1
        assert result.stderr == "no such file"

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_run_with_env(self, mock_run):
        mock_run.return_value = _proc(stdout="42\n")
        self.exe.run("echo $FOO", env={"FOO": "42"})
        remote_command_arg = mock_run.call_args[0][0][2]
        assert "FOO=42" in remote_command_arg
        assert remote_command_arg.startswith("env ")

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_run_retries_on_failure_then_succeeds(self, mock_run):
        mock_run.side_effect = [_proc(returncode=1), _proc(returncode=0)]
        result = self.exe.run("flaky", retries=1)
        assert not result.failed
        assert mock_run.call_count == 2

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_run_exhausts_retries(self, mock_run):
        mock_run.return_value = _proc(returncode=1)
        result = self.exe.run("bad", retries=2)
        assert result.failed
        assert mock_run.call_count == 3  # 1 initial + 2 retries

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_run_no_retry_on_success(self, mock_run):
        mock_run.return_value = _proc(returncode=0)
        self.exe.run("ok", retries=5)
        assert mock_run.call_count == 1

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_upload_folder(self, mock_run):
        mock_run.return_value = _proc()
        self.exe.upload_folder(Path("/local/mydir"), Path("/remote/jobs"))
        assert mock_run.call_count == 2
        mkdir_call = mock_run.call_args_list[0][0][0]
        assert mkdir_call[:2] == ["ssh", "alice@cluster.example.com"]
        rsync_call = mock_run.call_args_list[1][0][0]
        assert rsync_call[0] == "rsync"
        assert rsync_call[-1] == "alice@cluster.example.com:/remote/jobs"

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_upload_folder_raises_on_rsync_failure(self, mock_run):
        mock_run.side_effect = [_proc(), _proc(returncode=255, stderr="refused")]
        with pytest.raises(RuntimeError, match="rsync upload failed"):
            self.exe.upload_folder(Path("/local/mydir"), Path("/remote/jobs"))

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_download_folder(self, mock_run):
        mock_run.return_value = _proc()
        with TemporaryDirectory() as local:
            self.exe.download_folder(Path("/remote/jobs/myjob"), Path(local))
        rsync_call = mock_run.call_args[0][0]
        assert rsync_call[0] == "rsync"
        assert "alice@cluster.example.com:/remote/jobs/myjob" in rsync_call

    @patch("slurmpilot.remote_command.subprocess.run")
    def test_download_folder_raises_on_rsync_failure(self, mock_run):
        mock_run.return_value = _proc(returncode=1, stderr="error")
        with TemporaryDirectory() as local:
            with pytest.raises(RuntimeError, match="rsync download failed"):
                self.exe.download_folder(Path("/remote/jobs/myjob"), Path(local))
