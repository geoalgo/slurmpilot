from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from pandas._libs.tslibs.parsing import DateParseError

from slurmpilot.job_metadata import JobMetadata
from slurmpilot.remote_command import RemoteExecution
from slurmpilot.util import parse_nseconds_slurm_status


class SlurmJobStatus:
    completed: str = "COMPLETED"
    pending: str = "PENDING"
    failed: str = "FAILED"
    running: str = "RUNNING"
    cancelled: str = "CANCELLED"
    timeout: str = "TIMEOUT"
    out_of_memory: str = "OUT_OF_MEMORY"

    def statuses(self):
        return [self.completed, self.pending, self.failed, self.running, self.cancelled]


@dataclass
class SlurmJobInfo:
    jobname: str
    cluster: str
    JobID: str
    task_id: int | None  # for job-array
    Elapsed: str
    creation: str
    Start: datetime
    State: str
    NodeList: str


def job_infos(
    connections, jobid_from_jobname, jobnames: list[str]
) -> list[SlurmJobInfo]:
    if not isinstance(jobnames, list):
        assert isinstance(jobnames, str)
        jobnames = [jobnames]

    # first, we build a dictionary mapping clusters to job information
    jobid_mapping = {}
    clusters = defaultdict(list)
    for jobname in jobnames:
        # TODO support having this one missing (
        jobid = jobid_from_jobname(jobname)
        jobid_mapping[jobid] = jobname
        job_metadata = JobMetadata.from_jobname(jobname)
        if job_metadata is not None:
            cluster = job_metadata.cluster
            if jobid is not None:
                clusters[cluster].append((jobid, job_metadata))

    # second, we call sacct on each clusters with the corresponding jobs
    rows = []
    for cluster in clusters.keys():
        job_clusters = clusters[cluster]
        # filter jobs with missing jobid
        job_and_ids = [
            (job_metadata, jobid)
            for (jobid, job_metadata) in job_clusters
            if jobid is not None
        ]
        rows += call_and_parse_sacct(
            cluster=cluster,
            job_and_ids=job_and_ids,
            connections=connections,
        )
    return list(sorted(rows, key=lambda x: x.creation, reverse=True))


def call_and_parse_sacct(
    connections: dict[str, RemoteExecution],
    cluster: str,
    job_and_ids: list[JobMetadata, int],
) -> list[SlurmJobInfo]:
    # calls sacct on the requested jobids for a given cluster
    jobinfos, jobids = zip(*job_and_ids)
    jobid_mapping = {jobid: job for job, jobid in job_and_ids}
    sacct_format = "JobID,Elapsed,start,State,nodelist"
    job_ids = ",".join([str(x) for x in jobids])
    try:
        cmd_res = connections[cluster].run(
            f'sacct --format="{sacct_format}" -X -p --jobs={job_ids}'
        )
    except (KeyError, ValueError) as e:
        return []
    sacct_string = cmd_res.stdout

    # parse sacct_string
    lines = sacct_string.split("\n")
    keys = lines[0].split("|")[:-1]
    rows = []
    for line in lines[1:]:
        if len(line) > 0:
            kwargs = dict(zip(keys, line.split("|")))
            if "JobID" in kwargs:
                slurm_jobid = kwargs.get("JobID")
                if "_" in slurm_jobid:
                    parent_jobid, task_id = kwargs.get("JobID").split("_")
                    try:
                        task_id = int(task_id)
                    except ValueError:
                        task_id = None
                else:
                    parent_jobid = kwargs.get("JobID")
                    task_id = None
                jobinfo = jobid_mapping.get(int(parent_jobid))
                try:
                    kwargs["Start"] = pd.to_datetime(kwargs["Start"]).strftime(
                        "%d/%m/%y-%H:%M"
                    )
                except DateParseError:
                    kwargs["Start"] = None
                rows.append(
                    SlurmJobInfo(
                        jobname=jobinfo.jobname,
                        task_id=task_id,
                        cluster=cluster,
                        creation=jobinfo.date,
                        **kwargs,
                    )
                )
    return rows


def print_jobs(
    jobinfos: list[SlurmJobInfo],
    n_jobs: int = 10,
    max_colwidth: int = 50,
    status_verbose: bool = True,
):
    rows = []
    print("Calling remote sacct on remote nodes to get status.")

    for jobinfo in jobinfos:
        status = jobinfo.State
        # TODO status when missing jobid.json => error at launching
        if status is None:
            status_symbol = "Unknown slurm status 🏝"
        else:
            status_mapping = {
                SlurmJobStatus.out_of_memory: "OOM 🤯",
                SlurmJobStatus.failed: "Job failed ❌",
                SlurmJobStatus.pending: "Pending ⏳",
                SlurmJobStatus.running: "️Running 🏃",
                SlurmJobStatus.completed: "Completed ✅",
                SlurmJobStatus.cancelled: "Canceled ⚠️",
            }
            if "CANCELLED" in status:
                status_symbol = "Cancelled ⚠️"
            else:
                status_symbol = status_mapping.get(status, f"Unknown state: {status}")
        n_seconds = parse_nseconds_slurm_status(jobinfo.Elapsed)
        task_id = "" if jobinfo.task_id is None else f" ({jobinfo.task_id})"
        # right now, results are provided sorted by creation date and then invert taskid
        # TODO we should support not listing all tasks of a job-array
        rows.append(
            {
                "job": Path(jobinfo.jobname).name + task_id,
                "cluster": jobinfo.cluster,
                "creation": jobinfo.creation,
                "min": f"{n_seconds / 60.:.1f}",
                "status": (
                    f"{status_symbol} " if status_verbose else f"{status_symbol[-1:]} "
                ),
                "NodeList": jobinfo.NodeList,
                # "full jobname": jobinfo.jobname,
            }
        )
    if n_jobs is not None:
        rows = rows[:n_jobs]
    df = pd.DataFrame(rows)
    print(
        df.to_string(
            index=False,
            max_colwidth=max_colwidth,
        )
    )
