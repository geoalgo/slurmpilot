import logging
import tempfile
from pathlib import Path
from typing import NamedTuple, Optional
import tarfile

logger = logging.getLogger(__name__)


class CommandResult(NamedTuple):
    command: str
    failed: bool
    stderr: str
    stdout: str
    return_code: int


class RemoteExecution:
    def __init__(self, master: str, proxy: Optional[str] = None):
        """
        Wraps functionality to run remote command and upload/download files and folders to a remote host possibly
        connected through a proxy.
        Note: We wrap fabric instead of exposing it (which is a wrapper itself) in order to be able to support
        multiple choices in the future possibly including one which is dependency free.
        :param master:
        :param proxy:
        """
        self.master = master
        self.proxy = proxy

    def run(self, command: str, pty: bool = False, env: dict | None = None) -> CommandResult:
        raise NotImplementedError()

    def upload_file(self, local_path: Path, remote_path: Path = Path("/")):
        raise NotImplementedError()

    def upload_folder(self, local_path: Path, remote_path: Path = Path("/")):
        raise NotImplementedError()

    def download_file(self, remote_path: Path, local_path: Path):
        raise NotImplementedError()


class RemoteCommandExecutionFabrik(RemoteExecution):
    # TODO we could create a dependency free version with `getstatusoutput` that calls ssh command
    def __init__(self, master: str, user: str | None = None, proxy: str | None = None):
        super().__init__(master=master, proxy=proxy)
        from fabric import Connection

        self.connection = Connection(
            self.master,
            user=user,
            gateway=None if not proxy else Connection(proxy)
        )

    def run(self, command: str, pty: bool = False, env: dict | None = None) -> CommandResult:
        fabric_result = self.connection.run(command=command, hide=True, pty=pty, env=env)
        # TODO show error when failed
        if fabric_result.failed:
            logging.info(f"Command {command} failed\n{fabric_result.stderr}")
        return CommandResult(
            command=command,
            failed=fabric_result.failed,
            return_code=fabric_result.return_code,
            stderr=fabric_result.stderr,
            stdout=fabric_result.stdout,
        )

    def upload_file(self, local_path: Path, remote_path: Path = Path("/")):
        # TODO consider using rsync which is supported in Fabric,
        #  potential downside: it may not be installed on remote node...
        # fabric.contrib.project.upload_project seems also a viable option
        local_path = Path(local_path)
        assert local_path.is_file()
        self.run(f"mkdir -p {remote_path}")
        self.connection.put(
            local=str(local_path),
            remote=str(remote_path),
        )

    def upload_folder(self, local_path: Path, remote_path: Path = Path("/")):
        local_path = Path(local_path)
        assert local_path.is_dir()
        # tar before sending and untar remotely
        # Note: we could also use rsync
        with tempfile.TemporaryDirectory() as tmpdirname:
            tarpath = self._tar(local_path, tgt=Path(tmpdirname) / local_path.name)
            logger.info(f"sending {tarpath} remotely to {self.connection.host}")
            self.run(f"mkdir -p {str(remote_path)}")
            self.connection.put(
                local=str(tarpath),
                remote=str(remote_path),
            )
            logger.debug(f"extracting remotely")
            command = f"cd {remote_path}; tar -xvf {tarpath.name}; rm {tarpath.name}"
            self.run(command)

    def _tar(self, path_to_archive: Path, tgt: Path):
        assert path_to_archive.is_dir()
        tarpath = tgt.with_suffix(".tar.gz")
        logger.info(f"Compressing {path_to_archive} into {tgt}")
        with tarfile.open(tarpath, "w:gz") as tar:
            tar.add(path_to_archive, arcname=path_to_archive.stem)
        return tarpath

    def download_file(self, remote_path: Path, local_path: Path):
        self.connection.get(
            remote=str(remote_path),
            local=str(local_path),
        )


if __name__ == "__main__":
    connection = (RemoteCommandExecutionFabrik("slurm_master"),)  # proxy="proxy")
    connection.send("check", remote_path="yo/")
