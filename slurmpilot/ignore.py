"""Gitignore-style filtering for files copied into the staging job folder.

Patterns are read from a ``.gitignore`` file at the root of each source
directory (``src_dir`` and each ``python_libraries`` entry). Sub-directory
``.gitignore`` files are not consulted.
"""

from pathlib import Path

import pathspec

IGNORE_FILENAME = ".gitignore"


def _load_gitignore(directory: Path) -> list[str]:
    path = directory / IGNORE_FILENAME
    if not path.exists():
        return []
    return path.read_text().splitlines()


def make_ignore(root: Path):
    """Return a ``shutil.copytree``-compatible ignore callable.

    Patterns are read from ``root/.gitignore``.
    """
    patterns = _load_gitignore(root)

    spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def ignore(src: str, names: list[str]) -> set[str]:
        src_path = Path(src)
        rel_dir = src_path.relative_to(root)
        ignored: set[str] = set()
        for name in names:
            rel_path = (rel_dir / name).as_posix()
            is_dir = (src_path / name).is_dir()
            if name.startswith("."):
                ignored.add(name)
                continue
            # gitwildmatch requires a trailing slash to match directory-only patterns.
            if spec.match_file(rel_path) or (
                is_dir and spec.match_file(rel_path + "/")
            ):
                ignored.add(name)
        return ignored

    return ignore
