import json
from pathlib import Path
from typing import NamedTuple, Dict, List

import yaml

config_path = Path(__file__).parent.parent / "config"


class GeneralConfig(NamedTuple):
    # General configurations containing defaults

    # default path where slurmpilot job files are generated
    local_path: str

    # default path where slurmpilot job files are generated on the remote machine, Note: "~" cannot be used
    remote_path: str


class ClusterConfig(NamedTuple):
    # Configuration for a cluster, can override default in GeneralConfig
    host: str
    remote_path: str
    account: str | None = None


class Config:
    def __init__(
        self, general_config: GeneralConfig, cluster_configs: Dict[str, ClusterConfig] | None = None,
    ):
        self.general_config = general_config
        self.cluster_configs = cluster_configs if cluster_configs is not None else {}

    @classmethod
    def load_from_path(cls, path=config_path, clusters: List[str] | None = None):
        general_config = load_general_config(path / "general.yaml")
        cluster_configs = {
            cluster_config_path.stem: load_cluster_config(cluster_config_path)
            for cluster_config_path in (path / "clusters").rglob("*.yaml")
            if clusters is None or cluster_config_path.stem in clusters
        }
        return cls(general_config, cluster_configs)

    def __str__(self):
        res = {
            "general_config": self.general_config,
            "cluster_configs": "\n".join(
                [f"{k}: {v}" for k, v in self.cluster_configs.items()]
            ),
        }
        return json.dumps(res, indent=4)

    def local_slurmpilot_path(self) -> Path:
        return Path(self.general_config.local_path).expanduser()

    def remote_slurmpilot_path(self, cluster: str) -> Path:
        remote_path = self.cluster_configs[cluster].remote_path
        if remote_path is None:
            remote_path = self.general_config.remote_path
        return Path(remote_path)


def load_yaml(path: Path) -> dict:
    with open(path, "r") as stream:
        return yaml.safe_load(stream)


def load_cluster_config(path: Path) -> ClusterConfig:
    return ClusterConfig(**load_yaml(path))


def load_general_config(path: Path) -> GeneralConfig:
    args = load_yaml(path)
    args["local_path"] = str(Path(args["local_path"]).expanduser())
    return GeneralConfig(**load_yaml(path))
