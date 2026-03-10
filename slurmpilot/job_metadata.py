import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class JobMetadata:
    """Persisted metadata written to ``metadata.json`` at scheduling time."""

    jobname: str
    cluster: str
    date: str

    def to_json(self) -> str:
        return json.dumps({"jobname": self.jobname, "cluster": self.cluster, "date": self.date})

    @classmethod
    def from_json(cls, s: str) -> "JobMetadata":
        data = json.loads(s)
        # Support legacy format: jobname nested inside job_creation_info
        if "jobname" not in data and "job_creation_info" in data:
            data["jobname"] = data["job_creation_info"]["jobname"]
        return cls(jobname=data["jobname"], cluster=data["cluster"], date=data["date"])


def list_metadatas(jobs_root: Path) -> list["JobMetadata"]:
    """Return all JobMetadata found under ``jobs_root``, sorted newest-first.

    Uses a manual traversal that stops descending into a directory as soon as
    ``metadata.json`` is found, avoiding redundant scanning of ``logs/``,
    ``src/``, and other subdirectories inside each job folder.
    """
    if not jobs_root.exists():
        return []
    metadatas = []
    stack = [jobs_root]
    while stack:
        cur = stack.pop()
        candidate = cur / "metadata.json"
        if candidate.exists():
            try:
                metadatas.append(JobMetadata.from_json(candidate.read_text()))
            except Exception:
                pass
        else:
            stack.extend(child for child in cur.iterdir() if child.is_dir())
    return sorted(metadatas, key=lambda m: m.date, reverse=True)
