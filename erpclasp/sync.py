"""Pull/push sync and mapping file handling."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from erpclasp.api import FrappeAPIError, FrappeClient
from erpclasp.utils import (
    MAP_FILENAME,
    backup_dir,
    sanitize_filename,
    scripts_dir,
    unique_filename,
)


def map_path(project_root: Path) -> Path:
    return project_root / MAP_FILENAME


def resolve_scripts_file(project_root: Path, user_path: str) -> Path:
    """Resolve ``user_path`` to a ``.py`` file under ``scripts/`` (basename or ``scripts/...``)."""
    raw = user_path.strip()
    p = Path(raw)
    sroot = scripts_dir(project_root).resolve()
    if p.is_absolute():
        out = p.resolve()
    else:
        norm = raw.replace("\\", "/").lstrip("./")
        if norm.lower().startswith("scripts/"):
            out = (project_root / norm).resolve()
        else:
            out = (sroot / p.name).resolve()
    try:
        out.relative_to(sroot)
    except ValueError as exc:
        raise ValueError(f"Path must be inside {sroot}") from exc
    if out.suffix.lower() != ".py":
        raise ValueError("Only .py files are supported")
    return out


def register_script(
    project_root: Path,
    user_path: str,
    erp_script_name: str,
    *,
    create: bool = False,
) -> Path:
    """Map ``scripts/<name>.py`` to ``erp_script_name``; optionally create the file."""
    dest = resolve_scripts_file(project_root, user_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file():
        if create:
            dest.write_text("# Server Script\n\n", encoding="utf-8")
        else:
            raise FileNotFoundError(str(dest))
    mapping = load_mapping(project_root)
    mapping[dest.name] = erp_script_name.strip()
    save_mapping(project_root, mapping)
    return dest


def unmapped_local_scripts(project_root: Path) -> list[str]:
    """Basenames of ``scripts/*.py`` not listed in ``.erpclasp-map.json``."""
    mapping = load_mapping(project_root)
    sdir = scripts_dir(project_root)
    if not sdir.is_dir():
        return []
    return sorted(
        p.name
        for p in sdir.iterdir()
        if p.is_file() and p.suffix.lower() == ".py" and p.name not in mapping
    )


def load_mapping(project_root: Path) -> dict[str, str]:
    """Load ``filename -> ERP script name`` mapping."""
    path = map_path(project_root)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid {MAP_FILENAME}: expected a JSON object")
    out: dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def save_mapping(project_root: Path, mapping: dict[str, str]) -> None:
    path = map_path(project_root)
    sorted_map = dict(sorted(mapping.items(), key=lambda kv: kv[0].lower()))
    path.write_text(json.dumps(sorted_map, indent=2) + "\n", encoding="utf-8")


def _reverse_map(mapping: dict[str, str]) -> dict[str, str]:
    return {v: k for k, v in mapping.items()}


def _pick_filename_for_erp_name(
    erp_name: str,
    mapping: dict[str, str],
    used_filenames: set[str],
) -> str:
    reverse = _reverse_map(mapping)
    if erp_name in reverse:
        return reverse[erp_name]
    stem = sanitize_filename(erp_name)
    taken_stems = {Path(f).stem for f in used_filenames}
    stem = unique_filename(stem, taken_stems)
    return f"{stem}.py"


def _backup_file(target: Path, scripts_root: Path) -> Path:
    bdir = backup_dir(scripts_root)
    bdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = bdir / f"{ts}_{target.name}"
    shutil.copy2(target, dest)
    return dest


@dataclass
class PullResult:
    pulled: list[str]
    errors: list[str]


def pull_scripts(
    client: FrappeClient,
    project_root: Path,
    *,
    backup: bool = False,
    log_each: bool = False,
    on_progress: Callable[[str], None] | None = None,
) -> PullResult:
    """Fetch all Server Scripts and write ``scripts/*.py``."""
    sdir = scripts_dir(project_root)
    sdir.mkdir(parents=True, exist_ok=True)

    mapping = load_mapping(project_root)
    used_filenames = set(mapping.keys())
    names = client.list_server_script_names()
    pulled: list[str] = []
    errors: list[str] = []

    for erp_name in names:
        try:
            script_text = client.get_script_field(erp_name)
        except FrappeAPIError as exc:
            errors.append(f"{erp_name}: {exc}")
            continue

        filename = _pick_filename_for_erp_name(erp_name, mapping, used_filenames)
        mapping[filename] = erp_name
        used_filenames.add(filename)

        dest = sdir / filename
        if dest.is_file() and backup:
            try:
                backup_path = _backup_file(dest, sdir)
                if on_progress:
                    on_progress(f"Backup {filename} -> {backup_path.relative_to(project_root)}")
            except OSError as exc:
                errors.append(f"{filename}: backup failed: {exc}")
                continue

        try:
            dest.write_text(script_text, encoding="utf-8", newline="\n")
        except OSError as exc:
            errors.append(f"{filename}: write failed: {exc}")
            continue

        pulled.append(filename)
        if on_progress and log_each:
            on_progress(f"Pulled {erp_name} -> scripts/{filename}")

    save_mapping(project_root, mapping)
    return PullResult(pulled=pulled, errors=errors)


@dataclass
class PushItemResult:
    filename: str
    erp_name: str
    ok: bool
    message: str


def push_scripts(
    client: FrappeClient,
    project_root: Path,
    *,
    dry_run: bool = False,
    only_filenames: set[str] | None = None,
) -> list[PushItemResult]:
    """Push each ``scripts/*.py`` that appears in the mapping."""
    sdir = scripts_dir(project_root)
    if not sdir.is_dir():
        raise FileNotFoundError(f"Missing scripts directory: {sdir}")

    mapping = load_mapping(project_root)
    results: list[PushItemResult] = []

    py_files = sorted(p for p in sdir.iterdir() if p.is_file() and p.suffix.lower() == ".py")
    for path in py_files:
        name = path.name
        if only_filenames is not None and name not in only_filenames:
            continue
        if name not in mapping:
            results.append(
                PushItemResult(
                    filename=name,
                    erp_name="",
                    ok=False,
                    message=f"No mapping in {MAP_FILENAME} for {name}. Run `erpclasp pull` or `erpclasp add`.",
                )
            )
            continue
        erp_name = mapping[name]
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as exc:
            results.append(
                PushItemResult(filename=name, erp_name=erp_name, ok=False, message=str(exc))
            )
            continue

        if dry_run:
            results.append(
                PushItemResult(
                    filename=name,
                    erp_name=erp_name,
                    ok=True,
                    message="dry-run: would push",
                )
            )
            continue

        try:
            client.update_server_script(erp_name, body)
            results.append(
                PushItemResult(filename=name, erp_name=erp_name, ok=True, message="updated")
            )
        except FrappeAPIError as exc:
            results.append(
                PushItemResult(filename=name, erp_name=erp_name, ok=False, message=str(exc))
            )

    return results


def push_single_file(
    client: FrappeClient,
    project_root: Path,
    filename: str,
    *,
    dry_run: bool = False,
) -> PushItemResult:
    """Push one file by name (e.g. ``my_script.py``)."""
    results = push_scripts(
        client,
        project_root,
        dry_run=dry_run,
        only_filenames={filename},
    )
    if not results:
        return PushItemResult(
            filename=filename,
            erp_name="",
            ok=False,
            message="file not found under scripts/",
        )
    return results[0]
