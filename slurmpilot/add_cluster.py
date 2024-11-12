import argparse
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from slurmpilot.remote_command import RemoteCommandExecutionFabrik


@dataclass
class ClusterConfiguration:
    name: str
    host: str
    user: str | None = None
    default_partition: str | None = None
    ssh_file: str | None = None
    keep_alive_minute: int | None = None
    account: str | None = None

    def ssh_string(self) -> str:
        s = "# Added by slurmpilot\n"
        s += f"Host {self.name}\n"
        s += f"  HostName {self.host}\n"
        if self.ssh_file is not None:
            s += f"  IdentityFile {self.ssh_file}\n"
        if self.user is not None:
            s += f"  User {self.user}\n"
        if self.keep_alive_minute is not None:
            s += f"  ControlMaster auto\n"
            s += f"  ControlPath ~/.ssh/ssh_%h_%p_%r\n"
            s += f"  ControlPersist {self.keep_alive_minute}m\n"
        s += "\n\n"
        return s

    def slurmpilot_string(self) -> str:
        slurmpilot_keys = ["name", "default_partition", "account"]
        config_dict = {k: self.__dict__[k] for k in slurmpilot_keys}
        config_dict = {k: v for k, v in config_dict.items() if v}
        config_dict["host"] = config_dict["name"]
        config_dict.pop("name")
        # convert `config_dict` to a yaml string
        s = yaml.dump(config_dict, indent=4)
        return s


def install_cluster(configuration: ClusterConfiguration):
    cluster = configuration.name

    # TODO this would only works on linux/macos, probably not on windows.
    # 1) add ssh configuration
    ssh_config_path = Path("~/.ssh/config").expanduser()

    if not ssh_config_path.exists():
        ssh_config_path.touch(exist_ok=True)

    # checks if f"Host {cluster}" is already present in `f`
    with open(ssh_config_path, "r") as f:
        config_contains_host = any([line.startswith(f"Host {cluster}") for line in f])

    if config_contains_host:
        print(
            f"Not adding ssh configuration for {cluster} since it was found already. "
            f"If you want to update the ssh configuration, please remove the existing entry from {ssh_config_path}."
        )
    else:
        print(f"Adding ssh configuration for {cluster} in {ssh_config_path}")
        print(f"The following is going to be added:\n{configuration.ssh_string()}")
        with open(ssh_config_path, "a") as f:
            f.write(configuration.ssh_string())

    # 2) add slurmpilot configuration
    slurmpilot_config_path = Path(
        f"~/slurmpilot/config/clusters/{cluster}.yaml"
    ).expanduser()
    slurmpilot_config_path.parent.mkdir(exist_ok=True, parents=True)
    with open(slurmpilot_config_path, "w") as f:
        print(
            f"Adding slurmpilot configuration for {cluster} in {slurmpilot_config_path}"
        )
        print(
            f"The following is going to be added:\n{configuration.slurmpilot_string()}"
        )
        f.write(configuration.slurmpilot_string())


def check_ssh_connection(configuration: ClusterConfiguration):
    print(f"Trying ssh connection to {configuration.name}.")
    remote_connection = RemoteCommandExecutionFabrik(
        master=configuration.name,
        user=configuration.user,
    )
    try:
        print(f'> ssh {configuration.name} "ls"')
        print(remote_connection.run("ls", pty=True).stdout)
        print(
            f"✅ SSH connection to {configuration.name} is successful, enjoy the cluster!"
        )
    except Exception as e:
        print(f"❌ SSH connection to {configuration.name} failed: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        prog="Install cluster tool",
        description="Tool that adds ssh configuration and slurmpilot configuration for a cluster",
    )
    parser.add_argument(
        "--cluster",
        type=str,
        help="Cluster name to be installed",
        required=True,
    )
    parser.add_argument(
        "--host",
        type=str,
        help="Hostname of the cluster, the machine should have slurm installed.",
        required=True,
    )
    parser.add_argument(
        "--user",
        type=str,
        help="Name for the user on the remote machine",
        default=os.getenv("USER"),
        required=False,
    )
    parser.add_argument(
        "--ssh-file",
        type=str,
        help="Name for an ssh key file",
        required=False,
    )
    parser.add_argument(
        "--keep-alive-minute",
        type=int,
        help="Time to keep alive the ssh connection.",
        required=False,
    )
    parser.add_argument(
        "--remote-path",
        type=int,
        help="Folder where slurmpilot writes experiments on the remote host.",
        required=False,
    )
    parser.add_argument(
        "--default-partition",
        type=str,
        help="Default partition to use.",
        required=False,
    )
    parser.add_argument(
        "--account",
        type=str,
        help="Default account to use on slurm, passed with --account when calling sbatch.",
        required=False,
    )
    parser.add_argument(
        "--check-ssh-connection",
        help="Test ssh connection after configuring host.",
        action=argparse.BooleanOptionalAction,
    )
    args = parser.parse_args()

    print(f"Installing cluster with options {args.__dict__}")
    if args.ssh_file is not None:
        args.ssh_file = Path(args.ssh_file).expanduser()
        assert Path(
            args.ssh_file
        ).exists(), f"SSH key file {args.ssh_file} does not exist."

    configuration = ClusterConfiguration(
        name=args.cluster,
        host=args.host,
        user=args.user,
        default_partition=args.default_partition,
        ssh_file=args.ssh_file,
        keep_alive_minute=args.keep_alive_minute,
        account=args.account,
    )
    print(f"Installing user-configured cluster {args.cluster}: {configuration}")
    install_cluster(configuration)

    if args.check_ssh_connection:
        check_ssh_connection(configuration)


if __name__ == "__main__":
    main()
