"""Debounced filesystem watcher for ``scripts/*.py``."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from erpclasp.api import FrappeClient
from erpclasp.sync import push_single_file
from erpclasp.utils import is_ignored_watch_path, scripts_dir

logger = logging.getLogger(__name__)

DEFAULT_DEBOUNCE_MS = 450


class _DebouncedPushHandler(FileSystemEventHandler):
    """Coalesce rapid saves and push a single file."""

    def __init__(
        self,
        *,
        project_root: Path,
        client: FrappeClient,
        debounce_ms: float,
        on_event: Callable[[str, str], None],
        on_error: Callable[[str, BaseException], None],
    ) -> None:
        super().__init__()
        self._project_root = project_root
        self._client = client
        self._debounce_s = debounce_ms / 1000.0
        self._on_event = on_event
        self._on_error = on_error
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._schedule(Path(event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._schedule(Path(event.src_path))

    def _schedule(self, path: Path) -> None:
        path = path.resolve()
        if is_ignored_watch_path(path):
            return
        key = str(path)

        def fire() -> None:
            with self._lock:
                self._timers.pop(key, None)
            self._push(path)

        with self._lock:
            old = self._timers.pop(key, None)
            if old is not None:
                old.cancel()
            timer = threading.Timer(self._debounce_s, fire)
            self._timers[key] = timer
            timer.daemon = True
            timer.start()

    def _push(self, path: Path) -> None:
        scripts_root = scripts_dir(self._project_root)
        try:
            rel = path.relative_to(scripts_root)
        except ValueError:
            return
        filename = rel.as_posix()
        if "/" in filename:
            return
        started = time.perf_counter()
        try:
            result = push_single_file(self._client, self._project_root, filename, dry_run=False)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if result.ok:
                self._on_event(filename, f"ok in {elapsed_ms:.0f} ms — {result.message}")
            else:
                self._on_error(filename, RuntimeError(result.message))
        except BaseException as exc:
            self._on_error(filename, exc)


def watch_scripts(
    project_root: Path,
    client: FrappeClient,
    *,
    debounce_ms: float = DEFAULT_DEBOUNCE_MS,
    on_event: Callable[[str, str], None] | None = None,
    on_error: Callable[[str, BaseException], None] | None = None,
) -> None:
    """Block and watch ``scripts/`` until process exit."""
    scripts_root = scripts_dir(project_root)
    scripts_root.mkdir(parents=True, exist_ok=True)

    def default_on_event(name: str, msg: str) -> None:
        logger.info("%s: %s", name, msg)

    def default_on_error(name: str, exc: BaseException) -> None:
        logger.error("%s: %s", name, exc)

    handler = _DebouncedPushHandler(
        project_root=project_root,
        client=client,
        debounce_ms=debounce_ms,
        on_event=on_event or default_on_event,
        on_error=on_error or default_on_error,
    )
    observer = Observer()
    observer.schedule(handler, str(scripts_root), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join(timeout=10)
