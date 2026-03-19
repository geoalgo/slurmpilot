from slurmpilot import default_cluster_and_partition
from launch_program import main

if __name__ == "__main__":
    """
    This example shows how to run a job on a remote cluster.
    The cluster and partition will be determined by the default settings in your Slurm configuration.
    """
    cluster, partition = default_cluster_and_partition()
    main(cluster, partition)
