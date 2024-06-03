import tempfile
from pathlib import Path

from slurmpilot.config import Config, load_config, GeneralConfig, ClusterConfig


def test_save_config():
    path = Path("/tmp/foo")
    config = Config(
        general_config=GeneralConfig(local_path="/a", remote_path="/b"),
        cluster_configs={"cluster1": ClusterConfig(host="foo.org", remote_path="~/foo")}
    )
    config.save_to_path(path)
    config_loaded = Config.load_from_path(path=path)
    assert config.general_config == config_loaded.general_config
    assert config.cluster_configs == config_loaded.cluster_configs


user_config = Config(
    general_config=GeneralConfig(local_path="/a", remote_path="/b"),
    cluster_configs={"cluster1": ClusterConfig(host="foo.org", remote_path="~/foo")}
)
code_config = Config(
    general_config=GeneralConfig(local_path="/c", remote_path="/d"),
    cluster_configs={"cluster2": ClusterConfig(host="foo.org", remote_path="~/foo")}
)

def test_load_config():
    # check that configuration can be loaded when both user config and code config are defined
    with tempfile.TemporaryDirectory() as tmpdirname:
        path = Path(tmpdirname)
        user_path = path / "slurmpilot"
        code_path = path / "code"
        user_config.save_to_path(user_path)
        code_config.save_to_path(code_path)
        loaded_config = load_config(user_path=user_path, code_path=code_path)
        assert loaded_config.general_config == user_config.general_config
        merge_config = dict(code_config.cluster_configs, **user_config.cluster_configs)
        assert loaded_config.cluster_configs == merge_config


def test_load_config_user_config_not_defined():
    # check that configuration can be loaded when no user config is defined
    with tempfile.TemporaryDirectory() as tmpdirname:
        path = Path(tmpdirname)
        user_path = path / "slurmpilot"
        code_path = path / "code"
        code_config.save_to_path(code_path)
        loaded_config = load_config(user_path=user_path, code_path=code_path)
        assert loaded_config.general_config == code_config.general_config
        assert loaded_config.cluster_configs == code_config.cluster_configs


def test_load_config_user_general_config_not_defined():
    # check that configuration can be loaded when no user config is defined
    with tempfile.TemporaryDirectory() as tmpdirname:
        path = Path(tmpdirname)
        user_path = path / "slurmpilot"
        code_path = path / "code"
        user_config.general_config = None
        user_config.save_to_path(user_path)
        code_config.save_to_path(code_path)
        loaded_config = load_config(user_path=user_path, code_path=code_path)
        assert loaded_config.general_config == code_config.general_config
        merge_config = dict(code_config.cluster_configs, **user_config.cluster_configs)
        assert loaded_config.cluster_configs == merge_config
