import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Dict, List, Tuple

import yaml

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
config_path = Path("~/slurmpilot/config").expanduser()


class GeneralConfig(NamedTuple):
    # General configurations containing defaults

    # default path where slurmpilot job files are generated
    local_path: str = str(Path("~/slurmpilot").expanduser())

    # default cluster to be used, must have a file `config/clusters/{default_cluster}.yaml` associated
    default_cluster: str | None = None


@dataclass
class ClusterConfig:
    # Configuration for a cluster, can override default in GeneralConfig
    host: str
    remote_path: str = "slurmpilot/"
    account: str | None = None
    user: str | None = None
    default_partition: str | None = None


class Config:
    def __init__(
        self,
        general_config: GeneralConfig,
        cluster_configs: Dict[str, ClusterConfig] | None = None,
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
                dict_without_none = {
                    k: v for k, v in self.cluster_configs[cluster].__dict__.items() if v
                }
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

    def remote_slurmpilot_path(self, cluster: str | None = None) -> Path:
        # first look at cluster config, then general config then default
        if cluster in self.cluster_configs:
            return Path(self.cluster_configs[cluster].remote_path)
        else:
            return Path(ClusterConfig.remote_path)


def load_yaml(path: Path) -> dict:
    with open(path, "r") as stream:
        return yaml.safe_load(stream)


def load_cluster_config(path: Path) -> ClusterConfig:
    if path.exists():
        try:
            return ClusterConfig(**load_yaml(path))
        except TypeError as e:
            raise ValueError(f"Could not read configuration in {path}: {str(e)}")
    else:
        return None


def load_general_config(path: Path) -> GeneralConfig:
    if path.exists():
        args = load_yaml(path)
        if "local_path" in args:
            args["local_path"] = str(Path(args["local_path"]).expanduser())
        return GeneralConfig(**load_yaml(path))
    else:
        return None


def load_config(user_path: Path | None = None) -> Config:
    """
    :param user_path:
    :return: loads configuration by default from ~/slurmpilot/config unless `user_path` is specified.
    """
    if user_path is None:
        user_path = Path("~/slurmpilot/config").expanduser()
    user_config = Config.load_from_path(user_path)

    general_config = user_config.general_config
    if general_config is None:
        general_config = GeneralConfig(
            local_path="~/slurmpilot"
        )

    logger.info(
        f'Loaded cluster configurations {", ".join(user_config.cluster_configs.keys())}.'
    )
    return Config(
        general_config=general_config, cluster_configs=user_config.cluster_configs
    )


def default_cluster_and_partition(user_path: Path | None = None) -> Tuple[str, str]:
    """
    :param user_path:
    :return: default cluster and partition. The values should be specified in "~/slurmpilot/general.yaml" for
    `default_cluster` and the default partition should be specified in the cluster config with
    "~/slurmpilot/configs/{default_cluster}.yaml". Alternatively, one can also specify the default cluster with the
    environment variable "SP_DEFAULT_CLUSTER".
    """
    # We have a couple of options, we could
    # 1) load the configuration and take the first cluster (assuming it has a default partition field)
    # 2) load an environment variable DEFAULT_CLUSTER
    config = load_config(user_path=user_path)

    if "SP_DEFAULT_CLUSTER" in os.environ:
        cluster = os.getenv("SP_DEFAULT_CLUSTER")
        assert cluster in config.cluster_configs
        # TODO add partition to cluster config
        partition = config.cluster_configs[cluster].default_partition
    else:
        cluster = config.general_config.default_cluster
        assert cluster is not None, (
            "To be able to use a default cluster, you need to set the environment variable $SP_DEFAULT_CLUSTER to the "
            "desired cluster or alternatively to add `default_cluster` to general.yaml"
        )
        partition = config.cluster_configs[cluster].default_partition

    assert (
        partition is not None
    ), f"Cannot use default cluster {cluster} without default partition, provide it in {cluster}.yaml"
    return cluster, partition
