"""File and directory filtering rules for ignoring non-user modifications."""

import fnmatch
from pathlib import Path
from typing import Union

from src.utils.constants import IGNORED_DIR_NAMES, IGNORED_FILE_PATTERNS


def is_path_ignored(
    path: Union[str, Path],
    ignored_dirs: set[str] = IGNORED_DIR_NAMES,
    ignored_patterns: set[str] = IGNORED_FILE_PATTERNS,
) -> bool:
    """Evaluates whether a given file/folder path should be ignored by the watcher.

    Ignores:
        - Internal VCS directories (.git)
        - macOS system metadata (.DS_Store, AppleDouble)
        - Virtualenvs, cache directories, and lock files
        - Local log files and secrets (.env, keys)
    """
    path_obj = Path(path)
    parts = set(path_obj.parts)

    # Check if any parent folder component matches ignored directory names
    if any(dir_name in parts for dir_name in ignored_dirs):
        return True

    filename = path_obj.name

    # Check direct filename match
    if filename in ignored_patterns:
        return True

    # Check glob pattern matches
    for pattern in ignored_patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True

    return False
