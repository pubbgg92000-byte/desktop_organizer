
# Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py preview
python main.py organize
python telegram/telegram_bot.py
```

# File Organizer Agent

Local, rule-based file organizer with CLI + Telegram bot control. No AI, no cloud, no paid APIs.

## Features

- Organize files by extension/category/date
- Duplicate detection (SHA256)
- Safe restore system (every move is reversible)
- Trash Review quarantine (never permanently deletes)
- Telegram remote control
- File watcher (auto-organize new downloads)
- Scheduler automation (cron/launchd)
- Dry-run preview mode

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Telegram bot token and chat ID
```

## CLI Commands

```bash
python main.py organize      # Organize files
python main.py preview       # Preview plan (dry run)
python main.py restore       # Undo last operation
python main.py watch         # Watch folders for new files
python main.py duplicates    # Find duplicate files
python main.py cleanup       # Move junk to Trash Review
python main.py report        # Generate scan report
python main.py status        # Show status
```

## Telegram Bot

```bash
python telegram/telegram_bot.py
```

Or use the scripts:
```bash
./scripts/start-agent.sh     # Start bot in background
./scripts/stop-agent.sh      # Stop bot
```

### Bot Commands
- `/start` — Main menu with folder picker
- `/storage` — Disk usage report
- `/performance` — CPU, RAM, processes

### Per-Folder Actions (via buttons)
- Quick Scan — file counts, categories, sizes
- Organize — sort files into folders (asks confirmation)
- Browse Files — tree view with navigation
- Clear Junk — move temp/old files to Trash Review
- Find Duplicates — SHA256 duplicate detection

## Scheduler

### macOS
```bash
./install_scheduler_mac.sh
```

### Linux
```bash
./install_scheduler_linux.sh
```

## Safety

- Never permanently deletes files
- All moves go to `~/Trash Review/` first
- Every operation has a restore map
- Protected folders/extensions are never touched
- Dry-run mode available for all operations

## Project Structure

```
file-organizer-agent/
├── main.py                  # CLI entry point
├── organizer/
│   ├── file_organizer.py    # Core scan/organize logic
│   ├── rules_engine.py      # Category rules
│   ├── duplicate_detector.py
│   ├── restore_engine.py
│   ├── watcher.py
│   ├── report_generator.py
│   └── utils.py
├── telegram/
│   └── telegram_bot.py      # Telegram bot
├── config/
│   ├── config.json
│   ├── categories.json
│   └── protected.json
├── scripts/
│   ├── start-agent.sh
│   ├── stop-agent.sh
│   ├── install_scheduler_mac.sh
│   └── install_scheduler_linux.sh
├── logs/
├── reports/
├── restore-maps/
├── requirements.txt
└── .env
```
