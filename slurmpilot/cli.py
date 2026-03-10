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
"""
import argparse
import sys
from pathlib import Path

from config import Config, load_config
from job_metadata import JobMetadata, list_metadatas
from job_path import JobPath
from slurmpilot import SlurmPilot
from slurmpilot_logging import _cluster, _jobname
from util import parse_elapsed_minutes

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

    args = parser.parse_args()
    if config is None:
        config = load_config()
    if args.command == "list-jobs":
        cmd_list_jobs(args, config)
    elif args.command == "test-ssh":
        cmd_test_ssh(args, config)
    elif args.command == "stop-all":
        cmd_stop_all(args, config)
    else:
        _COMMANDS[args.command](args, config)


if __name__ == "__main__":
    main()
