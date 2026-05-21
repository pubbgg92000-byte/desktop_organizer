#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.havard.fileorganizer"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"
BOT_LABEL="com.havard.fileorganizer.telegram"
BOT_PLIST_PATH="$HOME/Library/LaunchAgents/${BOT_LABEL}.plist"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

SCHEDULE_MODE="${1:-every_3_days}"

if [ "$SCHEDULE_MODE" = "weekly" ]; then
  cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${PROJECT_DIR}/file_organizer.py</string>
    <string>--scheduled</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key>
    <integer>7</integer>
    <key>Hour</key>
    <integer>10</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${PROJECT_DIR}/file-organizer-records/Logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${PROJECT_DIR}/file-organizer-records/Logs/launchd.err.log</string>
</dict>
</plist>
PLIST
else
  cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${PROJECT_DIR}/file_organizer.py</string>
    <string>--scheduled</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>
  <key>StartCalendarInterval</key>
  <array>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>1</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>4</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>7</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>10</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>13</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>16</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>19</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>22</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>25</integer>
    </dict>
    <dict>
      <key>Hour</key>
      <integer>10</integer>
      <key>Minute</key>
      <integer>0</integer>
      <key>Day</key>
      <integer>28</integer>
    </dict>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${PROJECT_DIR}/file-organizer-records/Logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${PROJECT_DIR}/file-organizer-records/Logs/launchd.err.log</string>
</dict>
</plist>
PLIST
fi

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

cat > "$BOT_PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${BOT_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${PROJECT_DIR}/file_organizer.py</string>
    <string>--telegram-sync</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_DIR}</string>
  <key>StartInterval</key>
  <integer>10</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${PROJECT_DIR}/file-organizer-records/Logs/telegram-sync.out.log</string>
  <key>StandardErrorPath</key>
  <string>${PROJECT_DIR}/file-organizer-records/Logs/telegram-sync.err.log</string>
</dict>
</plist>
PLIST

launchctl unload "$BOT_PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$BOT_PLIST_PATH"
echo "Installed ${LABEL} at ${PLIST_PATH}"
echo "Installed ${BOT_LABEL} at ${BOT_PLIST_PATH}"
