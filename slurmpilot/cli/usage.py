import argparse
import tarfile
from pathlib import Path

import pandas as pd

from slurmpilot import SlurmPilot
from slurmpilot.callback import format_cluster


def parse_line(keys: list[str], s: str):
    res = dict(zip(keys, s.split("|")[:-1]))
    if "Elapsed" in res:
        n_hours, n_minutes, n_seconds = res["Elapsed"].split(":")
        res["seconds"] = int(n_hours) * 3600 + int(n_minutes) * 60 + int(n_seconds)
    else:
        res["seconds"] = 0

    n_node = int(res["NNodes"])
    #    if "node" in usage_dict:
    # n_node = int(usage_dict["node"])
    n_node = int(res["NNodes"])
    res["seconds"] *= n_node

    if res["AllocTRES"]:
        # Multiply number of seconds by number of nodes and GPUs
        usage_tokens = res["AllocTRES"].split(",")
        usage_dict = {
            token.split("=")[0]: token.split("=")[1] for token in usage_tokens
        }
        if "gres/gpu" in usage_dict:
            n_gpu = int(usage_dict["gres/gpu"])
            res["seconds-gpu"] = n_gpu * res["seconds"]
            res["n-gpu"] = n_gpu
    if "n-gpu" not in res:
        res["n-gpu"] = 0
    # if "NNodes" not in res:
    #     res["NNodes"] = 1
    return res


def parse_file(usage_filename: Path) -> pd.DataFrame:

    with open(usage_filename, "r") as f:
        lines = f.readlines()
    keys = lines[0].split("|")
    rows = [parse_line(keys, line) for line in lines[1:]]
    return pd.DataFrame(rows)


def download_usage_file(download_path: Path, cluster: str):
    # 1) establish connection with remote host
    api = SlurmPilot(clusters=[cluster])
    connection = api.connections[cluster]

    # 2) call sacct on remote machine and dump into compressed result file
    date = "2024-01-01"
    usage_filename = f"usage-{cluster}.txt"
    # we compress the list as it may be big in some cases
    sacct_comand = (
        f"sacct --starttime {date} --format JobName,Start,Elapsed,NNodes,partition,AllocTRES -X  -p > {usage_filename};"
        f"tar -czvf {usage_filename}.tar {usage_filename}"
    )
    connection.run(sacct_comand)

    # 3) copy usage file locally
    usage_local_path = download_path / f"{usage_filename}.tar"
    connection.download_file(f"{usage_filename}.tar", usage_local_path)
    # extract archive in usage_local_path
    with tarfile.open(usage_local_path, "r") as f:
        f.extractall(usage_local_path.parent)
    return download_path / f"usage-{cluster}.txt"


def main():
    parser = argparse.ArgumentParser(
        prog="Usage stat tool",
        description="Tool to compute how much usage was done on clusters.",
    )
    parser.add_argument(
        "--cluster",
        type=str,
        help="Cluster name to be queried",
        required=True,
    )
    parser.add_argument(
        "--download-path",
        type=str,
        help="Path to download the usage file, default to current directory.",
        required=False,
        default=".",
    )
    args = parser.parse_args()
    download_path = Path(args.download_path).expanduser()
    cluster = args.cluster
    print(f"Computing usage on {format_cluster(cluster)}")

    local_path = download_usage_file(download_path, cluster)

    df = parse_file(local_path)

    print(f"Total number of jobs submitted: {len(df)}")

    print(f'Total number of hours (only GPU): {df["seconds-gpu"].sum() / 3600:.2f}')

    print("\nNumber of GPU hours per type of configuration")
    print(
        (
            df[df["n-gpu"] > 0].groupby(["NNodes", "n-gpu"]).sum()["seconds-gpu"] / 3600
        ).to_string()
    )


if __name__ == "__main__":
    main()
