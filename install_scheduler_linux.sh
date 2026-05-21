#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

cat <<EOF
Add one of these to your crontab:

Every 3 days at 10:00:
0 10 */3 * * cd "${PROJECT_DIR}" && "${PYTHON_BIN}" file_organizer.py --scheduled

Every Saturday at 10:00:
0 10 * * 6 cd "${PROJECT_DIR}" && "${PYTHON_BIN}" file_organizer.py --scheduled
EOF
