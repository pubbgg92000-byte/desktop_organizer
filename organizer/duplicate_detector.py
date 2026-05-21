"""Duplicate file detection using SHA256 hashing."""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from .utils import sha256_file, format_bytes
from .rules_engine import SKIP_DIRS


def find_duplicates(folder: str, min_size: int = 100) -> list[dict]:
    """Find duplicate files in a folder by SHA256 hash.
    
    Returns list of duplicate groups:
    [{"hash": "...", "size": 1234, "files": [{"name": "...", "path": "..."}]}]
    """
    # First pass: group by size (fast filter)
    size_groups: dict[int, list[str]] = defaultdict(list)

    for root, dirs, filenames in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in filenames:
            if fname.startswith("."):
                continue
            fpath = os.path.join(root, fname)
            try:
                size = os.path.getsize(fpath)
                if size >= min_size:
                    size_groups[size].append(fpath)
            except:
                pass

    # Second pass: hash only files with matching sizes
    hash_groups: dict[str, list[dict]] = defaultdict(list)

    for size, paths in size_groups.items():
        if len(paths) < 2:
            continue
        for fpath in paths:
            try:
                h = sha256_file(fpath)
                hash_groups[h].append({
                    "name": os.path.basename(fpath),
                    "path": fpath,
                    "size": size,
                })
            except:
                pass

    # Build results
    duplicates = []
    for h, files in hash_groups.items():
        if len(files) > 1:
            duplicates.append({
                "hash": h,
                "size": files[0]["size"],
                "count": len(files),
                "files": files,
                "wasted": files[0]["size"] * (len(files) - 1),
            })

    duplicates.sort(key=lambda x: x["wasted"], reverse=True)
    return duplicates


def duplicates_report(duplicates: list[dict]) -> str:
    """Generate a human-readable duplicates report."""
    if not duplicates:
        return "No duplicates found."

    total_wasted = sum(d["wasted"] for d in duplicates)
    lines = [
        f"Duplicate Files Report",
        f"Groups: {len(duplicates)}",
        f"Wasted space: {format_bytes(total_wasted)}",
        "",
    ]

    for i, group in enumerate(duplicates[:20], 1):
        lines.append(f"Group {i} ({format_bytes(group['size'])} x {group['count']}):")
        for f in group["files"]:
            lines.append(f"  {f['path']}")
        lines.append("")

    if len(duplicates) > 20:
        lines.append(f"... and {len(duplicates) - 20} more groups")

    return "\n".join(lines)
