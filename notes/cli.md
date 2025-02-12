# CLI

## Not yet implemented

```bash
# list latest 10 jobs only for the given clusters
sp --list-jobs 10 --clusters cluster1 cluster2

# expand job-array otherwise, report one job for a given job-array
sp --list-jobs 10 --clusters cluster1 cluster2 --expand-job-array

# stop all jobs that are running on the specified clusters
sp --stop-all --clusters cluster1 cluster2

# stop all jobs on all available clusters
sp --stop-all

# shows the metadata of a given jobname
sp --metadata jobname
```

