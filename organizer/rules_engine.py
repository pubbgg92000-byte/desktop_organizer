"""Rule-based file classification and organization rules."""

from __future__ import annotations

import os
from pathlib import Path

from .utils import load_json

# Default category rules (extension -> category)
CATEGORIES = {
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".md", ".pages"],
    "Images": [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp", ".heic", ".tif", ".tiff"],
    "Videos": [".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"],
    "Audio": [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2"],
    "Code": [".js", ".ts", ".py", ".java", ".cpp", ".c", ".go", ".rs", ".swift", ".html", ".css", ".json", ".yaml", ".yml", ".sh"],
    "Installers": [".dmg", ".pkg", ".exe", ".msi", ".apk", ".iso", ".app"],
    "Screenshots": [],  # detected by filename
}

PROTECTED_FOLDERS = {
    "Applications", "System", "Library", ".git", "node_modules",
    ".venv", "venv", "__pycache__", ".next", "dist", "build",
}

PROTECTED_EXTENSIONS = {".env", ".key", ".pem", ".p12", ".pfx", ".db", ".sqlite"}

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    ".next", "dist", "build", ".Trash", "Library", "Trash Review",
}


def classify_file(name: str, ext: str) -> str:
    """Classify a file into a category based on rules."""
    name_lower = name.lower()

    # Screenshot detection
    if name_lower.startswith("screenshot") or "screen shot" in name_lower:
        return "Screenshots"

    # Extension-based classification
    ext_lower = ext.lower()
    for category, extensions in CATEGORIES.items():
        if ext_lower in extensions:
            return category

    return "Others"


def is_protected_file(name: str, ext: str, path: str) -> bool:
    """Check if a file should never be moved."""
    if ext.lower() in PROTECTED_EXTENSIONS:
        return True
    # Check if inside a protected folder
    for pf in PROTECTED_FOLDERS:
        if f"/{pf}/" in path or path.endswith(f"/{pf}"):
            return True
    return False


def is_junk_file(name: str, ext: str, age: int) -> bool:
    """Check if a file is likely junk."""
    if name == ".DS_Store":
        return True
    if ext.lower() in {".tmp", ".cache", ".part", ".crdownload"}:
        return True
    if ext.lower() in {".dmg", ".pkg"} and age > 30:
        return True
    return False


def get_destination(category: str, base_dir: str) -> str:
    """Get the destination folder for a category."""
    return os.path.join(base_dir, "Organized", category)


def should_rename(name: str) -> tuple[bool, str]:
    """Check if a file should be renamed and suggest new name."""
    name_lower = name.lower()
    # Only rename generic camera/screenshot names
    if name_lower.startswith("img_") or name_lower.startswith("dsc_"):
        return True, "image"
    if name_lower.startswith("screenshot"):
        return True, "screenshot"
    if name_lower == "untitled" or name_lower.startswith("untitled"):
        return True, "document"
    return False, ""
