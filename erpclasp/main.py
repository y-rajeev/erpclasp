"""Typer CLI entry for erpclasp."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated

import requests
import typer
from dotenv import load_dotenv
from pydantic import ValidationError
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from erpclasp import __version__
from erpclasp.api import FrappeAPIError, FrappeClient
from erpclasp.config import (
    ENV_KEYS_API_KEY,
    ENV_KEYS_API_SECRET,
    ENV_KEYS_BASE_URL,
    AppConfig,
    credential_from_flag_or_env,
    load_app_config,
    persist_credentials_to_env,
    write_project_marker,
)
from erpclasp.diff import diff_against_remote, render_diffs
from erpclasp.sync import load_mapping, pull_scripts, push_scripts, register_script
from erpclasp.utils import MAP_FILENAME, require_project_root, scripts_dir
from erpclasp.watcher import DEFAULT_DEBOUNCE_MS, watch_scripts

app = typer.Typer(
    name="erpclasp",
    help="Sync ERPNext Server Scripts with your project via Frappe REST API.",
    no_args_is_help=True,
)
console = Console(stderr=True)


def _get_project_and_config() -> tuple[Path, AppConfig]:
    try:
        root = require_project_root()
        return root, load_app_config(root)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


def _print_version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(0)


@app.callback()
def main_callback(
    _show_version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_print_version,
            is_eager=True,
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable debug logging."),
    ] = False,
) -> None:
    """erpclasp — ERPNext Server Script CLI."""
    load_dotenv()
    _setup_logging(verbose)


_HELP_BASE_URL = "Override .env: BASE_URL or ERPCLASP_BASE_URL."
_HELP_API_KEY = "Override .env: API_KEY or ERPCLASP_API_KEY."
_HELP_API_SECRET = "Override .env: API_SECRET or ERPCLASP_API_SECRET."


@app.command("login")
def login_cmd(
    base_url: Annotated[
        str | None,
        typer.Option("--base-url", help=_HELP_BASE_URL),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help=_HELP_API_KEY),
    ] = None,
    api_secret: Annotated[
        str | None,
        typer.Option("--api-secret", help=_HELP_API_SECRET),
    ] = None,
    api_secret_file: Annotated[
        Path | None,
        typer.Option(
            "--api-secret-file",
            help="Read API secret from this UTF-8 file (e.g. paste into Notepad, save, pass path here).",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    plain_secret_prompt: Annotated[
        bool,
        typer.Option(
            "--plain-secret-prompt",
            help="When prompting for API Secret, show characters (clipboard paste works; avoid shoulder-surfing).",
        ),
    ] = False,
    skip_ping: Annotated[
        bool,
        typer.Option("--skip-ping", help="Do not verify credentials against the server."),
    ] = False,
) -> None:
    """Verify credentials, save them to `.env`, and write a marker `.erpclasp.json` (no secrets in JSON)."""
    project_root = Path.cwd()

    url = credential_from_flag_or_env(base_url, *ENV_KEYS_BASE_URL)
    key = credential_from_flag_or_env(api_key, *ENV_KEYS_API_KEY)
    secret = credential_from_flag_or_env(api_secret, *ENV_KEYS_API_SECRET)
    if not secret and api_secret_file is not None:
        try:
            secret = api_secret_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            console.print(f"[red]Could not read --api-secret-file:[/red] {exc}")
            raise typer.Exit(1) from exc
        if not secret:
            console.print("[red]API secret file is empty.[/red]")
            raise typer.Exit(1)

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if interactive and not (url and key and secret):
        console.print(
            "[dim]Add BASE_URL, API_KEY, and API_SECRET to a `.env` file in this directory, "
            "or pass --base-url / --api-key / --api-secret. "
            "For a masked secret prompt that won’t accept paste on Windows, use "
            "--plain-secret-prompt or --api-secret-file.[/dim]"
        )

    if not url:
        if not interactive:
            console.print(
                "[red]Missing BASE_URL. Set it in `.env` or pass --base-url.[/red]"
            )
            raise typer.Exit(1)
        url = typer.prompt("Base URL (https://your-site.frappe.cloud)")
    if not key:
        if not interactive:
            console.print("[red]Missing API_KEY. Set it in `.env` or pass --api-key.[/red]")
            raise typer.Exit(1)
        key = typer.prompt("API Key")
    if not secret:
        if not interactive:
            console.print(
                "[red]Missing API_SECRET. Set it in `.env` or pass --api-secret.[/red]"
            )
            raise typer.Exit(1)
        if plain_secret_prompt:
            console.print(
                "[yellow]API Secret will be visible while you type or paste "
                "(safe for dev machines; avoid on shared screens).[/yellow]"
            )
            secret = typer.prompt("API Secret", hide_input=False)
        else:
            secret = typer.prompt(
                "API Secret",
                hide_input=True,
                show_default=False,
            )

    try:
        cfg = AppConfig(base_url=url, api_key=key, api_secret=secret)
    except ValidationError as exc:
        console.print(f"[red]Invalid configuration:[/red]\n{exc}")
        raise typer.Exit(1) from exc

    client = FrappeClient(cfg)
    if not skip_ping:
        try:
            client.ping()
        except FrappeAPIError as exc:
            console.print(f"[red]Authentication or server check failed:[/red] {exc}")
            raise typer.Exit(1) from exc
        except requests.RequestException as exc:
            console.print(
                "[red]Network error while contacting the server.[/red] "
                f"Check the URL and your connection.\n{exc}"
            )
            raise typer.Exit(1) from exc

    persist_credentials_to_env(project_root, cfg)
    write_project_marker(project_root)
    console.print("[green]Login OK.[/green]")


@app.command("init")
def init_cmd(
    force_map: Annotated[
        bool,
        typer.Option("--force-map", help="Overwrite existing `.erpclasp-map.json` with {}."),
    ] = False,
) -> None:
    """Create `scripts/` and `.erpclasp-map.json` if missing."""
    project_root = Path.cwd()
    sdir = scripts_dir(project_root)
    sdir.mkdir(parents=True, exist_ok=True)
    map_path = project_root / MAP_FILENAME
    if not map_path.is_file() or force_map:
        map_path.write_text("{}\n", encoding="utf-8")
        console.print(f"[green]Wrote[/green] {map_path}")
    else:
        console.print(f"[yellow]Keep existing[/yellow] {map_path}")
    console.print(f"[green]Ensured directory[/green] {sdir}")


@app.command("add")
def add_cmd(
    file_path: Annotated[
        str,
        typer.Argument(help="Local file, e.g. my.py or scripts/my.py (under the project)."),
    ],
    server_name: Annotated[
        str | None,
        typer.Argument(
            metavar="[SERVER_NAME]",
            help=(
                "Exact Server Script name in ERPNext. Omit for a prompt, or use --name in CI/scripts."
            ),
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Server Script name (when you pass only the file path).",
        ),
    ] = None,
    create: Annotated[
        bool,
        typer.Option(
            "--create",
            "-c",
            help="Create an empty .py if the file does not exist yet.",
        ),
    ] = False,
) -> None:
    """Register a script in `.erpclasp-map.json` so it can be pushed (server must have that Server Script)."""
    erp_name = server_name or name
    if not erp_name:
        if sys.stdin.isatty() and sys.stdout.isatty():
            erp_name = typer.prompt("Server Script name (exact, as in ERPNext)")
        else:
            console.print(
                "[red]Missing Server Script name.[/red] Pass it as the second argument, "
                "or use [dim]erpclasp add my.py --name \"My Script\"[/dim]"
            )
            raise typer.Exit(1)
    erp_name = erp_name.strip()
    root = require_project_root()
    try:
        dest = register_script(root, file_path, erp_name, create=create)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except FileNotFoundError:
        console.print(
            f"[red]File not found:[/red] {file_path}. "
            "Create it first or use [dim]--create[/dim]."
        )
        raise typer.Exit(1)
    console.print(f"[green]Mapped[/green] [cyan]{dest.name}[/cyan] → {erp_name!r}")


@app.command("list")
def list_cmd() -> None:
    """Show ``scripts/*.py`` files and each file's mapped Server Script name (from ``.erpclasp-map.json``)."""
    root = require_project_root()
    sdir = scripts_dir(root)
    mapping = load_mapping(root)
    if not sdir.is_dir():
        console.print(f"[yellow]No scripts folder yet:[/yellow] {sdir} — run [dim]erpclasp init[/dim]")
        raise typer.Exit(0)
    py_files = sorted(
        p for p in sdir.iterdir() if p.is_file() and p.suffix.lower() == ".py"
    )
    if not py_files:
        console.print(f"[dim]No .py files in[/dim] {sdir}")
        raise typer.Exit(0)
    table = Table(title=str(sdir), show_header=True, header_style="bold")
    table.add_column("File")
    table.add_column("Server Script")
    for path in py_files:
        fn = path.name
        erp = mapping.get(fn)
        table.add_row(fn, erp or "[dim]— not mapped —[/dim]")
    console.print(table)


@app.command("pull")
def pull_cmd(
    backup: Annotated[
        bool,
        typer.Option("--backup", help="Backup each local file before overwriting."),
    ] = False,
    files: Annotated[
        bool,
        typer.Option(
            "--files",
            "-f",
            help="While downloading, print ERP script name → file (default lists filenames after pull).",
        ),
    ] = False,
) -> None:
    """Download all Server Scripts into `scripts/` and refresh `.erpclasp-map.json`."""
    root, cfg = _get_project_and_config()
    client = FrappeClient(cfg)
    scripts_path = scripts_dir(root)

    def progress(msg: str) -> None:
        console.print(f"[dim]{msg}[/dim]")

    try:
        result = pull_scripts(
            client,
            root,
            backup=backup,
            log_each=files,
            on_progress=progress if backup or files else None,
        )
    except FrappeAPIError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except requests.RequestException as exc:
        console.print(f"[red]Network error:[/red] {exc}")
        raise typer.Exit(1) from exc

    n = len(result.pulled)
    if not n and not result.errors:
        console.print("[yellow]No Server Scripts found on the site.[/yellow]")
    elif n and not files:
        console.print(
            f"[green]Pulled {n} script{'s' if n != 1 else ''}[/green] → [cyan]{scripts_path}[/cyan]"
        )
        for name in result.pulled:
            console.print(f"[dim]  scripts/{name}[/dim]")
    for err in result.errors:
        console.print(f"[red]ERR[/red] {err}")
    if result.errors:
        raise typer.Exit(1)


@app.command("push")
def push_cmd(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be pushed without calling the API."),
    ] = False,
    paths: Annotated[
        list[str] | None,
        typer.Argument(
            help="Optional: only these basenames (e.g. foo.py). Omit to push all mapped scripts.",
        ),
    ] = None,
) -> None:
    """Upload local `scripts/*.py` files to the server using the mapping file."""
    root, cfg = _get_project_and_config()
    client = FrappeClient(cfg)
    only: set[str] | None = {Path(p).name for p in paths} if paths else None
    if only:
        sdir = scripts_dir(root)
        missing = [fn for fn in only if not (sdir / fn).is_file()]
        if missing:
            console.print(f"[red]Not found under scripts/:[/red] {', '.join(sorted(missing))}")
            raise typer.Exit(1)
    try:
        results = push_scripts(client, root, dry_run=dry_run, only_filenames=only)
    except FrappeAPIError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except requests.RequestException as exc:
        console.print(f"[red]Network error:[/red] {exc}")
        raise typer.Exit(1) from exc

    table = Table(show_header=True, header_style="bold")
    table.add_column("File")
    table.add_column("Server script")
    table.add_column("Status")
    failed = False
    for r in results:
        if r.ok:
            style = "yellow" if dry_run else "green"
            table.add_row(r.filename, r.erp_name or "—", f"[{style}]{r.message}[/{style}]")
        else:
            failed = True
            table.add_row(r.filename, r.erp_name or "—", f"[red]{r.message}[/red]")
    console.print(table)
    if failed:
        raise typer.Exit(1)


@app.command("diff")
def diff_cmd(
    files: Annotated[
        list[str] | None,
        typer.Argument(help="Optional script filenames (e.g. `my.py`). Default: all mapped."),
    ] = None,
) -> None:
    """Show a colored diff between local files and the server."""
    root, cfg = _get_project_and_config()
    client = FrappeClient(cfg)
    only = list(files) if files else None
    try:
        entries = diff_against_remote(client, root, only_files=only)
    except (FrappeAPIError, ValueError, FileNotFoundError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except requests.RequestException as exc:
        console.print(f"[red]Network error:[/red] {exc}")
        raise typer.Exit(1) from exc

    render_diffs(Console(), entries)
    if any(e.error or not e.identical for e in entries):
        raise typer.Exit(1)


@app.command("watch")
def watch_cmd(
    debounce_ms: Annotated[
        float,
        typer.Option(
            "--debounce-ms",
            help="Milliseconds to wait after a change before pushing.",
            min=50,
            max=10_000,
        ),
    ] = DEFAULT_DEBOUNCE_MS,
) -> None:
    """Watch `scripts/` and push a file shortly after it is saved."""
    root, cfg = _get_project_and_config()
    client = FrappeClient(cfg)
    console.print(
        f"[green]Watching[/green] {scripts_dir(root)} "
        f"(debounce {debounce_ms:.0f} ms). Ctrl+C to stop."
    )

    def on_event(name: str, msg: str) -> None:
        console.print(f"[green]{name}[/green] {msg}")

    def on_error(name: str, exc: BaseException) -> None:
        console.print(f"[red]{name}[/red] {exc}")

    try:
        watch_scripts(
            root,
            client,
            debounce_ms=debounce_ms,
            on_event=on_event,
            on_error=on_error,
        )
    except requests.RequestException as exc:
        console.print(f"[red]Network error:[/red] {exc}")
        raise typer.Exit(1) from exc


@app.command("version")
def version_cmd() -> None:
    """Print the installed version."""
    typer.echo(__version__)


def main() -> None:
    """Console script entry point."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted.[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
