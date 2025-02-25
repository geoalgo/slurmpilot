# CLI

## Not yet implemented

```bash
# list latest 10 jobs only for the given clusters
sp list-jobs 10 --clusters cluster1 cluster2

# expand job-array otherwise, report one job for a given job-array
sp list-jobs 10 --clusters cluster1 cluster2 --expand-job-array

# stop all jobs that are running on the specified clusters
sp stop-all --clusters cluster1 cluster2

# stop all jobs on all available clusters
sp stop-all

# shows the metadata of a given jobname
sp metadata --job jobname
sp show-slurm-script --job jobname

sp launch --jobname helloworld --entrypoint main.py --partition GPUlarge --cluster cloud
```


## List of commands
Features not implemented are denoted with a *.


### Job commands
| Command       | Arguments | What                                 |
|---------------|-----------|--------------------------------------|
| download      | job name  | Download a job locally               |
| path          | job name  | Shows local and remote path of a job |
| log           | job name  | Prints log of a given job            |
| metadata      | job name  | Prints metadata of a given job       |
| slurm-script* | job name  | Shows the slurm script a given job   |
| status        | job name  | Returns status of a given job        |
| stop          | job name  | Stops the given job                  |

### Cluster commands
| Command   | Arguments                             | What                                         |
|-----------|---------------------------------------|----------------------------------------------|
| list-jobs | Num jobs, cluster*, expand-job-array* | Prints a table with information for all jobs |
| test-ssh  | cluster*                              | Test ssh connection                          |
| stop-all* | cluster                               | Stop all jobs                                |

### Other commands
| Command         | Arguments              | What                    |
|-----------------|------------------------|-------------------------|
| install-cluster | cluster, hostname, ... | Install a given cluster |



