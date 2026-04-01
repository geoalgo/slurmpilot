from launch_program import main

if __name__ == "__main__":
    """
    This example shows how to run a job on a local cluster.
    This is useful for submitting your jobs from the same machine that will run the jobs, without needing
    to set up SSH access to a remote cluster. Note that you need to have Slurm installed and configured on
    your local machine for this to work.
    """

    # replace with the name of the partition on your local cluster
    cluster, partition = "local", "YOURPARTITION"
    main(cluster, partition)
