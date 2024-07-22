# Running Locally

We could implement `RemoteExecution` interface to allow to run locally.

This would be especially useful for testing slurmpilot and also for users who want to test locally their code.

A local folder would be passed or a temporary folder would be used.

Mimicking sbatch would be a tad annoying, we would have to run the command given, but also reroute logs. 
For now, we would probably ignore other flags that assign ressources (we could run ray locally but that may be an
overkill for simple testing). 

In particular one needs to emulate the following behavior:

* `sbatch main.sh`
  * creates process that runs bash main.sh
  * returns PID with stdout “Submitted batch job X”
  * (optional but nice) redirect logs to what is written in main.sh
`sacct --jobs=11301195 --format=State -X`
    * returns status from process (check syne tune)


For now all other slurm operations to query status etc could be ignored (we could support them later the way syne tune works).

One would also need to change the interface of SlurmWrapper which right now takes a list of configurations.
* we could either allow to specify a local node as a configuration (could set paths)
* or refactor the code (seems less ideal)


