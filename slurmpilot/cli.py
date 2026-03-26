"""Command-line interface for SlurmPilot.

Entry point: ``sp``

Job commands (all take an optional positional jobname, default = latest job):
  log           Print stdout/stderr of a job
  metadata      Print metadata of a job
  status        Print current Slurm state of a job
  stop          Cancel a running job
  path          Show local (and remote) path of a job
  slurm-script  Print the generated Slurm script for a job

Cluster commands:
  list-jobs     Print a table of recent jobs

Launch command:
  launch        Build and submit a job from a YAML config and/or CLI flags
"""
import argparse
import sys
from dataclasses import fields as dc_fields
from pathlib import Path

import yaml

from .config import Config, load_config
from .job_creation_info import JobCreationInfo
from .job_metadata import JobMetadata, list_metadatas
from .job_path import JobPath
from .slurm_script import generate_slurm_script
from .slurmpilot import LOCAL_CLUSTER, MOCK_CLUSTER, SlurmPilot
from .slurmpilot_logging import _cluster, _jobname
from .util import parse_elapsed_minutes, unify

_STATUS_EMOJI = {
    "COMPLETED":     "✅",
    "FAILED":        "❌",
    "RUNNING":       "🏃",
    "PENDING":       "⏳",
    "CANCELLED":     "⚠️",
    "OUT_OF_MEMORY": "🤯",
}


def _status_str(state: str | None) -> str:
    if state is None:
        return "❓ unknown"
    emoji = _STATUS_EMOJI.get(state.split()[0], "❓")
    return f"{emoji} {state}"


def _print_table(rows: list[dict]) -> None:
    """Print a list of dicts as a fixed-width table with a header."""
    if not rows:
        return
    headers = list(rows[0].keys())
    # Compute column widths (ignoring ANSI codes for width)
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row[h])))
    fmt = "  ".join(f"{{:<{widths[h]}}}" for h in headers)
    sep = "  ".join("-" * widths[h] for h in headers)
    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*[str(row[h]) for h in headers]))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_jobname(jobname: str | None, config: Config) -> JobMetadata:
    """Return the JobMetadata for *jobname*, falling back to partial matching.

    If *jobname* is None, returns the most recently submitted job.
    """
    jobs_root = config.local_slurmpilot_path() / "jobs"

    if jobname is None:
        all_jobs = list_metadatas(jobs_root)
        if not all_jobs:
            print("Error: no jobs found.", file=sys.stderr)
            sys.exit(1)
        meta = all_jobs[0]
        print(f"No job specified, using latest: {_jobname(meta.jobname)}", file=sys.stderr)
        return meta

    # Exact match
    jp = JobPath(jobname=jobname, root=config.local_slurmpilot_path())
    if jp.metadata.exists():
        return JobMetadata.from_json(jp.metadata.read_text())

    # Partial match across all known jobs
    matches = [m for m in list_metadatas(jobs_root) if jobname in m.jobname]
    if not matches:
        print(f"Error: no job found matching '{jobname}'", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"Multiple jobs match '{jobname}', using the most recent one:", file=sys.stderr)
        for m in matches:
            print(f"  {m.jobname}", file=sys.stderr)
    return matches[0]


def _make_sp(jobname: str, config: Config) -> tuple[SlurmPilot, str]:
    """Return ``(SlurmPilot, resolved_jobname)`` for the given (possibly partial) jobname."""
    meta = _resolve_jobname(jobname, config)
    return SlurmPilot(config=config, clusters=[meta.cluster]), meta.jobname


# ---------------------------------------------------------------------------
# Command implementations  (each takes (args, config) for easy unit-testing)
# ---------------------------------------------------------------------------

def cmd_log(args: argparse.Namespace, config: Config) -> None:
    sp, jobname = _make_sp(args.jobname, config)
    print(f"Log for {_jobname(jobname)}:")
    stdout, stderr = sp.log(jobname)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)
    if not stdout and not stderr:
        print("(no logs available yet)")


def cmd_metadata(args: argparse.Namespace, config: Config) -> None:
    meta = _resolve_jobname(args.jobname, config)
    print(f"jobname : {_jobname(meta.jobname)}")
    print(f"cluster : {_cluster(meta.cluster)}")
    print(f"date    : {meta.date}")


