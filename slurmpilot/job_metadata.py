import dataclasses
import json
from pathlib import Path

from slurmpilot.job_creation_info import JobCreationInfo
from slurmpilot.jobpath import JobPathLogic


@dataclasses.dataclass
class JobMetadata:
    user: str
    date: str
    job_creation_info: JobCreationInfo
    cluster: str

    @property
    def jobname(self):
        return self.job_creation_info.jobname

    def to_json(self) -> str:
        # The methods `to_json` and `from_json` are there because we have nested dataclasses which makes JobMetadata
        # not directly Json serializable
        class EnhancedJSONEncoder(json.JSONEncoder):
            def default(self, o):
                if dataclasses.is_dataclass(o):
                    return dataclasses.asdict(o)
                return super().default(o)

        return json.dumps(self, cls=EnhancedJSONEncoder)

    @classmethod
    def from_json(cls, string) -> "JobMetadata":
        dict_from_string = json.loads(string)
        dict_from_string["job_creation_info"] = JobCreationInfo(
            **dict_from_string.get("job_creation_info")
        )
        return JobMetadata(
            **dict_from_string,
        )


def list_metadatas_files(root: Path):
    # we write a custom code to get all the metadata.json recursively under root
    # the code is custom to avoid searching subdir as soon as we find a metadata.json which is wasteful
    res = []
    to_be_visited = [root]
    while to_be_visited:
        cur = to_be_visited[-1]
        to_be_visited.pop()
        if (cur / "metadata.json").exists():
            res.append(cur / "metadata.json")
        else:
            for child in cur.glob("*"):
                if child.is_dir():
                    to_be_visited.append(child)
    return res


def list_metadatas(root: Path, n_jobs: int | None = None) -> list[JobMetadata]:
    """
    :param root: folder where job metadata are searched recursively
    :param n_jobs:
    :return: the list of all job metadata contains recursively under root, files are sorted by edit time, the first
    file is the most recent.
    """
    files = list_metadatas_files(root=root)
    if n_jobs is not None:
        files = files[:n_jobs]
    jobs = []
    for file in files:
        with open(file, "r") as f:
            try:
                jobmetadata = JobMetadata.from_json(f.read())
                # if job has been moved, then the path would not be consistent, only picks files which have not moved
                local_path = JobPathLogic(jobname=jobmetadata.jobname)
                if local_path.metadata_path().exists():
                    jobs.append(jobmetadata)
            except (json.decoder.JSONDecodeError, TypeError):
                # print(f"Error while reading {file}")
                pass
    # sort by creation time
    return list(sorted(jobs, key=lambda item: item.date, reverse=True))
