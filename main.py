#!/usr/bin/env python3
"""CLI entry point for file organizer agent."""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from organizer.utils import load_json, format_bytes, HOME
from organizer.file_organizer import scan_folder, plan_organize, execute_organize, cleanup_junk
from organizer.duplicate_detector import find_duplicates, duplicates_report
from organizer.restore_engine import RestoreEngine
from organizer.report_generator import format_scan_summary, format_organize_summary

PROJECT_DIR = Path(__file__).parent
CONFIG_PATH = PROJECT_DIR / "config" / "config.json"
RESTORE_DIR = str(PROJECT_DIR / "restore-maps")
REPORTS_DIR = str(PROJECT_DIR / "reports")
LOGS_DIR = str(PROJECT_DIR / "logs")
TRASH_DIR = str(Path(HOME) / "Trash Review")


def load_config() -> dict:
    defaults = {
        "watch_folders": ["~/Downloads"],
        "organize_folders": ["~/Downloads", "~/Desktop", "~/Documents"],
        "protected_folders": ["Applications", "System", ".git", "node_modules"],
        "dry_run": False,
        "enable_duplicates": True,
        "enable_telegram": True,
        "trash_review_enabled": True,
        "log_level": "INFO",
    }
    if CONFIG_PATH.exists():
        user = json.loads(CONFIG_PATH.read_text())
        defaults.update(user)
    return defaults


def cmd_organize(args, config):
    restore = RestoreEngine(RESTORE_DIR)
    folders = config["organize_folders"]
    print("Organizing files...\n")
    for folder in folders:
        path = str(Path(folder).expanduser())
        plan = plan_organize(path)
        if "error" in plan:
            print(f"  {folder}: {plan['error']}")
            continue
        s = plan["summary"]
        print(f"  {folder}: move={s['to_move']} rename={s['to_rename']} junk={s['junk']} protected={s['protected']}")
        if s["total_actions"] == 0:
            print("    Already organized.")
            continue
        if args.dry_run:
            print("    [DRY RUN] No changes.")
            continue
        results = execute_organize(plan, restore)
        print(f"    Done: moved={results['moved']} renamed={results['renamed']} errors={results['errors']}")
    print(f"\nRestore: python main.py restore")

def cmd_preview(args, config):
    folders = config["organize_folders"]
    print("Preview (no changes):\n")
    for folder in folders:
        path = str(Path(folder).expanduser())
        plan = plan_organize(path, dry_run=True)
        if "error" in plan:
            print(f"  {folder}: {plan['error']}")
            continue
        s = plan["summary"]
        print(f"  {folder}/")
        print(f"    Move: {s['to_move']} | Rename: {s['to_rename']} | Junk: {s['junk']} | Skip: {s['skipped']}")
        for m in plan["moves"][:5]:
            print(f"      {m['name']} -> {m['category']}/")
        if len(plan["moves"]) > 5:
            print(f"      +{len(plan['moves'])-5} more")
        print()

def cmd_restore(args, config):
    restore = RestoreEngine(RESTORE_DIR)
    op_id = getattr(args, "operation_id", None)
    results = restore.restore_by_id(op_id) if op_id else restore.restore_last()
    for r in results:
        s = r.get("status")
        if s == "restored": print(f"  ✓ {r['to']}")
        elif s == "missing": print(f"  ✗ Missing: {r['from']}")
        else: print(f"  ✗ {r.get('error', r.get('message', ''))}")
    print(f"\n{len(results)} entries processed.")

def cmd_watch(args, config):
    from organizer.watcher import start_watcher, HAS_WATCHDOG
    if not HAS_WATCHDOG:
        print("Error: pip install watchdog")
        sys.exit(1)
    restore = RestoreEngine(RESTORE_DIR)
    print(f"Watching: {', '.join(config['watch_folders'])}")
    print("Ctrl+C to stop.\n")
    observer = start_watcher(config, restore)
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop(); observer.join()
        print("Stopped.")

def cmd_duplicates(args, config):
    print("Scanning for duplicates...\n")
    all_dupes = []
    for folder in config["organize_folders"]:
        dupes = find_duplicates(str(Path(folder).expanduser()))
        all_dupes.extend(dupes)
    print(duplicates_report(all_dupes))

def cmd_cleanup(args, config):
    restore = RestoreEngine(RESTORE_DIR)
    print("Cleaning junk...\n")
    total_moved = 0
    for folder in config["organize_folders"]:
        path = str(Path(folder).expanduser())
        r = cleanup_junk(path, restore, TRASH_DIR)
        if r.get("moved", 0) > 0:
            print(f"  {folder}: {r['moved']} files ({format_bytes(r['freed'])})")
            total_moved += r["moved"]
    if total_moved == 0: print("  No junk found!")
    else: print(f"\nMoved to: {TRASH_DIR}")

def cmd_report(args, config):
    print("Scan Report:\n")
    for folder in config["organize_folders"]:
        path = str(Path(folder).expanduser())
        scan = scan_folder(path)
        if "error" in scan: continue
        print(f"  {folder}/")
        print(f"  {format_scan_summary(scan['stats'])}\n")

def cmd_status(args, config):
    print("File Organizer Status")
    print(f"  Folders: {', '.join(config['organize_folders'])}")
    print(f"  Watch: {', '.join(config['watch_folders'])}")
    print(f"  Trash: {TRASH_DIR}")
    print(f"  Dry run: {config.get('dry_run', False)}")
    maps = list(Path(RESTORE_DIR).glob("restore-*.json")) if Path(RESTORE_DIR).exists() else []
    print(f"  Restore maps: {len(maps)}")


def main():
    parser = argparse.ArgumentParser(description="File Organizer Agent")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("organize", help="Organize files")
    sub.add_parser("preview", help="Preview plan (dry run)")
    r = sub.add_parser("restore", help="Restore last operation")
    r.add_argument("operation_id", nargs="?", default=None)
    sub.add_parser("undo", help="Undo last operation")
    sub.add_parser("watch", help="Watch folders")
    sub.add_parser("duplicates", help="Find duplicates")
    sub.add_parser("cleanup", help="Move junk to Trash Review")
    sub.add_parser("report", help="Scan report")
    sub.add_parser("status", help="Show status")

    args = parser.parse_args()
    config = load_config()

    if args.command == "organize": cmd_organize(args, config)
    elif args.command == "preview": cmd_preview(args, config)
    elif args.command in {"restore", "undo"}: cmd_restore(args, config)
    elif args.command == "watch": cmd_watch(args, config)
    elif args.command == "duplicates": cmd_duplicates(args, config)
    elif args.command == "cleanup": cmd_cleanup(args, config)
    elif args.command == "report": cmd_report(args, config)
    elif args.command == "status": cmd_status(args, config)
    else: parser.print_help()


if __name__ == "__main__":
    main()
