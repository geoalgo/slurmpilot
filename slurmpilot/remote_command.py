import logging
import socket
import subprocess
import tempfile
import time
import traceback
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
import tarfile

from slurmpilot.callback import format_highlight
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
        :param master: hostname of the remote host which should have slurm available
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


class RemoteCommandExecutionSubprocess(RemoteExecution):
    def __init__(
        self,
        master: str,
        user: str | None = None,
        proxy: str | None = None,
        local_dir: str | Path = None,
    ):
        """
        Calls native unix ssh and scp with subprocesses. Should work reliably as long as ssh and scp works in a terminal
        :param master: hostname of the remote host which should have slurm available
        :param user:
        :param proxy:
        :param local_dir: where logs are written of intermediate commands, if None, use tempdir
        """
        super().__init__(master=master, proxy=proxy, user=user)
        assert (
            proxy is None
        ), "not supported"  # would just need to add the proxy in the ssh/scp call
        self.local_dir = local_dir if local_dir else tempfile.mkdtemp()
        self.local_dir = Path(self.local_dir)

    def run(
        self, command: str, pty: bool = False, env: dict | None = None, retries: int = 0
    ) -> CommandResult:
        command = f"ssh {self._remote_ssh_hostname()} {command}"
        return self._run_shell_command(
            command=command, pty=pty, env=env, retries=retries
        )

    def _run_shell_command(
        self, command: str, pty: bool = False, env: dict | None = None, retries: int = 0
    ) -> CommandResult:
        # TODO specify dir
        with open(self.local_dir / "std.out", "w") as stdout:
            with open(self.local_dir / "std.err", "w") as stderr:
                process = subprocess.Popen(
                    command.split(" "), stderr=stderr, stdout=stdout
                )

        # wait for ssh to be finished, return code is 100 in case of timeout
        code = 100
        for _ in range(20):
            code = process.poll()
            if code is not None:
                break
            time.sleep(1)

        with open(self.local_dir / "std.out", "r") as f:
            stdout = f.read()
        with open(self.local_dir / "std.err", "r") as f:
            stderr = f.read()

        return CommandResult(
            command=command,
            failed=code != 0,
            stderr=stderr,
            stdout=stdout,
            return_code=code,
        )

    def _remote_ssh_hostname(self) -> str:
        # returns a string like salinasd@hostname
        user_str = "" if self.user is None else self.user + "@"
        return f"{user_str}{self.master}"

    def upload_file(self, local_path: Path, remote_path: Path = Path("/")):
        res = self._run_shell_command(
            command=f"scp {local_path} {self._remote_ssh_hostname()}:{remote_path}",
        )
        if res.failed:
            raise ValueError(
                f"Failed to upload {local_path} to {self.master}: {res.stderr}"
            )

    def upload_folder(self, local_path: Path, remote_path: Path = Path("/")):
        # TODO do tar and same as fabrik instead...
        logger.info(
            f"Running rsync from {format_highlight(str(local_path))} to {format_highlight(str(remote_path))}"
        )
        user_prefix = f"{self.user}@" if self.user else ""
        # creates directory as rsync causes an error otherwise, passing --mkpath to rsync would be a cleaner option
        # but this is only supported in recent version of rsync
        self._run_shell_command(
            command=f"ssh {user_prefix}{self.master} mkdir -p {remote_path}"
        )
        # runs rsync
        command = f"rsync -aPvz {local_path} {user_prefix}{self.master}:{remote_path}"
        res = self._run_shell_command(command=command)
        if res.failed:
            logger.warning(
                f"The rsync command did not succeed when copying {local_path} to {self.master}. "
                f"Tried running:\n{command}\nBut got:{res.stdout} {res.stderr}"
            )

    def download_file(self, remote_path: Path, local_path: Path):
        user_str = "" if self.user is None else self.user + "@"
        res = self._run_shell_command(
            command=f"scp {user_str}{self.master}:{remote_path} {local_path}",
        )
        if res.failed:
            raise ValueError(f"Failed to upload {local_path} to {self.master}.")

    def download_folder(self, remote_path: Path, local_path: Path):
        """
        :param remote_path:
        :param local_path:
        :return:
        """
        # Note, we could also tar the whole thing like we do to send, the reason we pick rsync is that often
        # some files will only be present and rsync allows to not copy those based on hashes
        local_path.mkdir(parents=True, exist_ok=True)
        user_prefix = f"{self.user}@" if self.user else ""
        command = (
            f"rsync -aPvz {user_prefix}{self.master}:{remote_path} {local_path.parent}"
        )
        logger.info(
            f"Running rsync from {format_highlight(remote_path)} to {format_highlight(local_path)}.\n{command}"
        )
        self._run_shell_command(command=command)


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
        import paramiko

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
                        logging.info(
                            f"Command {command} failed\n{fabric_result.stderr}"
                        )
            except paramiko.ssh_exception.SSHException as e:
                if log_error:
                    logging.info(
                        f"Command {command} failed because of connection issue {str(e)}"
                    )
            except socket.gaierror as e:
                logging.error(str(e))
                # print trace of e
                print(traceback.format_exc())
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
        logger.info(
            f"Running rsync from {format_highlight(remote_path)} to {format_highlight(local_path)}"
        )
        user_prefix = f"{self.user}@" if self.user else ""
        command = f"rsync -aPvz {user_prefix}{self.master}:{remote_path} {local_path}"
        subprocess.run(command.split(" "), check=True)
