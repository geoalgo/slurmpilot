import random
import string
import time


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


def parse_elapsed_minutes(elapsed: str) -> float:
    """Convert a Slurm elapsed string (``[D-]HH:MM:SS``) to minutes."""
    if not elapsed or elapsed == "00:00:00":
        return 0.0
    n_days = 0
    if "-" in elapsed:
        days_part, elapsed = elapsed.split("-", 1)
        n_days = int(days_part)
    parts = elapsed.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return n_days * 1440 + h * 60 + m + s / 60