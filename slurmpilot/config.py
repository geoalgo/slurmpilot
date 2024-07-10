import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Dict, List

import yaml

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
config_path = Path(__file__).parent.parent / "config"


class GeneralConfig(NamedTuple):
    # General configurations containing defaults

    # default path where slurmpilot job files are generated
    local_path: str

    # default path where slurmpilot job files are generated on the remote machine, Note: "~" cannot be used
    remote_path: str


@dataclass
class ClusterConfig:
    # Configuration for a cluster, can override default in GeneralConfig
    host: str
    remote_path: str
    account: str | None = None
    user: str | None = None


class Config:
    def __init__(
        self, general_config: GeneralConfig | None = None, cluster_configs: Dict[str, ClusterConfig] | None = None,
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

    def save_to_path(self, path=config_path, clusters: List[str] | None = None):
        path.mkdir(parents=True, exist_ok=True)
        (path / "clusters").mkdir(parents=True, exist_ok=True)
        if self.general_config:
            with open(path / "general.yaml", "w") as f:
                yaml.dump(self.general_config._asdict(), f)
        if clusters is None:
            clusters = self.cluster_configs.keys()
        for cluster in clusters:
            with open(path / "clusters" / f"{cluster}.yaml", "w") as f:
                dict_without_none = {k: v for k, v in self.cluster_configs[cluster].__dict__.items() if v}
                yaml.dump(dict_without_none, f)

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
    if path.exists():
        return ClusterConfig(**load_yaml(path))
    else:
        return None

def load_general_config(path: Path) -> GeneralConfig:
    if path.exists():
        args = load_yaml(path)
        args["local_path"] = str(Path(args["local_path"]).expanduser())
        return GeneralConfig(**load_yaml(path))
    else:
        return None


def load_config(code_path: Path | None = None, user_path: Path | None = None) -> Config:
    # TODO check if duplicate exists, merge
    if code_path is None:
        code_path = Path(__file__).parent.parent / "config"
    code_config = Config.load_from_path(code_path)

    if user_path is None:
        user_path = Path("~/slurmpilot/config").expanduser()
    user_config = Config.load_from_path(user_path)
    general_config = code_config.general_config if user_config.general_config is None else user_config.general_config
    merge_config = dict(code_config.cluster_configs, **user_config.cluster_configs)
    logger.info(f"Loaded cluster configurations {list(merge_config.keys())}.")
    return Config(general_config=general_config, cluster_configs=merge_config)

