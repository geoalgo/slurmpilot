import dataclasses
import json

from slurmpilot.job_creation_info import JobCreationInfo


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
            **dict_from_string["job_creation_info"]
        )
        return JobMetadata(
            **dict_from_string,
        )
