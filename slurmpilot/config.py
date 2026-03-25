import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("~/slurmpilot/config")


@dataclass
class ClusterConfig:
    host: str
    user: str | None = None
    account: str | None = None
    remote_path: str = "~/slurmpilot"
    default_partition: str | None = None


class Config:
    def __init__(
        self,
        local_path: str | Path | None = None,
        cluster_configs: dict[str, ClusterConfig] | None = None,
        default_cluster: str | None = None,
    ):
        if local_path is None:
            local_path = Path("~/slurmpilot").expanduser()
        self._local_path = Path(local_path)
        self.cluster_configs = cluster_configs or {}
        self.default_cluster = default_cluster

    def local_slurmpilot_path(self) -> Path:
        return self._local_path.expanduser()

    def remote_slurmpilot_path(self, cluster: str) -> Path:
        if cluster in self.cluster_configs:
            return Path(self.cluster_configs[cluster].remote_path)
        return Path("~/slurmpilot")


def load_config(path: Path | None = None) -> Config:
    """Load a :class:`Config` from YAML files on disk.

    Directory layout::

        {path}/
          general.yaml            # optional; keys: local_path, default_cluster
          clusters/
            {cluster}.yaml        # one file per cluster; keys match ClusterConfig fields

    :param path: config directory. Defaults to ``~/slurmpilot/config``.
    """
    if path is None:
        path = DEFAULT_CONFIG_PATH.expanduser()
    path = Path(path).expanduser()

    local_path, default_cluster = _load_general(path / "general.yaml")
    cluster_configs = _load_clusters(path / "clusters")

    logger.info(f"Loaded cluster configurations: {', '.join(cluster_configs) or '(none)'}.")
    return Config(
        local_path=local_path,
        cluster_configs=cluster_configs,
        default_cluster=default_cluster,
    )


def default_cluster_and_partition(config: Config | None = None) -> tuple[str, str]:
    """Return ``(cluster, partition)`` from config or the ``SP_DEFAULT_CLUSTER`` env var.

    Resolution order:
    1. ``SP_DEFAULT_CLUSTER`` environment variable (cluster must exist in config).
    2. ``config.default_cluster``.

    The chosen cluster must have ``default_partition`` set in its :class:`ClusterConfig`.
    """
    if config is None:
        config = load_config()
    cluster = os.environ.get("SP_DEFAULT_CLUSTER") or config.default_cluster
    if cluster is None:
        raise ValueError(
            "No default cluster configured. Set the SP_DEFAULT_CLUSTER environment "
            "variable or pass default_cluster to Config."
        )
    if cluster not in config.cluster_configs:
        raise ValueError(
            f"Default cluster '{cluster}' not found in config. "
            f"Available clusters: {list(config.cluster_configs)}"
        )
    partition = config.cluster_configs[cluster].default_partition
    if partition is None:
        raise ValueError(
            f"Cluster '{cluster}' has no default_partition set in its ClusterConfig."
        )
    return cluster, partition


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _load_general(path: Path) -> tuple[str | None, str | None]:
    """Return (local_path, default_cluster) from general.yaml, or (None, None) if missing."""
    if not path.exists():
        return None, None
    data = _load_yaml(path)
    local_path = data.get("local_path")
    if local_path is not None:
        local_path = str(Path(local_path).expanduser())
    return local_path, data.get("default_cluster")


def _load_clusters(clusters_dir: Path) -> dict[str, ClusterConfig]:
    if not clusters_dir.exists():
        return {}
    configs = {}
    for yaml_path in sorted(clusters_dir.rglob("*.yaml")):
        name = yaml_path.stem
        try:
            configs[name] = ClusterConfig(**_load_yaml(yaml_path))
        except TypeError as e:
            raise ValueError(f"Invalid cluster config {yaml_path}: {e}")
    return configs
