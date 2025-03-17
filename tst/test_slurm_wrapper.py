import logging
import tempfile
from pathlib import Path

from slurmpilot.config import GeneralConfig, Config
from slurmpilot import SlurmPilot, JobCreationInfo


def generate_local_script(src_dir: Path, entrypoint: str):
    src_dir.mkdir(parents=True, exist_ok=True)
    with open(src_dir / entrypoint, "w") as f:
        f.write('echo "coucou"\n')


def test_schedule_job():
    logging.basicConfig(level=logging.INFO)
    src_dir = "script"
    entrypoint = "launch.sh"
    jobname = "job-1"
    with tempfile.TemporaryDirectory() as tmpdirname:
        local_slurmpilot_path = tmpdirname
        generate_local_script(src_dir=Path(src_dir), entrypoint=entrypoint)
        config = Config(
            general_config=GeneralConfig(local_path=local_slurmpilot_path),
        )
        slurm = SlurmPilot(
            clusters=[],
            config=config,
        )
        jobinfo = JobCreationInfo(
            jobname=jobname,
            entrypoint=entrypoint,
            src_dir=src_dir,
            partition="foo",
            mem=1,
            n_cpus=1,
        )
        jobinfo.check_path()
        # generate slurm launcher script in slurmpilot dir
        local_job_paths = slurm._generate_local_folder(jobinfo)

        # checks expected files exist
        assert local_job_paths.resolve_path().exists()
        assert local_job_paths.slurm_entrypoint_path().exists()
        assert local_job_paths.src_path().exists()
        assert local_job_paths.metadata_path().exists()

        # TODO we could check that the metadata are as we expect
