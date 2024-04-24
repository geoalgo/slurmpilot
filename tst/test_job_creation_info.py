from slurmpilot.slurm_wrapper import JobCreationInfo


def test_preamble():
    jobinfo = JobCreationInfo(
        jobname="name",
        entrypoint="main.sh",
        src_dir="dummy/slurmpilot/",
        partition="gpu-partition",
        n_cpus=1,
        n_gpus=2,
        mem=100,
        account="unicorn"
    )
    sbatch_preamble = jobinfo.sbatch_preamble().split("\n")
    sbatch_preamble = set(x for x in sbatch_preamble if x)  # remove empty lines

    # ['#SBATCH -p gpu-partition', '#SBATCH --mem 100', '#SBATCH --c 1', '#SBATCH --gres=gpu:2', '']
    expected_preamble_lines = {
        "#SBATCH -J name",
        "#SBATCH -o logs/stdout",
        "#SBATCH -e logs/stderr",
        "#SBATCH -p gpu-partition",
        "#SBATCH -c 1",
        "#SBATCH --gres=gpu:2",
        "#SBATCH --mem 100",
        "#SBATCH -A unicorn"
    }
    for line in expected_preamble_lines:
        assert line in sbatch_preamble
    assert len(sbatch_preamble) == len(expected_preamble_lines)