def cmd_status(args: argparse.Namespace, config: Config) -> None:
    sp, jobname = _make_sp(args.jobname, config)
    state = sp.status([jobname])[0]
    print(state if state is not None else "unknown")


def cmd_download(args: argparse.Namespace, config: Config) -> None:
    meta = _resolve_jobname(args.jobname, config)
    if meta.cluster in ("local", "mock"):
        print(f"Nothing to download: job is on {_cluster(meta.cluster)} (no remote).")
        return
    sp, jobname = _make_sp(args.jobname, config)
    print(f"Downloading {_jobname(jobname)}…")
    sp.download_job(jobname)
    local = sp.local_job_path(jobname)
    print(f"Downloaded to {_jobname(local)}")


def cmd_stop(args: argparse.Namespace, config: Config) -> None:
    sp, jobname = _make_sp(args.jobname, config)
    sp.stop_job(jobname)
    print(f"Job {_jobname(jobname)} stopped.")


def cmd_path(args: argparse.Namespace, config: Config) -> None:
    sp, jobname = _make_sp(args.jobname, config)
    local = sp.local_job_path(jobname)
    remote = sp.remote_job_path(jobname)
    print(f"local  : {_jobname(local)}")
    if remote:
        print(f"remote : {_jobname(remote)}")


def cmd_list_jobs(args: argparse.Namespace, config: Config) -> None:
    jobs_root = config.local_slurmpilot_path() / "jobs"
    metadatas = list_metadatas(jobs_root)

    if args.clusters:
        metadatas = [m for m in metadatas if m.cluster in args.clusters]

    metadatas = metadatas[: args.n]
    if not metadatas:
        print("No jobs found.")
        return

    unique_clusters = list({m.cluster for m in metadatas})
    sp = SlurmPilot(config=config, clusters=unique_clusters)
    infos = sp.sacct_info([m.jobname for m in metadatas])

    rows = []
    seen_jobids: set = set()
    for info in infos:
        if args.collapse_job_array and info["jobid"] in seen_jobids:
            continue
        seen_jobids.add(info["jobid"])
        task_suffix = f" ({info['task_id']})" if info["task_id"] is not None else ""
        rows.append({
            "job":      Path(info["jobname"]).name + task_suffix,
            "jobid":    info["jobid"],
            "cluster":  info["cluster"],
            "creation": info["creation"][:19],
            "min":      f"{parse_elapsed_minutes(info['elapsed']):.1f}",
            "status":   _status_str(info["state"]),
            "nodelist": info["nodelist"],
        })

    rows.sort(key=lambda r: r["creation"], reverse=True)
    _print_table(rows)


def cmd_test_ssh(args: argparse.Namespace, config: Config) -> None:
    clusters = args.clusters
    sp = SlurmPilot(config=config, clusters=clusters)
    for cluster in clusters:
        ok = sp.test_ssh(cluster)
        symbol = "✅" if ok else "❌"
        print(f"{symbol} {_cluster(cluster)}")


def cmd_stop_all(args: argparse.Namespace, config: Config) -> None:
    clusters = args.clusters
    if not clusters:
        # default to all clusters from config
        clusters = list(config.cluster_configs.keys()) or [c for c in
                   SlurmPilot(config=config).clusters]
    sp = SlurmPilot(config=config, clusters=clusters)
    cancelled = sp.stop_all_jobs(clusters)
    if not cancelled:
        print("No jobs to stop.")
    else:
        for jn in cancelled:
            print(f"🛑 stopped {_jobname(jn)}")
        print(f"\n{len(cancelled)} job(s) stopped.")


def cmd_slurm_script(args: argparse.Namespace, config: Config) -> None:
    meta = _resolve_jobname(args.jobname, config)
    jp = JobPath(jobname=meta.jobname, root=config.local_slurmpilot_path())
    if not jp.slurm_script.exists():
        print(f"Error: no slurm script found for job '{meta.jobname}'", file=sys.stderr)
        sys.exit(1)
    print(jp.slurm_script.read_text(), end="")


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

