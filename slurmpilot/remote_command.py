"""
SSH and local command execution.

Two implementations are provided:
- `SSHExecution`: runs commands on a remote host via native ssh/rsync subprocesses.
- `LocalExecution`: runs commands locally; useful for testing or single-machine use.
"""
import logging
import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    command: str
    stdout: str
    stderr: str
    return_code: int

    @property
    def failed(self) -> bool:
        return self.return_code != 0


class RemoteExecution(ABC):
    @abstractmethod
    def run(self, command: str, env: dict | None = None, retries: int = 0) -> CommandResult: ...

    @abstractmethod
    def upload_folder(self, local_path: Path, remote_path: Path) -> None: ...

    @abstractmethod
    def download_folder(self, remote_path: Path, local_path: Path) -> None: ...


class LocalExecution(RemoteExecution):
    """Runs commands and copies files locally."""

    def run(self, command: str, env: dict | None = None, retries: int = 0) -> CommandResult:
        # shell=True is required so that compound commands (&&, cd, etc.) work
        # the same way they do when forwarded through ssh.
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return CommandResult(
            command=command,
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.returncode,
        )

    def upload_folder(self, local_path: Path, remote_path: Path) -> None:
        """Copy local_path into remote_path (mirrors rsync semantics: dst/src_name/)."""
        local_path = Path(local_path)
        remote_path = Path(remote_path)
        dest = remote_path / local_path.name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src=local_path, dst=dest, dirs_exist_ok=True)

    def download_folder(self, remote_path: Path, local_path: Path) -> None:
        """Copy remote_path into local_path (mirrors rsync semantics: dst/src_name/)."""
        remote_path = Path(remote_path)
        local_path = Path(local_path)
        dest = local_path / remote_path.name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src=remote_path, dst=dest, dirs_exist_ok=True)


class SSHExecution(RemoteExecution):
    """Runs commands on a remote host via ssh subprocess; transfers files via rsync."""

    def __init__(self, host: str, user: str | None = None):
        self.host = host
        self.user = user

    @property
    def _remote(self) -> str:
        return f"{self.user}@{self.host}" if self.user else self.host

    def run(self, command: str, env: dict | None = None, retries: int = 0) -> CommandResult:
        """
        Run `command` on the remote host.

        :param command: shell command string to execute remotely.
        :param env: optional dict of environment variables prepended via `env KEY=val`.
        :param retries: number of additional attempts on failure (0 = try once).
        """
        remote_command = command
        if env:
            env_prefix = " ".join(f"{k}={shlex.quote(str(v))}" for k, v in env.items())
            remote_command = f"env {env_prefix} {command}"

        ssh_args = ["ssh", self._remote, remote_command]

        for attempt in range(1 + retries):
            result = subprocess.run(ssh_args, capture_output=True, text=True)
            cmd_result = CommandResult(
                command=command,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                return_code=result.returncode,
            )
            if not cmd_result.failed:
                return cmd_result
            if attempt < retries:
                logger.warning(
                    f"Command failed (attempt {attempt + 1}/{1 + retries}), retrying: {command}"
                )

        return cmd_result

    def upload_folder(self, local_path: Path, remote_path: Path) -> None:
        """
        Upload local_path to remote_path via rsync.
        The folder will appear as remote_path/local_path.name/ on the remote host.
        """
        local_path = Path(local_path)
        subprocess.run(
            ["ssh", self._remote, f"mkdir -p {str(remote_path)}"],
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["rsync", "-az", str(local_path), f"{self._remote}:{remote_path}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"rsync upload failed:\n{result.stderr}")

    def download_folder(self, remote_path: Path, local_path: Path) -> None:
        """
        Download remote_path to local_path via rsync.
        The folder will appear as local_path/remote_path.name/ locally.
        """
        local_path = Path(local_path)
        local_path.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["rsync", "-az", f"{self._remote}:{remote_path}", str(local_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"rsync download failed:\n{result.stderr}")
