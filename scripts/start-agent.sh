#!/bin/bash
cd "$(dirname "$0")/.."

# Kill any existing bot instances first
pkill -f "telegram_bot.py" 2>/dev/null
sleep 1

# Use system Python 3.9 (has required packages installed)
PYTHON="/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python"

# Start the telegram bot in background
nohup "$PYTHON" telegram/telegram_bot.py >> logs/bot.log 2>> logs/bot-err.log &
echo "Bot started (PID: $!)"
