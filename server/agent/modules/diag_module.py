"""
diag_module.py — System diagnostics and crash explanation for AutoOS.
Uses action_params.check_type from the planner.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger("AutoOS.diag_module")


async def run(task: str, entities: list[str], action_params: dict[str, Any]) -> str:
    check_type: str = action_params.get("check_type", "").lower()
    task_lower = task.lower()

    if check_type == "crash" or any(
        w in task_lower for w in ("crash", "blue screen", "bsod", "error", "event log")
    ):
        return await _explain_crashes()
    if check_type == "performance" or any(
        w in task_lower for w in ("slow", "performance", "speed", "lag", "freez")
    ):
        return await _performance_check()
    if check_type == "recycle_bin" or any(
        w in task_lower for w in ("recycle", "trash", "deleted")
    ):
        return await _recycle_bin_info()

    # Default: performance check
    return await _performance_check()


import sys


async def _explain_crashes() -> str:
    if sys.platform != "win32":
        return "Crash log analysis is only available on Windows."
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "powershell",
                "-Command",
                "Get-EventLog -LogName System -EntryType Error -Newest 5 "
                "| Select-Object TimeGenerated, Source, Message "
                "| ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return "Good news — I checked your system logs and did not find any recent crashes or serious errors."

        import json

        events = json.loads(result.stdout)
        if isinstance(events, dict):
            events = [events]

        lines = [f"Found {len(events)} recent system error(s):\n"]
        for e in events:
            time_str = e.get("TimeGenerated", "Unknown time")
            source = e.get("Source", "Unknown")
            msg = e.get("Message", "")[:200]
            lines.append(f"  [{time_str}] {source}: {msg}...")

        lines.append(
            "\nIf your computer has been crashing or restarting unexpectedly, "
            "please let me know and I can help troubleshoot further."
        )
        return "\n".join(lines)
    except Exception as exc:
        return f"Could not read system logs: {exc}"


async def _performance_check() -> str:
    try:
        import psutil

        cpu = await asyncio.to_thread(psutil.cpu_percent, interval=1)
        mem = await asyncio.to_thread(psutil.virtual_memory)
        root_path = os.path.abspath(os.sep)
        disk = await asyncio.to_thread(psutil.disk_usage, root_path)

        mem_pct = mem.percent
        disk_pct = disk.percent
        disk_free_gb = disk.free / (1024**3)

        issues = []
        if cpu > 80:
            issues.append(
                f"CPU is very busy ({cpu:.0f}%) — some program may be using a lot of power."
            )
        if mem_pct > 85:
            issues.append(
                f"Memory is almost full ({mem_pct:.0f}%) — try closing some apps."
            )
        if disk_pct > 90:
            issues.append(
                f"Your C: drive is almost full ({disk_free_gb:.1f} GB free) — consider deleting old files."
            )

        if not issues:
            return (
                f"Your computer looks healthy.\n"
                f"  CPU usage: {cpu:.0f}%\n"
                f"  Memory used: {mem_pct:.0f}%\n"
                f"  Disk free: {disk_free_gb:.1f} GB"
            )

        return "Health check results:\n" + "\n".join(f"  - {i}" for i in issues)
    except Exception as exc:
        return f"Could not check performance: {exc}"


async def _recycle_bin_info() -> str:
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "powershell",
                "-Command",
                "$shell = New-Object -ComObject Shell.Application; "
                "$bin = $shell.Namespace(10); "
                "$bin.Items() | Select-Object -ExpandProperty Name | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return "Your Recycle Bin is empty."

        import json

        try:
            items = json.loads(result.stdout)
            if isinstance(items, str):
                items = [items]
        except json.JSONDecodeError:
            return "There are items in your Recycle Bin but I could not list them."

        lines = [f"Recycle Bin contains {len(items)} item(s):\n"]
        for item in items[:15]:
            lines.append(f"  {item}")
        if len(items) > 15:
            lines.append(f"  ... and {len(items) - 15} more.")
        lines.append(
            "\nTo restore a file, open the Recycle Bin on your desktop and right-click the file."
        )
        return "\n".join(lines)
    except Exception as exc:
        return f"Could not check Recycle Bin: {exc}"