# Fields of JobCreationInfo that can be set via CLI flags (all optional).
_LAUNCH_FIELDS: list[tuple[str, type, str]] = [
    ("--cluster",              str,  "Target cluster"),
    ("--partition",            str,  "Slurm partition"),
    ("--entrypoint",           str,  "Script to run (relative to src-dir)"),
    ("--src-dir",              str,  "Local directory to ship (default: dir of YAML or cwd)"),
    ("--jobname",              str,  "Job name (default: auto-generated from entrypoint)"),
    ("--python-binary",        str,  "Python interpreter"),
    ("--python-args",          str,  "Arguments forwarded to the entrypoint (string)"),
    ("--bash-setup-command",   str,  "Shell command run before the entrypoint"),
    ("--n-cpus",               int,  "CPUs per task"),
    ("--n-gpus",               int,  "GPUs per node"),
    ("--mem",                  int,  "Memory per node in MB"),
    ("--max-runtime-minutes",  int,  "Wall-clock time limit in minutes"),
    ("--account",              str,  "Slurm account"),
    ("--n-concurrent-jobs",    int,  "Max concurrent tasks in a job array"),
    ("--remote-path",          str,  "Override remote slurmpilot root for this job"),
]


def _load_launch_yaml(path: Path) -> dict:
    """Load a launch YAML, resolving relative paths against the YAML's directory."""
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    yaml_dir = path.parent
    # src_dir defaults to the directory that contains the YAML file
    if "src_dir" not in data:
        data["src_dir"] = str(yaml_dir)
    elif not Path(data["src_dir"]).is_absolute():
        data["src_dir"] = str(yaml_dir / data["src_dir"])
    return data


def _build_job_info(args: argparse.Namespace) -> JobCreationInfo:
    """Merge YAML config (if any) with CLI flags to produce a JobCreationInfo.

    Resolution order: defaults < YAML < CLI flags.
    """
    data: dict = {}

    if args.config:
        data = _load_launch_yaml(Path(args.config))

    # CLI flag names are hyphenated; JobCreationInfo uses underscores.
    for flag, *_ in _LAUNCH_FIELDS:
        dest = flag.lstrip("-").replace("-", "_")
        val = getattr(args, dest, None)
        if val is not None:
            data[dest] = val

    # src_dir: fall back to cwd when neither YAML nor flag provided
    if "src_dir" not in data:
        data["src_dir"] = str(Path.cwd())

    # Apply jobname_method: unify(jobname, method=...) — supports "date", "coolname", "ascii"
    jobname_method = data.pop("jobname_method", None) or getattr(args, "jobname_method", None)
    if jobname_method:
        base = data.get("jobname") or Path(data.get("entrypoint", "job")).stem
        data["jobname"] = unify(base, method=jobname_method)
    elif "jobname" not in data or not data["jobname"]:
        entrypoint = data.get("entrypoint", "job")
        data["jobname"] = unify(Path(entrypoint).stem, method="coolname")

    required = {"cluster", "entrypoint"}
    missing = required - data.keys()
    if missing:
        print(f"Error: missing required field(s): {', '.join(sorted(missing))}", file=sys.stderr)
        sys.exit(1)

    # Strip keys not recognised by JobCreationInfo
    valid = {f.name for f in dc_fields(JobCreationInfo)}
    data = {k: v for k, v in data.items() if k in valid}

    return JobCreationInfo(**data)


