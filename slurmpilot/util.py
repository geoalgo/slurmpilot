import os
import random
import string
import time
from contextlib import contextmanager
from time import perf_counter
from typing import Tuple


@contextmanager
def catchtime(name: str, logger=None) -> float:
    start = perf_counter()
    print_fun = print if logger is None else logger.info
    try:
        print_fun(f"start: {name}")
        yield lambda: perf_counter() - start
    finally:
        print_fun(f"Time for {name}: {perf_counter() - start:.4f} secs")


def unify(name: str, method: str = "date") -> str:
    """
    :param name:
    :param method:
    :return: a name likely to be unique obtained by adding a random suffix or a time-stamp depending on the method
    """
    assert method in ["ascii", "coolname", "date"]
    if method == "ascii":
        suffix = "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(5)
        )
    elif method == "coolname":
        from coolname import generate_slug

        suffix = generate_slug()
    else:
        suffix = time.strftime("%Y-%m-%d-%H-%M-%S")
    return name + "-" + suffix


def print_table(rows):
    if len(rows) > 0:
        import pandas as pd

        print(pd.DataFrame(rows).set_index("JobName").to_string())


def path_size_human_readable(path: str) -> str:
    size = os.path.getsize(path)
    if size < 1024:
        return f"{size} bytes"
    elif size < 1024**2:
        return f"{size / 1024:.2f} KB"
    elif size < 1024**3:
        return f"{size / 1024 ** 2:.2f} MB"
    elif size < 1024**4:
        return f"{size / 1024 ** 3:.2f} GB"
