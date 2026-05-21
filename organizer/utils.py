"""Shared utilities."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

HOME = str(Path.home())


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    return f"{value:.1f} {units[unit]}"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: str) -> dict:
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_json(path: str, data) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def age_days(path: str) -> int:
    try:
        return int((time.time() - os.path.getmtime(path)) / 86400)
    except:
        return 0


def is_hidden(name: str) -> bool:
    return name.startswith(".")


def expand_path(p: str) -> str:
    return str(Path(p).expanduser())
