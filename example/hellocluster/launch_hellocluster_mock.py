from launch_program import main

if __name__ == "__main__":
    """
    This example shows how to run a job on a mock cluster, i.e., on your local machine without needing Slurm installed.
    The job will be run as a subprocess on your local machine, and the output will be printed to the console.
    """
    cluster, partition = "mock", None
    main(cluster, partition)
