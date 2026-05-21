#!/usr/bin/env python3
"""Telegram bot — per-folder actions, safe, no permanent deletes."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from organizer.utils import format_bytes, HOME
from organizer.file_organizer import scan_folder, plan_organize, execute_organize, cleanup_junk
from organizer.duplicate_detector import find_duplicates
from organizer.restore_engine import RestoreEngine
from organizer.report_generator import format_scan_summary, format_organize_summary
from organizer.rules_engine import SKIP_DIRS

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("pip install requests python-dotenv")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout)
log = logging.getLogger("bot")

PROJECT_DIR = Path(__file__).parent.parent
RESTORE_DIR = str(PROJECT_DIR / "restore-maps")
TRASH_DIR = str(Path(HOME) / "Trash Review")
RUNNING = True
PENDING: dict[str, dict] = {}

def handle_signal(signum, frame):
    global RUNNING
    RUNNING = False

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def load_env():
    env_path = PROJECT_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    return token, chat_id


# ─── Telegram helpers ────────────────────────────────────────────────────────

def get_updates(token, offset, timeout=30):
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/getUpdates",
            json={"offset": offset, "timeout": timeout, "allowed_updates": ["message", "callback_query"]},
            timeout=timeout+5)
        r.raise_for_status()
        d = r.json()
        get_updates._backoff = 3  # reset on success
        return d.get("result", []) if d.get("ok") else []
    except requests.exceptions.ReadTimeout:
        return []
    except Exception as e:
        backoff = getattr(get_updates, "_backoff", 3)
        log.error("poll: %s (retry in %ds)", e, backoff)
        time.sleep(backoff)
        get_updates._backoff = min(backoff * 2, 60)
        return []

def send(token, chat_id, text, markup=None):
    p = {"chat_id": chat_id, "text": text[:4096], "parse_mode": "HTML"}
    if markup: p["reply_markup"] = markup
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=p, timeout=20)
    except Exception as e: log.error("send: %s", e)

def answer(token, cb_id, text):
    try: requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery",
        json={"callback_query_id": cb_id, "text": text[:180]}, timeout=10)
    except: pass

# ─── /start — Main menu ─────────────────────────────────────────────────────

def cmd_start(token, chat_id):
    buttons = [
        [{"text": "🖥 Desktop", "callback_data": "folder:Desktop"}, {"text": "⬇️ Downloads", "callback_data": "folder:Downloads"}],
        [{"text": "📄 Documents", "callback_data": "folder:Documents"}, {"text": "🏠 Home", "callback_data": "folder:Home"}],
        [{"text": "💾 Storage", "callback_data": "cmd:storage"}, {"text": "⚡ Performance", "callback_data": "cmd:performance"}],
    ]
    send(token, chat_id, "<b>📂 File Organizer</b>\n\nPick a folder to manage:", markup={"inline_keyboard": buttons})


# ─── Folder action menu ─────────────────────────────────────────────────────

def cmd_folder_menu(token, chat_id, folder_name):
    display = "~" if folder_name == "Home" else f"~/{folder_name}"
    buttons = [
        [{"text": "🔍 Quick Scan", "callback_data": f"act:scan:{folder_name}"}, {"text": "🧹 Organize", "callback_data": f"act:organize:{folder_name}"}],
        [{"text": "🗂 Browse Files", "callback_data": f"act:browse:{folder_name}"}, {"text": "🗑 Clear Junk", "callback_data": f"act:clear:{folder_name}"}],
        [{"text": "🔁 Find Duplicates", "callback_data": f"act:dupes:{folder_name}"}],
        [{"text": "⬅️ Back", "callback_data": "cmd:start"}],
    ]
    send(token, chat_id, f"<b>📁 {display}</b>\n\nWhat do you want to do?", markup={"inline_keyboard": buttons})

# ─── Per-folder actions ──────────────────────────────────────────────────────

def get_path(folder_name):
    return HOME if folder_name == "Home" else os.path.join(HOME, folder_name)

def act_scan(token, chat_id, folder_name):
    path = get_path(folder_name)
    display = "~" if folder_name == "Home" else f"~/{folder_name}"
    send(token, chat_id, f"🔍 Scanning {display}...")
    s = scan_folder(path)
    if "error" in s:
        send(token, chat_id, f"❌ {s['error']}"); return
    st = s["stats"]
    lines = [
        f"<b>🔍 {display}</b>", "",
        f"📁 Files: <b>{st['files']}</b> | Folders: <b>{st['folders']}</b>",
        f"💾 Size: <b>{format_bytes(st['total_size'])}</b>",
        "", "<b>Breakdown:</b>",
        f"  📸 Screenshots: {st['screenshots']}",
        f"  🖼 Images: {st['images']}",
        f"  🎬 Videos: {st['videos']}",
        f"  📄 Documents: {st['documents']}",
        f"  💿 Installers: {st['installers']}",
        f"  🗜 Archives: {st['archives']}",
        f"  💻 Code: {st['code']}",
        f"  🗑 Junk: {st['junk']}",
        f"  📦 Large: {st['large']}",
        f"  💤 Old: {st['old']}",
    ]
    buttons = [
        [{"text": "🧹 Organize", "callback_data": f"act:organize:{folder_name}"}, {"text": "🗑 Clear", "callback_data": f"act:clear:{folder_name}"}],
        [{"text": "⬅️ Back", "callback_data": f"folder:{folder_name}"}],
    ]
    send(token, chat_id, "\n".join(lines), markup={"inline_keyboard": buttons})

def act_browse(token, chat_id, folder_name, sub_path=""):
    base = get_path(folder_name)
    target = Path(os.path.join(base, sub_path)) if sub_path else Path(base)
    if not target.exists():
        send(token, chat_id, "❌ Not found"); return
    display = str(target).replace(HOME, "~")
    lines = [f"<b>📁 {display}</b>", ""]
    deeper = []
    try:
        entries = sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        send(token, chat_id, "⛔ Permission denied"); return
    for entry in entries:
        if entry.name.startswith(".") or entry.name in SKIP_DIRS:
            continue
        if entry.is_dir():
            lines.append(f"├── 📁 <b>{entry.name}/</b>")
            try:
                subs = [e for e in entry.iterdir() if not e.name.startswith(".") and e.name not in SKIP_DIRS][:8]
                for s in subs:
                    if s.is_dir():
                        lines.append(f"│   ├── 📁 {s.name}/")
                        deeper.append(entry)
                    else:
                        try: sz = format_bytes(s.stat().st_size)
                        except: sz = "?"
                        lines.append(f"│   ├── 📄 {s.name} [{sz}]")
            except: pass
            lines.append("│")
        else:
            try: sz = format_bytes(entry.stat().st_size)
            except: sz = "?"
            lines.append(f"├── 📄 {entry.name} [{sz}]")
    # Buttons for deeper folders
    buttons = []
    row = []
    for d in list(dict.fromkeys(deeper))[:12]:
        rel = str(d).replace(base, "").lstrip("/")
        cb = f"brs:{folder_name}:{rel}"
        if len(cb) > 64: cb = f"brs:{folder_name}:{d.name}"
        row.append({"text": f"📁 {d.name}", "callback_data": cb})
        if len(row) == 2: buttons.append(row); row = []
    if row: buttons.append(row)
    if sub_path:
        parent = str(Path(sub_path).parent)
        parent = "" if parent == "." else parent
        buttons.append([{"text": "⬆️ Back", "callback_data": f"brs:{folder_name}:{parent}"}, {"text": "🏠 Menu", "callback_data": f"folder:{folder_name}"}])
    else:
        buttons.append([{"text": "⬅️ Back", "callback_data": f"folder:{folder_name}"}])
    text = "\n".join(lines)
    if len(text) > 4000:
        mid = len(lines)//2
        send(token, chat_id, "\n".join(lines[:mid]))
        send(token, chat_id, "\n".join(lines[mid:]), markup={"inline_keyboard": buttons})
    else:
        send(token, chat_id, text, markup={"inline_keyboard": buttons})

def act_organize(token, chat_id, folder_name):
    path = get_path(folder_name)
    display = "~" if folder_name == "Home" else f"~/{folder_name}"
    send(token, chat_id, f"🧹 Planning {display}...")
    plan = plan_organize(path)
    if "error" in plan:
        send(token, chat_id, f"❌ {plan['error']}"); return
    s = plan["summary"]
    if s["total_actions"] == 0:
        send(token, chat_id, f"✅ {display} already organized!", markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": f"folder:{folder_name}"}]]})
        return
    lines = [
        f"<b>🧹 Organize Plan — {display}</b>", "",
        f"Move: <b>{s['to_move']}</b> | Rename: <b>{s['to_rename']}</b>",
        f"Junk: {s['junk']} | Protected: {s['protected']}",
        "", "⚠️ Nothing changed yet.",
    ]
    PENDING[f"organize:{folder_name}"] = plan
    buttons = [[{"text": "✅ Confirm", "callback_data": f"confirm:organize:{folder_name}"}, {"text": "❌ Cancel", "callback_data": f"folder:{folder_name}"}]]
    send(token, chat_id, "\n".join(lines), markup={"inline_keyboard": buttons})

def exec_organize(token, chat_id, folder_name):
    plan = PENDING.pop(f"organize:{folder_name}", None)
    if not plan:
        send(token, chat_id, "❌ No pending plan."); return
    display = "~" if folder_name == "Home" else f"~/{folder_name}"
    send(token, chat_id, f"⏳ Organizing {display}...")
    restore = RestoreEngine(RESTORE_DIR)
    results = execute_organize(plan, restore)
    lines = [
        f"<b>✅ {display} Organized!</b>", "",
        f"Moved: {results['moved']} | Renamed: {results['renamed']} | Errors: {results['errors']}",
        f"\n↩️ Undo: <code>python main.py restore</code>",
    ]
    send(token, chat_id, "\n".join(lines), markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": f"folder:{folder_name}"}]]})

def act_clear(token, chat_id, folder_name):
    path = get_path(folder_name)
    display = "~" if folder_name == "Home" else f"~/{folder_name}"
    send(token, chat_id, f"🗑 Finding junk in {display}...")
    s = scan_folder(path)
    if "error" in s:
        send(token, chat_id, f"❌ {s['error']}"); return
    junk = [f for f in s["files"] if f["junk"]]
    if not junk:
        send(token, chat_id, f"✅ No junk in {display}!", markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": f"folder:{folder_name}"}]]})
        return
    total = sum(f["size"] for f in junk)
    lines = [
        f"<b>🗑 Junk in {display}</b>", "",
        f"Files: <b>{len(junk)}</b> | Size: <b>{format_bytes(total)}</b>", "",
    ]
    for f in junk[:10]:
        lines.append(f"  🗑 {f['name']} — {format_bytes(f['size'])}")
    if len(junk) > 10: lines.append(f"  +{len(junk)-10} more")
    lines.extend(["", "Move to ~/Trash Review/?"])
    PENDING[f"clear:{folder_name}"] = {"path": path, "folder_name": folder_name}
    buttons = [[{"text": "✅ Confirm", "callback_data": f"confirm:clear:{folder_name}"}, {"text": "❌ Cancel", "callback_data": f"folder:{folder_name}"}]]
    send(token, chat_id, "\n".join(lines), markup={"inline_keyboard": buttons})

def exec_clear(token, chat_id, folder_name):
    pending = PENDING.pop(f"clear:{folder_name}", None)
    if not pending:
        send(token, chat_id, "❌ No pending clear."); return
    path = pending["path"]
    display = "~" if folder_name == "Home" else f"~/{folder_name}"
    send(token, chat_id, f"⏳ Clearing {display}...")
    restore = RestoreEngine(RESTORE_DIR)
    r = cleanup_junk(path, restore, TRASH_DIR)
    send(token, chat_id, f"✅ Cleared {display}\n🗑 Moved: {r.get('moved',0)} | Freed: {format_bytes(r.get('freed',0))}",
        markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": f"folder:{folder_name}"}]]})

def act_dupes(token, chat_id, folder_name):
    path = get_path(folder_name)
    display = "~" if folder_name == "Home" else f"~/{folder_name}"
    send(token, chat_id, f"🔁 Scanning duplicates in {display}...")
    dupes = find_duplicates(path)
    if not dupes:
        send(token, chat_id, f"✅ No duplicates in {display}!", markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": f"folder:{folder_name}"}]]})
        return
    total_waste = sum(d["wasted"] for d in dupes)
    lines = [f"<b>🔁 Duplicates in {display}</b>", "", f"Groups: <b>{len(dupes)}</b> | Wasted: <b>{format_bytes(total_waste)}</b>", ""]
    for i, g in enumerate(dupes[:8], 1):
        lines.append(f"<b>Group {i}</b> ({format_bytes(g['size'])} x{g['count']}):")
        for f in g["files"][:3]:
            lines.append(f"  📄 {f['name']}")
        if len(g["files"]) > 3: lines.append(f"  +{len(g['files'])-3} more")
        lines.append("")
    if len(dupes) > 8: lines.append(f"+{len(dupes)-8} more groups")
    send(token, chat_id, "\n".join(lines), markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": f"folder:{folder_name}"}]]})

# ─── Global commands ─────────────────────────────────────────────────────────

def cmd_storage(token, chat_id):
    st = os.statvfs("/")
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - free
    pct = (used / total) * 100
    bar = "█" * int(20*pct/100) + "░" * (20 - int(20*pct/100))
    folders = []
    for name in ["Downloads", "Desktop", "Documents", "Pictures", "Projects", "Movies"]:
        p = Path(HOME) / name
        if not p.exists(): continue
        size = 0
        try:
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    try: size += os.path.getsize(os.path.join(root, f))
                    except: pass
        except: pass
        folders.append((name, size))
    folders.sort(key=lambda x: x[1], reverse=True)
    lines = [
        "<b>💾 Storage</b>", f"<code>[{bar}]</code> {pct:.0f}%",
        f"Used: <b>{format_bytes(used)}</b> / {format_bytes(total)}",
        f"Free: <b>{format_bytes(free)}</b>", "", "<b>Folders:</b>",
    ]
    for name, size in folders:
        lines.append(f"  {name}/ — <b>{format_bytes(size)}</b>")
    send(token, chat_id, "\n".join(lines), markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": "cmd:start"}]]})

def cmd_performance(token, chat_id):
    lines = ["<b>⚡ Performance</b>", ""]
    try:
        r = subprocess.run(["ps", "-A", "-o", "%cpu,%mem,comm"], capture_output=True, text=True, timeout=10)
        procs = []
        for line in r.stdout.strip().split("\n")[1:]:
            parts = line.split(None, 2)
            if len(parts) == 3:
                procs.append((float(parts[0]), float(parts[1]), parts[2].split("/")[-1]))
        lines.append(f"CPU: <b>{sum(p[0] for p in procs):.0f}%</b>")
        top_cpu = sorted(procs, key=lambda x: x[0], reverse=True)[:5]
        top_mem = sorted(procs, key=lambda x: x[1], reverse=True)[:5]
    except: top_cpu, top_mem = [], []
    try:
        r = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
        lines.append(f"RAM: <b>{format_bytes(int(r.stdout.strip()))}</b> total")
    except: pass
    try:
        r = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
        up = r.stdout.strip().split("up")[1].split(",")[0].strip() if "up" in r.stdout else "?"
        lines.append(f"Uptime: {up}")
    except: pass
    st = os.statvfs("/")
    lines.append(f"Disk: {format_bytes((st.f_blocks-st.f_bavail)*st.f_frsize)} / {format_bytes(st.f_blocks*st.f_frsize)}")
    if top_cpu:
        lines.extend(["", "<b>Top CPU:</b>"])
        for cpu, mem, name in top_cpu: lines.append(f"  {name} — {cpu:.1f}%")
    if top_mem:
        lines.extend(["", "<b>Top Memory:</b>"])
        for cpu, mem, name in top_mem: lines.append(f"  {name} — {mem:.1f}%")
    send(token, chat_id, "\n".join(lines), markup={"inline_keyboard": [[{"text": "⬅️ Back", "callback_data": "cmd:start"}]]})

# ─── Main loop ───────────────────────────────────────────────────────────────

def _acquire_lock():
    """Prevent multiple bot instances via a PID lock file."""
    lock_path = PROJECT_DIR / "logs" / "bot.pid"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            old_pid = int(lock_path.read_text().strip())
            # Check if that process is still alive
            os.kill(old_pid, 0)
            # Process exists — another instance is running
            return None
        except (ValueError, ProcessLookupError, OSError):
            # Stale lock file — previous process died
            pass
    lock_path.write_text(str(os.getpid()))
    return lock_path


def _release_lock():
    lock_path = PROJECT_DIR / "logs" / "bot.pid"
    try:
        if lock_path.exists() and lock_path.read_text().strip() == str(os.getpid()):
            lock_path.unlink()
    except OSError:
        pass


def main():
    token, chat_id = load_env()
    if not token or not chat_id:
        log.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")
        return 1

    lock = _acquire_lock()
    if lock is None:
        log.error("Another bot instance is already running. Exiting.")
        return 1

    # Register commands
    commands = [
        {"command": "start", "description": "Main menu"},
        {"command": "storage", "description": "Disk usage"},
        {"command": "performance", "description": "CPU/RAM/processes"},
    ]
    try: requests.post(f"https://api.telegram.org/bot{token}/setMyCommands", json={"commands": commands}, timeout=10)
    except: pass

    # Offset tracking
    offset_file = PROJECT_DIR / "logs" / "bot-offset.json"
    offset_file.parent.mkdir(parents=True, exist_ok=True)
    offset = 0
    if offset_file.exists():
        try: offset = json.loads(offset_file.read_text()).get("offset", 0)
        except: pass

    log.info("Bot started.")

    while RUNNING:
        updates = get_updates(token, offset, timeout=30)

        for update in updates:
            uid = update.get("update_id", 0)
            offset = max(offset, uid + 1)
            offset_file.write_text(json.dumps({"offset": offset}))

            # Callback
            cb = update.get("callback_query")
            if cb:
                if str(cb.get("message",{}).get("chat",{}).get("id","")) != str(chat_id):
                    continue
                data = cb.get("data", "")
                answer(token, cb.get("id",""), "...")
                try:
                    if data == "cmd:start": cmd_start(token, chat_id)
                    elif data == "cmd:storage": cmd_storage(token, chat_id)
                    elif data == "cmd:performance": cmd_performance(token, chat_id)
                    elif data.startswith("folder:"): cmd_folder_menu(token, chat_id, data.split(":",1)[1])
                    elif data.startswith("act:scan:"): act_scan(token, chat_id, data.split(":",2)[2])
                    elif data.startswith("act:browse:"): act_browse(token, chat_id, data.split(":",2)[2])
                    elif data.startswith("act:organize:"): act_organize(token, chat_id, data.split(":",2)[2])
                    elif data.startswith("act:clear:"): act_clear(token, chat_id, data.split(":",2)[2])
                    elif data.startswith("act:dupes:"): act_dupes(token, chat_id, data.split(":",2)[2])
                    elif data.startswith("confirm:organize:"): exec_organize(token, chat_id, data.split(":",2)[2])
                    elif data.startswith("confirm:clear:"): exec_clear(token, chat_id, data.split(":",2)[2])
                    elif data.startswith("brs:"):
                        parts = data.split(":", 2)
                        fname = parts[1] if len(parts) > 1 else "Home"
                        sub = parts[2] if len(parts) > 2 else ""
                        act_browse(token, chat_id, fname, sub)
                except Exception as e:
                    log.error("cb error: %s", e)
                    send(token, chat_id, f"❌ {str(e)[:100]}")
                continue

            # Message
            msg = update.get("message")
            if not msg: continue
            if str(msg.get("chat",{}).get("id","")) != str(chat_id): continue
            text = (msg.get("text") or "").strip().lower()
            log.info("Msg: %s", text[:40])

            try:
                if text in {"/start", "start", "hi", "hello", "menu"}: cmd_start(token, chat_id)
                elif text in {"/storage", "storage"}: cmd_storage(token, chat_id)
                elif text in {"/performance", "performance"}: cmd_performance(token, chat_id)
                else: cmd_start(token, chat_id)
            except Exception as e:
                log.error("msg error: %s", e)
                send(token, chat_id, f"❌ {str(e)[:100]}")

    log.info("Bot stopped.")
    _release_lock()
    return 0


if __name__ == "__main__":
    sys.exit(main())