def cmd_launch(args: argparse.Namespace, config: Config) -> None:
    job_info = _build_job_info(args)

    sp = SlurmPilot(config=config, clusters=[job_info.cluster])

    if args.dry_run:
        job_info.check_path()
        # Generate the script without writing any files, using a temp-like path stub
        local = JobPath(
            jobname=job_info.jobname,
            root=config.local_slurmpilot_path(),
            src_dir_name=Path(job_info.src_dir).resolve().name,
        )
        if job_info.cluster in (MOCK_CLUSTER, LOCAL_CLUSTER):
            job_run_dir = local.job_dir
        else:
            job_run_dir = JobPath(
                jobname=job_info.jobname,
                root=config.remote_slurmpilot_path(job_info.cluster),
            ).job_dir
        script = generate_slurm_script(
            job_info=job_info,
            entrypoint_from_cwd=local.entrypoint_from_cwd(job_info.entrypoint),
            job_run_dir=job_run_dir,
        )
        print(f"# dry-run — job would be submitted as: {_jobname(job_info.jobname)}")
        print(f"# cluster : {_cluster(job_info.cluster)}")
        print(f"# src_dir : {job_info.src_dir}")
        print()
        print(script, end="")
        return

    sp.schedule_job(job_info)

    if args.wait:
        print(f"Waiting for {_jobname(job_info.jobname)} to complete…")
        final_state = sp.wait_completion(job_info.jobname, max_seconds=args.max_wait_seconds)
        print(f"\nFinal status: {_status_str(final_state)}")
        stdout, stderr = sp.log(job_info.jobname)
        if stdout:
            print("\n── stdout ──")
            print(stdout, end="")
        if stderr:
            print("\n── stderr ──", file=sys.stderr)
            print(stderr, end="", file=sys.stderr)


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

_COMMANDS = {
    "log": cmd_log,
    "metadata": cmd_metadata,
    "status": cmd_status,
    "download": cmd_download,
    "stop": cmd_stop,
    "path": cmd_path,
    "slurm-script": cmd_slurm_script,
}

_DESCRIPTIONS = {
    "log": "Print stdout/stderr of a job",
    "metadata": "Print metadata of a job",
    "status": "Print current Slurm state of a job",
    "download": "Download a job folder from the remote cluster",
    "stop": "Cancel a running job",
    "path": "Show local (and remote) path of a job",
    "slurm-script": "Print the generated Slurm script for a job",
    "list-jobs": "Print a table of recent jobs",
    "launch": "Build and submit a job from a YAML config and/or CLI flags",
}


def main(config: Config | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sp", description="SlurmPilot CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in _COMMANDS:
        p = subparsers.add_parser(name, help=_DESCRIPTIONS[name])
        p.add_argument("jobname", nargs="?", default=None, help="Job name (defaults to latest)")

    p = subparsers.add_parser("list-jobs", help=_DESCRIPTIONS["list-jobs"])
    p.add_argument("n", nargs="?", type=int, default=10, help="Number of jobs to show")
    p.add_argument("--clusters", "--cluster", dest="clusters", nargs="+", default=None,
                   metavar="CLUSTER", help="Filter by cluster(s)")
    p.add_argument("--collapse-job-array", action="store_true",
                   help="Show one row per job array instead of one per task")

    p = subparsers.add_parser("test-ssh", help="Test SSH connection to cluster(s)")
    p.add_argument("clusters", nargs="+", metavar="CLUSTER", help="Cluster(s) to test")

    p = subparsers.add_parser("stop-all", help="Stop all tracked jobs on cluster(s)")
    p.add_argument("--clusters", "--cluster", dest="clusters", nargs="+", default=None,
                   metavar="CLUSTER", help="Cluster(s) to stop (defaults to all)")

    p = subparsers.add_parser("launch", help=_DESCRIPTIONS["launch"])
    p.add_argument("--config", metavar="YAML", default=None,
                   help="Path to a job YAML config file")
    for flag, typ, helptext in _LAUNCH_FIELDS:
        p.add_argument(flag, type=typ, default=None, help=f"{helptext} (overrides YAML)")
    p.add_argument("--wait", action="store_true",
                   help="Block until the job completes and print its logs")
    p.add_argument("--max-wait-seconds", type=int, default=86400, dest="max_wait_seconds",
                   metavar="N", help="Timeout for --wait in seconds (default: 86400)")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="Print the generated Slurm script without submitting")
    p.add_argument("--jobname-method", dest="jobname_method", default=None,
                   choices=["date", "coolname", "ascii"],
                   help="Append a unique suffix to jobname: date=timestamp, coolname=random words")

    args = parser.parse_args()
    if config is None:
        config = load_config()
    if args.command == "list-jobs":
        cmd_list_jobs(args, config)
    elif args.command == "test-ssh":
        cmd_test_ssh(args, config)
    elif args.command == "stop-all":
        cmd_stop_all(args, config)
    elif args.command == "launch":
        cmd_launch(args, config)
    else:
        _COMMANDS[args.command](args, config)


if __name__ == "__main__":
    main()
