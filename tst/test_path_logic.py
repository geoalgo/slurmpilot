from pathlib import Path

from slurmpilot.jobpath import JobPathLogic

root_path = Path("~/slurmarker").expanduser()


def test_path_logic():
    jobname = "job-1"
    entrypoint = "main.sh"
    src_dir_name = "folder"
    path_logic = JobPathLogic(
        root_path=root_path,
        jobname=jobname,
        entrypoint=entrypoint,
        src_dir_name=src_dir_name,
    )
    assert path_logic.log_path() == root_path / jobname / "logs"
    assert path_logic.stderr_path() == root_path / jobname / "logs" / "stderr"
    assert path_logic.stdout_path() == root_path / jobname / "logs" / "stdout"
    assert path_logic.src_path() == root_path / jobname / src_dir_name
    assert path_logic.slurm_entrypoint_path() == root_path / jobname / "slurm_script.sh"
    assert path_logic.entrypoint_path_from_cwd() == Path(src_dir_name) / entrypoint
