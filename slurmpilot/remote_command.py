import logging
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
import tarfile

import paramiko

from slurmpilot.util import path_size_human_readable

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    command: str
    failed: bool
    stderr: str
    stdout: str
    return_code: int


class RemoteExecution:
    def __init__(self, master: str, user: str | None = None, proxy: str | None = None):
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
        self.user = user

    def run(
        self, command: str, pty: bool = False, env: dict | None = None, retries: int = 0
    ) -> CommandResult:
        raise NotImplementedError()

    def upload_file(self, local_path: Path, remote_path: Path = Path("/")):
        raise NotImplementedError()

    def upload_folder(self, local_path: Path, remote_path: Path = Path("/")):
        raise NotImplementedError()

    def download_file(self, remote_path: Path, local_path: Path):
        raise NotImplementedError()

    def download_folder(self, remote_path: Path, local_path: Path):
        raise NotImplementedError()


class LocalCommandExecution(RemoteExecution):
    def __init__(
        self,
        master: str,
        user: str | None = None,
        proxy: str | None = None,
        folder: str | None = None,
    ):
        super().__init__(master=master, proxy=proxy, user=user)
        self.folder = folder

    def run(
        self,
        command: str,
        pty: bool = False,
        env: dict | None = None,
        retries: int = 0,
        log_error: bool = True,
    ) -> CommandResult:
        # TODO evaluate command with subprocess like in syne tune
        raise NotImplementedError()

    def upload_file(self, local_path: Path, remote_path: Path = Path("/")):
        # TODO copy file locally
        raise NotImplementedError()

    def upload_folder(self, local_path: Path, remote_path: Path = Path("/")):
        # TODO copy folder locally with shutil.copytree
        raise NotImplementedError()

    def download_file(self, remote_path: Path, local_path: Path):
        # TODO copy file locally
        raise NotImplementedError()

    def download_folder(self, remote_path: Path, local_path: Path):
        # TODO copy file locally
        raise NotImplementedError()


class RemoteCommandExecutionFabrik(RemoteExecution):
    # TODO we could create a dependency free version with `getstatusoutput` that calls ssh command
    def __init__(
        self,
        master: str,
        user: str | None = None,
        proxy: str | None = None,
        prompt_for_login_password: bool = False,
        prompt_for_login_passphrase: bool = False,
    ):
        from fabric import Connection

        super().__init__(master=master, proxy=proxy, user=user)
        logging.getLogger("fabric").setLevel(logging.WARNING)
        logging.getLogger("paramiko").setLevel(logging.WARNING)
        if prompt_for_login_passphrase or prompt_for_login_password:
            connect_kwargs = {}
            if prompt_for_login_password:
                prompt = "Enter login password for SSH auth: "
                connect_kwargs["password"] = getpass(prompt)
            if prompt_for_login_passphrase:
                prompt = "Enter passphrase for unlocking SSH keys: "
                connect_kwargs["passphrase"] = getpass(prompt)
        else:
            connect_kwargs = {}
        self.connection = Connection(
            self.master,
            user=user,
            gateway=None if not proxy else Connection(proxy),
            connect_kwargs=connect_kwargs,
        )
        # follow the same procedure as in fabric main to set the connect_kwargs which feels awkward,
        # we can consider using another library or direct use of ssh through multiprocessing.
        # https://github.com/fabric/fabric/blob/main/fabric/main.py#L151
        self.connection.config._overrides["connect_kwargs"] = connect_kwargs
        # Since we gave merge=False above, we must do it ourselves here. (Also
        # allows us to 'compile' our overrides manipulation.)
        self.connection.config.merge()

    def run(
        self,
        command: str,
        pty: bool = False,
        env: dict | None = None,
        retries: int = 0,
        log_error: bool = True,
    ) -> CommandResult:
        success = False
        num_trial = 1 + retries
        while not success and num_trial > 0:
            try:
                fabric_result = self.connection.run(
                    command=command,
                    hide=True,
                    pty=pty,
                    env=env,
                )
                success = not fabric_result.failed
                # TODO show error when failed
                if fabric_result.failed:
                    if log_error:
                        logging.debug(
                            f"Command {command} failed\n{fabric_result.stderr}"
                        )
            except paramiko.ssh_exception.SSHException as e:
                if log_error:
                    logging.debug(
                        f"Command {command} failed because of connection issue {str(e)}"
                    )
            except socket.gaierror as e:
                logging.error(str(e))
                raise ValueError(
                    f"Could not connect to hostname {self.master}, check your ssh connection."
                )
            if not success:
                time.sleep(1)
                num_trial -= 1
        if success:
            return CommandResult(
                command=command,
                failed=fabric_result.failed,
                return_code=fabric_result.return_code,
                stderr=fabric_result.stderr,
                stdout=fabric_result.stdout,
            )
        else:
            raise ValueError(
                f"Command {command} did not succeed after {retries} trial, consider increasing `retries` argument."
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
            logger.info(
                f"sending {tarpath} ({path_size_human_readable(str(tarpath))}) remotely to {self.connection.host}"
            )
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

    def download_folder(self, remote_path: Path, local_path: Path):
        """
        :param remote_path:
        :param local_path:
        :return:
        """
        # Note, we could also tar the whole thing like we do to send, the reason we pick rsync is that often
        # some files will only be present and rsync allows to not copy those based on hashes
        logger.info(f"Running rsync from {remote_path} to {local_path}")
        command = (
            f"rsync -aPvz {self.user}@{self.master}:{remote_path} {local_path.parent}"
        )
        subprocess.run(command.split(" "), check=True)


if __name__ == "__main__":
    connection = RemoteCommandExecutionFabrik(
        master="YOURCLUSTER",
        user="YOURUSER",
        prompt_for_login_password=True,
        prompt_for_passphrase=False,
    )

    print(connection.run("ls"))
