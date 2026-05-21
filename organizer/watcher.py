"""File watcher — monitors folders and auto-organizes new files."""

from __future__ import annotations

import logging
import os
import time
import threading
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

from .rules_engine import classify_file, is_protected_file, SKIP_DIRS
from .file_organizer import organize_single_file

log = logging.getLogger("watcher")


class OrganizerHandler(FileSystemEventHandler):
    """Handles new file events by organizing them."""

    def __init__(self, config: dict, restore_engine, debounce_seconds: float = 3.0):
        self.config = config
        self.restore_engine = restore_engine
        self.debounce_seconds = debounce_seconds
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent):
            return
        path = event.src_path
        name = os.path.basename(path)

        # Skip hidden, temp, system
        if name.startswith("."):
            return
        if any(skip in path for skip in SKIP_DIRS):
            return
        if name.endswith((".tmp", ".part", ".crdownload")):
            return

        # Debounce — wait for file to finish writing
        with self._lock:
            self._pending[path] = time.time()

        threading.Timer(self.debounce_seconds, self._process, args=[path]).start()

    def _process(self, path: str):
        with self._lock:
            if path not in self._pending:
                return
            del self._pending[path]

        if not os.path.exists(path):
            return

        try:
            result = organize_single_file(path, self.config, self.restore_engine)
            if result.get("action") == "moved":
                log.info("Auto-organized: %s -> %s", path, result.get("new_path"))
        except Exception as e:
            log.error("Watcher error for %s: %s", path, e)


def start_watcher(config: dict, restore_engine) -> "Observer | None":
    """Start watching configured folders. Returns observer or None."""
    if not HAS_WATCHDOG:
        log.error("watchdog not installed. Run: pip install watchdog")
        return None

    watch_folders = config.get("watch_folders", ["~/Downloads"])
    observer = Observer()

    handler = OrganizerHandler(config, restore_engine)

    for folder in watch_folders:
        path = str(Path(folder).expanduser())
        if os.path.exists(path):
            observer.schedule(handler, path, recursive=False)
            log.info("Watching: %s", path)
        else:
            log.warning("Watch folder not found: %s", path)

    observer.start()
    return observer


def stop_watcher(observer) -> None:
    """Stop the file watcher."""
    if observer:
        observer.stop()
        observer.join()
