"""Core file organizer — scan, plan, and execute organization."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from .utils import format_bytes, age_days, HOME
from .rules_engine import (
    classify_file, is_protected_file, is_junk_file,
    get_destination, should_rename, SKIP_DIRS,
)
from .restore_engine import RestoreEngine


def scan_folder(folder: str) -> dict:
    """Scan a folder and return stats + file list. Read-only."""
    target = Path(folder).expanduser()
    if not target.exists():
        return {"error": f"Not found: {folder}"}

    files = []
    folder_count = 0
    empty_count = 0

    for root, dirs, filenames in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        folder_count += len(dirs)
        if not dirs and not filenames:
            empty_count += 1
        for fname in filenames:
            if fname.startswith(".") and fname != ".DS_Store":
                continue
            fpath = os.path.join(root, fname)
            try:
                st = os.stat(fpath)
                ext = os.path.splitext(fname)[1].lower()
                category = classify_file(fname, ext)
                protected = is_protected_file(fname, ext, fpath)
                junk = is_junk_file(fname, ext, age_days(fpath))
                files.append({
                    "name": fname, "path": fpath, "size": st.st_size,
                    "ext": ext, "category": category,
                    "age_days": age_days(fpath),
                    "protected": protected, "junk": junk,
                })
            except:
                pass

    total_size = sum(f["size"] for f in files)
    stats = {
        "files": len(files),
        "folders": folder_count,
        "empty_folders": empty_count,
        "total_size": total_size,
        "screenshots": sum(1 for f in files if f["category"] == "Screenshots"),
        "images": sum(1 for f in files if f["category"] == "Images"),
        "videos": sum(1 for f in files if f["category"] == "Videos"),
        "documents": sum(1 for f in files if f["category"] == "Documents"),
        "archives": sum(1 for f in files if f["category"] == "Archives"),
        "installers": sum(1 for f in files if f["category"] == "Installers"),
        "code": sum(1 for f in files if f["category"] == "Code"),
        "junk": sum(1 for f in files if f["junk"]),
        "large": sum(1 for f in files if f["size"] > 50 * 1024 * 1024),
        "old": sum(1 for f in files if f["age_days"] > 90),
    }
    return {"stats": stats, "files": files, "path": str(target)}


def plan_organize(folder: str, dry_run: bool = True) -> dict:
    """Create an organization plan for a folder. Does NOT move anything."""
    scan = scan_folder(folder)
    if "error" in scan:
        return scan

    base_dir = str(Path(folder).expanduser())
    plan = {"moves": [], "renames": [], "skipped": [], "protected": [], "junk": []}

    for f in scan["files"]:
        if f["protected"]:
            plan["protected"].append(f)
            continue
        if f["junk"]:
            plan["junk"].append(f)
            continue

        # Plan move
        dest_dir = get_destination(f["category"], base_dir)
        dest_path = os.path.join(dest_dir, f["name"])

        # Skip if already in correct location
        if os.path.dirname(f["path"]) == dest_dir:
            plan["skipped"].append(f)
            continue

        # Check rename
        do_rename, prefix = should_rename(f["name"])
        if do_rename:
            ext = f["ext"]
            date_str = time.strftime("%Y-%m-%d")
            new_name = f"{prefix}-{date_str}-{len(plan['renames'])+1:03d}{ext}"
            dest_path = os.path.join(dest_dir, new_name)
            plan["renames"].append({**f, "new_name": new_name, "new_path": dest_path})
        else:
            plan["moves"].append({**f, "new_path": dest_path})

    plan["summary"] = {
        "to_move": len(plan["moves"]),
        "to_rename": len(plan["renames"]),
        "junk": len(plan["junk"]),
        "protected": len(plan["protected"]),
        "skipped": len(plan["skipped"]),
        "total_actions": len(plan["moves"]) + len(plan["renames"]),
    }
    return plan


def execute_organize(plan: dict, restore_engine: RestoreEngine) -> dict:
    """Execute an organization plan. Moves files and records restore map."""
    moved = 0
    renamed = 0
    errors = 0
    space_freed = 0

    all_actions = plan.get("moves", []) + plan.get("renames", [])

    for item in all_actions:
        src = item["path"]
        dst = item["new_path"]
        try:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            # Handle name collision
            if os.path.exists(dst):
                stem = Path(dst).stem
                ext = Path(dst).suffix
                counter = 1
                while os.path.exists(dst):
                    dst = str(Path(dst).parent / f"{stem}_{counter:03d}{ext}")
                    counter += 1
            shutil.move(src, dst)
            restore_engine.record_move(src, dst, item.get("category", "organize"))
            if "new_name" in item:
                renamed += 1
            else:
                moved += 1
        except Exception as e:
            errors += 1

    restore_engine.save()

    return {
        "moved": moved,
        "renamed": renamed,
        "errors": errors,
        "skipped": len(plan.get("skipped", [])),
        "protected": len(plan.get("protected", [])),
        "duplicates": 0,
        "space_freed": space_freed,
    }


def cleanup_junk(folder: str, restore_engine: RestoreEngine, trash_dir: str) -> dict:
    """Move junk files to Trash Review."""
    scan = scan_folder(folder)
    if "error" in scan:
        return scan

    junk_files = [f for f in scan["files"] if f["junk"]]
    moved = 0
    errors = 0
    freed = 0

    date_dir = os.path.join(trash_dir, time.strftime("%Y-%m-%d"))
    Path(date_dir).mkdir(parents=True, exist_ok=True)

    for f in junk_files:
        src = f["path"]
        dst = os.path.join(date_dir, f["name"])
        try:
            if os.path.exists(dst):
                stem = Path(dst).stem
                ext = Path(dst).suffix
                counter = 1
                while os.path.exists(dst):
                    dst = str(Path(date_dir) / f"{stem}_{counter:03d}{ext}")
                    counter += 1
            shutil.move(src, dst)
            restore_engine.record_move(src, dst, "junk_cleanup")
            moved += 1
            freed += f["size"]
        except:
            errors += 1

    restore_engine.save()
    return {"moved": moved, "errors": errors, "freed": freed, "total_junk": len(junk_files)}


def organize_single_file(path: str, config: dict, restore_engine: RestoreEngine) -> dict:
    """Organize a single file (used by watcher)."""
    if not os.path.exists(path):
        return {"action": "skipped", "reason": "not found"}

    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()

    if is_protected_file(name, ext, path):
        return {"action": "skipped", "reason": "protected"}

    category = classify_file(name, ext)
    base_dir = str(Path(path).parent)
    dest_dir = get_destination(category, base_dir)
    dest = os.path.join(dest_dir, name)

    if os.path.dirname(path) == dest_dir:
        return {"action": "skipped", "reason": "already organized"}

    try:
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        if os.path.exists(dest):
            stem = Path(dest).stem
            ext_s = Path(dest).suffix
            counter = 1
            while os.path.exists(dest):
                dest = str(Path(dest_dir) / f"{stem}_{counter:03d}{ext_s}")
                counter += 1
        shutil.move(path, dest)
        restore_engine.record_move(path, dest, category)
        restore_engine.save()
        return {"action": "moved", "new_path": dest, "category": category}
    except Exception as e:
        return {"action": "error", "error": str(e)}
