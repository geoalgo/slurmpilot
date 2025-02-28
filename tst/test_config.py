import tempfile
from pathlib import Path

from slurmpilot.config import Config, load_config, GeneralConfig, ClusterConfig


def test_save_config():
    path = Path("/tmp/foo")
    config = Config(
        general_config=GeneralConfig(local_path="/a"),
        cluster_configs={"cluster1": ClusterConfig(host="foo.org", remote_path="~/foo")}
    )
    config.save_to_path(path)
    config_loaded = Config.load_from_path(path=path)
    assert config.general_config == config_loaded.general_config
    assert config.cluster_configs == config_loaded.cluster_configs

