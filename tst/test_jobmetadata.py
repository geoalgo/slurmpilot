from slurmpilot.slurm_wrapper import JobMetadata, JobCreationInfo


def test_jobmetadata_save_load():
    metadata = JobMetadata(
        user="foo",
        date="2023",
        job_creation_info=JobCreationInfo(jobname="job1"),
        cluster="big-cluster",
    )
    json_serialized = metadata.to_json()
    reloaded_metadata = JobMetadata.from_json(json_serialized)
    assert metadata == reloaded_metadata
