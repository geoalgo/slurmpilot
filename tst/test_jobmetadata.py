import json

from slurmpilot import JobCreationInfo
from slurmpilot.job_metadata import JobMetadata


def test_jobmetadata_save_load():
    metadata = JobMetadata(
        user="foo",
        date="2023",
        job_creation_info=JobCreationInfo(jobname="job1", entrypoint="foo"),
        cluster="big-cluster",
    )
    json_serialized = metadata.to_json()
    reloaded_metadata = JobMetadata.from_json(json_serialized)
    assert metadata == reloaded_metadata


def test_jobmetadata_load_previous_format():
    # check whether old format can still be read for backward compatibility
    json_str = {
        "user": "foo",
        "date": "2024-11-29 16:23:05.354280",
        "job_creation_info": {
            "jobname": "Helloworld",
            "entrypoint": "hellocluster_script.sh",
            "bash_setup_command": None,
            "src_dir": "./",
            "exp_id": None,
            "sbatch_arguments": None,
            "python_binary": None,
            "python_args": None,
            "python_paths": None,
            "python_libraries": None,
            "cluster": "CLUSTER",
            "partition": "P1",
            "n_cpus": 1,
            "n_gpus": None,
            "mem": None,
            "max_runtime_minutes": 60,
            "account": None,
            "env": {"API_TOKEN": "DUMMY"},
            "nodes": None,
        },
        "cluster": "CLUSTER",
    }
    JobMetadata.from_json(json.dumps(json_str))
