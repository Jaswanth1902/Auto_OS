"""
file_module.py — File search and file operations for AutoOS.
Uses action_params for precise filtering by keywords, file types, and time hints.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from utils.logger import agent_logger as logger

_USER_ROOTS = [
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Pictures",
    Path.home() / "Videos",
    Path.home() / "Music",
]_MAX_RESULTS = 10

_EXT_MAP = {
    "document": [".docx", ".doc", ".pdf", ".txt", ".odt"],
    "report":   [".docx", ".doc", ".pdf", ".xlsx", ".xls"],
    "image":    [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
    "video":    [".mp4", ".avi", ".mkv", ".mov"],
    "spreadsheet": [".xlsx", ".xls", ".csv"],
    "presentation": [".pptx", ".ppt"],
}

_TIME_HINTS = {
    "today":      timedelta(days=1),
    "yesterday":  timedelta(days=2),
    "last_week":  timedelta(weeks=1),
    "last_month": timedelta(days=30),
    "recent":     timedelta(weeks=2),
    "old":        timedelta(days=90),
    "any":        None,
}


def _open_file(path: str):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=True)
    else:
        subprocess.run(["xdg-open", path], check=True)

async def run(task: str, entities: list[str], action_params: dict) -> str:
    task_lower = (task or "").lower()
    keywords: list[str] = action_params.get("keywords") or entities or []
    file_types: list[str] = action_params.get("file_types") or []
    time_hint: str = action_params.get("time_hint", "any")
    action: str = action_params.get("action", "search")
    folder: str | None = action_params.get("folder")

    if action == "open":
        target_name = keywords[0] if keywords else ""
        if not target_name:
            return "Please specify a file name to open."
            
        if "/" in target_name or "\\" in target_name or "*" in target_name or "?" in target_name:
            return "Invalid file name. Please provide a simple file name without paths or wildcards."

        # Search in Downloads folder first
        downloads = Path.home() / "Downloads"
        candidate = downloads / target_name
        if candidate.exists() and candidate.is_file():
            try:
                _open_file(str(candidate))
                return f"Opened {target_name} from Downloads."
            except Exception as e:
                logger.error("Failed to open file %s: %s", candidate, e)
                return f"Failed to open {target_name}: {e}"

        # Fallback: search across user roots
        for root in _USER_ROOTS:
            if not root.exists():
                continue
            try:
                for f in root.iterdir():
                    if f.name.lower() == target_name.lower() and f.is_file():
                        try:
                            _open_file(str(f))
                            return f"Opened {target_name} from {root}."
                        except Exception as e:
                            logger.error("Failed to open file %s: %s", f, e)
                            return f"Failed to open {target_name}: {e}"
            except (OSError, PermissionError) as e:
                logger.debug("Skipping root %s due to error: %s", root, e)
                continue
                
        return f"Could not find {target_name} to open."

    # Existing logic for other actions follows
    if not keywords and not file_types:
        if any(w in task_lower for w in ("recent", "last", "working on", "yesterday")):
            return await _recent_files(entities, file_types)
        if any(w in task_lower for w in ("download", "downloaded")):
            return await _recent_downloads()

    if folder == "downloads" or any(w in task_lower for w in ("download",)):
        return await _recent_downloads()

    if not keywords:
        return await _recent_files(entities, file_types)

    return await _search_files(keywords, file_types, time_hint)


async def _search_files(keywords: list[str], file_types: list[str], time_hint: str) -> str:
    kw_lower = [k.lower() for k in keywords]
    allowed_exts = set(file_types)
    cutoff_dt = _resolve_time_hint(time_hint)
    is_old = (time_hint == "old")
async def _search_files(keywords: list[str], file_types: list[str], time_hint: str) -> str:
    kw_lower = [k.lower() for k in keywords]
    allowed_exts: set[str] = set()
    for ft in file_types:
        ft_lower = ft.lower()
        if ft_lower in _EXT_MAP:
            allowed_exts.update(_EXT_MAP[ft_lower])
        elif ft_lower.startswith("."):
            allowed_exts.add(ft_lower)
        else:
            # Treat as extension if not a known type
            allowed_exts.add(f".{ft_lower}")
    cutoff_dt = _resolve_time_hint(time_hint)
    results: list[tuple[datetime, Path]] = []

    for root in _USER_ROOTS:
        if not root.exists():
            continue
        try:
            for f in root.rglob("*"):
                if not f.is_file():
                    continue
                if allowed_exts and f.suffix.lower() not in allowed_exts:
                    continue
                name_lower = f.name.lower()
                if not any(kw in name_lower for kw in kw_lower):
                    continue                if not f.is_file():
                    continue
                if allowed_exts and f.suffix.lower() not in allowed_exts:
                    continue
                name_lower = f.name.lower()
                if not any(kw in name_lower for kw in kw_lower):
                    continue                except Exception:
                    continue

                if allowed_exts and f.suffix.lower() not in allowed_exts:
                    continue
                name_lower = f.name.lower()
                if not any(kw in name_lower for kw in kw_lower):
                    continue
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if cutoff_dt:
                        if is_old and mtime >= cutoff_dt:
                            continue
                        elif not is_old and mtime < cutoff_dt:
                            continue
                    results.append((mtime, f))
                except OSError:
                    continue
        except PermissionError:
            continue

    if not results:
        return f"No files matching '{', '.join(keywords)}' found in your common folders."

    results.sort(key=lambda x: x[0], reverse=True)
    lines = [f"Found {len(results)} file(s) matching your request:\n"]
    for mtime, path in results[:_MAX_RESULTS]:
        lines.append(f"  {path.name}  —  {path.parent}  ({mtime.strftime('%d %b %Y')})")
    return "\n".join(lines)


async def _recent_files(entities: list[str], file_types: list[str]) -> str:
    allowed_exts: set[str] = set(file_types)
    if not allowed_exts:
        # Infer from entity names
        for entity in entities:
            for key, exts in _EXT_MAP.items():
                if key in entity.lower():
                    allowed_exts.update(exts)

    results: list[tuple[datetime, Path]] = []
    seen = set()
    for root in _USER_ROOTS:
        if not root.exists():
            continue
        try:
            for f in root.rglob("*"):
                if f.name.startswith("."):
                    continue
                if not f.is_file():
                    continue
    files = []
    for f in downloads.iterdir():
        if not f.is_file():
            continue
        try:
            files.append((f.stat().st_mtime, f))
        except OSError:
            continue    for f in downloads.iterdir():
        if not f.is_file():
            continue
        try:
            files.append((f.stat().st_mtime, f))
        except OSError:
            continue                try:
                    resolved = f.resolve()
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                except Exception:
                    continue

                if allowed_exts and f.suffix.lower() not in allowed_exts:
                    continue
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    results.append((mtime, f))
                except OSError:
                    continue
        except PermissionError:
            continue

    if not results:
        return "No recent files found in your common folders."

    results.sort(key=lambda x: x[0], reverse=True)
    lines = ["Your most recently modified files:\n"]
    for mtime, path in results[:_MAX_RESULTS]:
        lines.append(
            f"  {path.name}  —  {path.parent}  "
            f"(last edited {mtime.strftime('%d %b %Y, %I:%M %p')})"
        )
    return "\n".join(lines)


async def _recent_downloads() -> str:
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        return "Could not find your Downloads folder."

    files = [(f.stat().st_mtime, f) for f in downloads.iterdir() if f.is_file()]
    if not files:
        return "Your Downloads folder is empty."

    files.sort(reverse=True)
    lines = ["Your most recent downloads:\n"]
    for mtime, path in files[:_MAX_RESULTS]:
        dt = datetime.fromtimestamp(mtime).strftime("%d %b %Y, %I:%M %p")
        lines.append(f"  {path.name}  ({dt})")
    return "\n".join(lines)


def _resolve_time_hint(hint: str) -> datetime | None:
    delta = _TIME_HINTS.get(hint)
    if delta is None:
        return None
    return datetime.now() - delta
