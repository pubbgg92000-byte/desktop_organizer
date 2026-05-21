"""Report generation for scan and organize operations."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .utils import format_bytes, save_json


def generate_scan_report(results: dict, output_dir: str) -> str:
    """Save scan results as JSON report. Returns path."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = str(Path(output_dir) / f"scan-{time.strftime('%Y-%m-%d-%H%M')}.json")
    save_json(path, results)
    return path


def generate_organize_report(results: dict, output_dir: str) -> str:
    """Save organize results as JSON report. Returns path."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = str(Path(output_dir) / f"organize-{time.strftime('%Y-%m-%d-%H%M')}.json")
    save_json(path, results)
    return path


def format_scan_summary(stats: dict) -> str:
    """Format scan stats as readable text."""
    lines = [
        "Scan Summary",
        f"  Files: {stats.get('files', 0)}",
        f"  Folders: {stats.get('folders', 0)}",
        f"  Total size: {format_bytes(stats.get('total_size', 0))}",
        f"  Screenshots: {stats.get('screenshots', 0)}",
        f"  Images: {stats.get('images', 0)}",
        f"  Videos: {stats.get('videos', 0)}",
        f"  Documents: {stats.get('documents', 0)}",
        f"  Archives: {stats.get('archives', 0)}",
        f"  Installers: {stats.get('installers', 0)}",
        f"  Code: {stats.get('code', 0)}",
        f"  Junk: {stats.get('junk', 0)}",
        f"  Large (>50MB): {stats.get('large', 0)}",
        f"  Old (90+ days): {stats.get('old', 0)}",
        f"  Empty folders: {stats.get('empty_folders', 0)}",
    ]
    return "\n".join(lines)


def format_organize_summary(results: dict) -> str:
    """Format organize results as readable text."""
    lines = [
        "Organization Complete",
        f"  Moved: {results.get('moved', 0)}",
        f"  Renamed: {results.get('renamed', 0)}",
        f"  Duplicates: {results.get('duplicates', 0)}",
        f"  Skipped: {results.get('skipped', 0)}",
        f"  Protected: {results.get('protected', 0)}",
        f"  Errors: {results.get('errors', 0)}",
        f"  Space freed: {format_bytes(results.get('space_freed', 0))}",
    ]
    return "\n".join(lines)
