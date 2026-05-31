"""
security_module.py — Security checks for AutoOS.
Uses action_params.action from the planner.
"""
from __future__ import annotations

import logging
import subprocess

from utils.logger import agent_logger as logger


async def run(task: str, entities: list[str], action_params: dict) -> str:
    action: str = action_params.get("action", "").lower()
    task_lower = task.lower()

    if action == "virus_scan" or any(w in task_lower for w in ("virus", "malware", "scan", "defender")):
        return await _virus_scan()
    if action == "check_updates" or any(w in task_lower for w in ("update", "windows update", "up to date")):
        return await _check_updates()
    if action == "lock_settings" or any(w in task_lower for w in ("lock", "pin", "password")):
        return await _lock_settings()

    return await _security_overview()


async def _virus_scan() -> str:
    try:
        mpcmd = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
        subprocess.Popen([mpcmd, "-Scan", "-ScanType", "1"], shell=False)
        return (
            "I started a Quick Virus Scan using Windows Defender.\n"
            "This usually takes 1 to 2 minutes. You will see the result in the "
            "notification area at the bottom-right of your screen."
        )
    except FileNotFoundError:
        subprocess.Popen("windowsdefender:", shell=True)
        return (
            "I opened Windows Security for you.\n"
            "Click 'Quick scan' to check your computer for viruses."
        )
    except Exception as exc:
        return f"Could not start virus scan: {exc}"


async def _check_updates() -> str:
    try:
        subprocess.Popen("ms-settings:windowsupdate", shell=True)
        return (
            "I opened Windows Update settings.\n"
            "Click 'Check for updates' to see if any updates are available.\n"
            "Keeping your computer updated helps keep it safe."
        )
    except Exception as exc:
        return f"Could not open Windows Update: {exc}"


async def _lock_settings() -> str:
    subprocess.Popen("ms-settings:signinoptions", shell=True)
    return "I opened Sign-in Options where you can set or change your PIN and password."


async def _security_overview() -> str:
    subprocess.Popen("windowsdefender:", shell=True)
    return (
        "I opened Windows Security for you. "
        "You can run scans, check updates, and review your protection status here."
    )
