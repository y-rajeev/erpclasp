"""Helpers: project root discovery and safe filenames."""

from __future__ import annotations

import re
from pathlib import Path

CONFIG_FILENAME = ".erpclasp.json"
MAP_FILENAME = ".erpclasp-map.json"
SCRIPTS_DIRNAME = "scripts"
BACKUP_DIRNAME = ".backups"


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk upward from ``start`` (or cwd) looking for a project marker or map file."""
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        if (directory / CONFIG_FILENAME).is_file():
            return directory
        if (directory / MAP_FILENAME).is_file():
            return directory
    return None


def require_project_root() -> Path:
    """Return project root or raise ``FileNotFoundError`` with a clear message."""
    root = find_project_root()
    if root is None:
        msg = (
            f"No {CONFIG_FILENAME} or {MAP_FILENAME} found. "
            "Run `erpclasp init` then `erpclasp login` from your project directory."
        )
        raise FileNotFoundError(msg)
    return root


def sanitize_filename(erp_name: str) -> str:
    """Turn an ERPNext Server Script name into a safe default ``.py`` stem."""
    s = erp_name.strip().lower()
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "script"


def unique_filename(stem: str, used: set[str]) -> str:
    """Return ``stem`` or ``stem_2``, ``stem_3``, ... if ``stem`` is already in ``used``."""
    base = stem
    n = 2
    candidate = base
    while candidate in used:
        candidate = f"{base}_{n}"
        n += 1
    return candidate


def is_ignored_watch_path(path: Path) -> bool:
    """Skip editor temps and non-Python files for the watcher."""
    name = path.name
    if name.startswith(".#") or name.endswith(".tmp") or name.endswith("~"):
        return True
    if name.startswith(".") and name not in {".gitkeep"}:
        return True
    return path.suffix.lower() != ".py"


def scripts_dir(root: Path) -> Path:
    return root / SCRIPTS_DIRNAME


def display_path_under_project(project_root: Path, path: Path) -> str:
    """Short label for CLI output: path relative to project, else the original path string."""
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def backup_dir(scripts_root: Path) -> Path:
    return scripts_root / BACKUP_DIRNAME
