"""
visual_module.py — Screen capture and system summaries for AutoOS.
Uses action_params.action from the planner.
"""

from __future__ import annotations

import datetime
import logging
import os
import platform
import socket
from typing import Any

import psutil
import pyautogui

logger = logging.getLogger("AutoOS.visual_module")


async def run(task: str, entities: list[str], action_params: dict[str, Any]) -> str:
    action: str = action_params.get("action", "").lower()
    task_lower = task.lower()

    if action == "screenshot" or any(
        w in task_lower for w in ("screenshot", "screen shot", "capture", "snapshot")
    ):
        return await _take_screenshot()

    if action == "summary" or any(
        w in task_lower for w in ("summary", "specs", "system info", "about my pc")
    ):
        return await _system_summary()

    # Default to summary if unclear
    return await _system_summary()


async def _take_screenshot() -> str:
    try:
        # Create unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"

        # Path logic — save to the 'screenshots' folder in the server root
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        screenshots_dir = os.path.join(base_dir, "server", "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        filepath = os.path.join(screenshots_dir, filename)

        # Take screenshot
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)

        logger.info(f"Screenshot saved to {filepath}")

        # Return URL-friendly message
        return (
            f"I have captured a screenshot of your desktop.\n"
            f"Saved as: {filename}\n"
            f"You can view it here: /screenshots/{filename}"
        )
    except Exception as exc:
        logger.error(f"Failed to take screenshot: {exc}")
        return f"I tried to take a screenshot but encountered an error: {exc}"


async def _system_summary() -> str:
    try:
        # OS Info
        os_name = platform.system()
        os_release = platform.release()
        os_version = platform.version()

        # CPU Info
        cpu_count = psutil.cpu_count(logical=False)
        cpu_logical = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq().max if psutil.cpu_freq() else 0

        # Memory Info
        mem = psutil.virtual_memory()
        total_ram = mem.total / (1024**3)
        available_ram = mem.available / (1024**3)

        # Disk Info
        disk = psutil.disk_usage("/")
        disk_total = disk.total / (1024**3)
        disk_free = disk.free / (1024**3)

        # Network Info
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except:
            local_ip = "Unknown"

        summary = [
            "### System Summary",
            f"**Operating System:** {os_name} {os_release} ({os_version})",
            (
                f"**Processor:** {cpu_count} Cores ({cpu_logical} Threads) @ {cpu_freq/1000:.1f}GHz"
                if cpu_freq
                else f"**Processor:** {cpu_count} Cores"
            ),
            f"**Memory (RAM):** {total_ram:.1f} GB total ({available_ram:.1f} GB available)",
            f"**Storage:** {disk_total:.1f} GB total ({disk_free:.1f} GB free on C:)",
            f"**Network:** Hostname: {hostname}, Local IP: {local_ip}",
        ]

        return "\n".join(summary)
    except Exception as exc:
        logger.error(f"Failed to generate system summary: {exc}")
        return f"I encountered an error while gathering system information: {exc}"
