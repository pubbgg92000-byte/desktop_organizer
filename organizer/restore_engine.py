"""Restore engine — tracks all moves and supports undo."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

from .utils import save_json, load_json


class RestoreEngine:
    def __init__(self, restore_dir: str):
        self.restore_dir = Path(restore_dir)
        self.restore_dir.mkdir(parents=True, exist_ok=True)
        self.current_op_id = str(uuid.uuid4())[:8]
        self.current_moves: list[dict] = []

    def _map_path(self) -> Path:
        return self.restore_dir / f"restore-{time.strftime('%Y-%m-%d')}.json"

    def record_move(self, original: str, new_path: str, reason: str = "") -> None:
        self.current_moves.append({
            "original_path": original,
            "new_path": new_path,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "operation_id": self.current_op_id,
            "reason": reason,
        })

    def save(self) -> str:
        """Save current operation's restore map. Returns path."""
        path = self._map_path()
        existing = []
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
        existing.extend(self.current_moves)
        save_json(str(path), existing)
        return str(path)

    def restore_last(self) -> list[dict]:
        """Restore the most recent operation."""
        path = self._map_path()
        if not path.exists():
            # Try yesterday
            import glob
            maps = sorted(self.restore_dir.glob("restore-*.json"))
            if not maps:
                return [{"status": "error", "message": "No restore maps found"}]
            path = maps[-1]

        entries = json.loads(path.read_text(encoding="utf-8"))
        if not entries:
            return [{"status": "error", "message": "Restore map is empty"}]

        # Get last operation_id
        last_op = entries[-1]["operation_id"]
        to_restore = [e for e in entries if e["operation_id"] == last_op]

        results = []
        for entry in to_restore:
            src = Path(entry["new_path"])
            dst = Path(entry["original_path"])
            if not src.exists():
                results.append({"from": str(src), "to": str(dst), "status": "missing"})
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                results.append({"from": str(src), "to": str(dst), "status": "restored"})
            except Exception as e:
                results.append({"from": str(src), "to": str(dst), "status": "error", "error": str(e)})

        # Remove restored entries from map
        remaining = [e for e in entries if e["operation_id"] != last_op]
        save_json(str(path), remaining)

        return results

    def restore_by_id(self, op_id: str) -> list[dict]:
        """Restore a specific operation by ID."""
        import glob
        results = []
        for map_path in sorted(self.restore_dir.glob("restore-*.json")):
            entries = json.loads(map_path.read_text(encoding="utf-8"))
            to_restore = [e for e in entries if e["operation_id"] == op_id]
            if not to_restore:
                continue
            for entry in to_restore:
                src = Path(entry["new_path"])
                dst = Path(entry["original_path"])
                if not src.exists():
                    results.append({"from": str(src), "to": str(dst), "status": "missing"})
                    continue
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
                    results.append({"from": str(src), "to": str(dst), "status": "restored"})
                except Exception as e:
                    results.append({"from": str(src), "to": str(dst), "status": "error", "error": str(e)})
            remaining = [e for e in entries if e["operation_id"] != op_id]
            save_json(str(map_path), remaining)
            break
        return results or [{"status": "error", "message": f"Operation {op_id} not found"}]
