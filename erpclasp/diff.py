"""Compare local Server Script files to the server copy."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from erpclasp.api import FrappeAPIError, FrappeClient
from erpclasp.sync import load_mapping
from erpclasp.utils import MAP_FILENAME, scripts_dir


@dataclass
class DiffEntry:
    filename: str
    erp_name: str
    unified_lines: list[str]
    identical: bool
    error: str | None = None


def _unified_diff(
    local_lines: list[str],
    remote_lines: list[str],
    from_name: str,
    to_name: str,
) -> list[str]:
    return list(
        difflib.unified_diff(
            local_lines,
            remote_lines,
            fromfile=from_name,
            tofile=to_name,
            lineterm="",
        )
    )


def diff_against_remote(
    client: FrappeClient,
    project_root: Path,
    *,
    only_files: list[str] | None = None,
) -> list[DiffEntry]:
    """Build unified diffs for mapped ``scripts/*.py`` files."""
    sdir = scripts_dir(project_root)
    mapping = load_mapping(project_root)
    if not mapping:
        raise ValueError(
            f"No mapping in {MAP_FILENAME}. Run `erpclasp pull` to create it."
        )

    targets: list[tuple[str, str]] = []
    for filename, erp_name in sorted(mapping.items(), key=lambda x: x[0].lower()):
        if only_files and filename not in only_files:
            continue
        targets.append((filename, erp_name))

    if only_files:
        missing = set(only_files) - {f for f, _ in targets}
        if missing:
            raise FileNotFoundError(
                "Unknown or unmapped file(s): " + ", ".join(sorted(missing))
            )

    entries: list[DiffEntry] = []
    for filename, erp_name in targets:
        path = sdir / filename
        if not path.is_file():
            entries.append(
                DiffEntry(
                    filename=filename,
                    erp_name=erp_name,
                    unified_lines=[],
                    identical=False,
                    error=f"missing local file: scripts/{filename}",
                )
            )
            continue
        try:
            local_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            entries.append(
                DiffEntry(
                    filename=filename,
                    erp_name=erp_name,
                    unified_lines=[],
                    identical=False,
                    error=str(exc),
                )
            )
            continue

        try:
            remote_text = client.get_script_field(erp_name)
        except FrappeAPIError as exc:
            entries.append(
                DiffEntry(
                    filename=filename,
                    erp_name=erp_name,
                    unified_lines=[],
                    identical=False,
                    error=str(exc),
                )
            )
            continue

        local_lines = local_text.splitlines()
        remote_lines = remote_text.splitlines()
        identical = local_lines == remote_lines
        lines = (
            []
            if identical
            else _unified_diff(
                local_lines,
                remote_lines,
                from_name=f"local:{filename}",
                to_name=f"remote:{erp_name}",
            )
        )
        entries.append(
            DiffEntry(
                filename=filename,
                erp_name=erp_name,
                unified_lines=lines,
                identical=identical,
            )
        )
    return entries


def render_diffs(console: Console, entries: list[DiffEntry]) -> None:
    """Print colored unified diffs using Rich."""
    for entry in entries:
        title = f"{entry.filename}  ({entry.erp_name})"
        if entry.error:
            console.print(Panel(Text(entry.error, style="red"), title=title, border_style="red"))
            continue
        if entry.identical:
            console.print(
                Panel(Text("No differences.", style="green"), title=title, border_style="green")
            )
            continue
        text = Text()
        for line in entry.unified_lines:
            if line.startswith("+++") or line.startswith("---"):
                text.append(line + "\n", style="cyan")
            elif line.startswith("@@"):
                text.append(line + "\n", style="magenta")
            elif line.startswith("+"):
                text.append(line + "\n", style="green")
            elif line.startswith("-"):
                text.append(line + "\n", style="red")
            else:
                text.append(line + "\n")
        console.print(Panel(Group(text), title=title, border_style="yellow"))
