from pathlib import Path

import pytest
import yaml

from slurmpilot.config import ClusterConfig, Config, default_cluster_and_partition, load_config


def make_config(**kwargs) -> Config:
    return Config(
        local_path="/tmp/sp",
        cluster_configs={
            "mycluster": ClusterConfig(host="login.hpc.org", default_partition="gpu"),
            "other": ClusterConfig(host="other.hpc.org"),
        },
        **kwargs,
    )


class TestDefaultClusterAndPartition:
    def test_uses_default_cluster_from_config(self):
        config = make_config(default_cluster="mycluster")
        cluster, partition = default_cluster_and_partition(config)
        assert cluster == "mycluster"
        assert partition == "gpu"

    def test_env_var_overrides_config_default(self, monkeypatch):
        monkeypatch.setenv("SP_DEFAULT_CLUSTER", "mycluster")
        config = make_config(default_cluster=None)
        cluster, partition = default_cluster_and_partition(config)
        assert cluster == "mycluster"
        assert partition == "gpu"

    def test_env_var_takes_priority_over_config_default(self, monkeypatch):
        monkeypatch.setenv("SP_DEFAULT_CLUSTER", "mycluster")
        # default_cluster points elsewhere but env var wins
        config = Config(
            local_path="/tmp/sp",
            cluster_configs={
                "mycluster": ClusterConfig(host="a.org", default_partition="gpu"),
                "fallback": ClusterConfig(host="b.org", default_partition="cpu"),
            },
            default_cluster="fallback",
        )
        cluster, partition = default_cluster_and_partition(config)
        assert cluster == "mycluster"

    def test_no_default_raises(self, monkeypatch):
        monkeypatch.delenv("SP_DEFAULT_CLUSTER", raising=False)
        config = make_config(default_cluster=None)
        with pytest.raises(ValueError, match="No default cluster"):
            default_cluster_and_partition(config)

    def test_unknown_cluster_raises(self, monkeypatch):
        monkeypatch.setenv("SP_DEFAULT_CLUSTER", "nonexistent")
        config = make_config(default_cluster=None)
        with pytest.raises(ValueError, match="not found in config"):
            default_cluster_and_partition(config)

    def test_missing_partition_raises(self):
        config = Config(
            local_path="/tmp/sp",
            cluster_configs={"other": ClusterConfig(host="other.hpc.org")},
            default_cluster="other",
        )
        with pytest.raises(ValueError, match="no default_partition"):
            default_cluster_and_partition(config)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

def write_general(path: Path, **kwargs):
    path.write_text(yaml.dump(kwargs))


def write_cluster(clusters_dir: Path, name: str, **kwargs):
    clusters_dir.mkdir(parents=True, exist_ok=True)
    (clusters_dir / f"{name}.yaml").write_text(yaml.dump(kwargs))


class TestLoadConfig:
    def test_empty_directory_returns_defaults(self, tmp_path):
        config = load_config(tmp_path)
        assert config.cluster_configs == {}
        assert config.default_cluster is None

    def test_missing_directory_returns_defaults(self, tmp_path):
        config = load_config(tmp_path / "nonexistent")
        assert config.cluster_configs == {}

    def test_loads_local_path_from_general_yaml(self, tmp_path):
        write_general(tmp_path / "general.yaml", local_path=str(tmp_path / "jobs"))
        config = load_config(tmp_path)
        assert config.local_slurmpilot_path() == tmp_path / "jobs"

    def test_expands_tilde_in_local_path(self, tmp_path):
        write_general(tmp_path / "general.yaml", local_path="~/slurmpilot")
        config = load_config(tmp_path)
        assert "~" not in str(config.local_slurmpilot_path())

    def test_loads_default_cluster_from_general_yaml(self, tmp_path):
        write_general(tmp_path / "general.yaml", default_cluster="gpu_cluster")
        config = load_config(tmp_path)
        assert config.default_cluster == "gpu_cluster"

    def test_loads_cluster_host(self, tmp_path):
        write_cluster(tmp_path / "clusters", "mycluster", host="login.hpc.org")
        config = load_config(tmp_path)
        assert "mycluster" in config.cluster_configs
        assert config.cluster_configs["mycluster"].host == "login.hpc.org"

    def test_loads_all_cluster_fields(self, tmp_path):
        write_cluster(
            tmp_path / "clusters", "gpu",
            host="gpu.hpc.org",
            user="alice",
            account="proj123",
            remote_path="~/slurmpilot",
            default_partition="gpu",
        )
        config = load_config(tmp_path)
        c = config.cluster_configs["gpu"]
        assert c.user == "alice"
        assert c.account == "proj123"
        assert c.default_partition == "gpu"

    def test_loads_multiple_clusters(self, tmp_path):
        clusters_dir = tmp_path / "clusters"
        write_cluster(clusters_dir, "cpu", host="cpu.hpc.org")
        write_cluster(clusters_dir, "gpu", host="gpu.hpc.org")
        config = load_config(tmp_path)
        assert set(config.cluster_configs) == {"cpu", "gpu"}

    def test_general_yaml_missing_is_fine(self, tmp_path):
        write_cluster(tmp_path / "clusters", "mycluster", host="h.org")
        config = load_config(tmp_path)
        assert "mycluster" in config.cluster_configs

    def test_defaults_to_home_slurmpilot_config_when_no_path(self, monkeypatch, tmp_path):
        # Redirect the default path so we don't touch the real ~/.slurmpilot/config.
        monkeypatch.setattr("slurmpilot.config.DEFAULT_CONFIG_PATH", tmp_path)
        write_cluster(tmp_path / "clusters", "cl", host="h.org")
        config = load_config()
        assert "cl" in config.cluster_configs

    def test_invalid_cluster_yaml_raises(self, tmp_path):
        clusters_dir = tmp_path / "clusters"
        clusters_dir.mkdir()
        (clusters_dir / "bad.yaml").write_text(yaml.dump({"unknown_field": "x"}))
        with pytest.raises(ValueError, match="Invalid cluster config"):
            load_config(tmp_path)

    def test_remote_slurmpilot_path_uses_cluster_config(self, tmp_path):
        write_cluster(tmp_path / "clusters", "cl", host="h.org", remote_path="~/mypath")
        config = load_config(tmp_path)
        assert "mypath" in str(config.remote_slurmpilot_path("cl"))
