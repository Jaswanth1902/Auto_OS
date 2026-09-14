"""
security_module.py — Hardened Security & System Diagnostics for AutoOS.
Eliminates all shell=True subprocess calls, adheres to the Windows CREATE_NO_WINDOW
visibility invariant (0x08000000), and provides safe system introspection.
"""
from __future__ import annotations

import os
import subprocess
from typing import List

from utils.logger import agent_logger as logger

CREATE_NO_WINDOW = 0x08000000

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
    mpcmd = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
    if os.path.exists(mpcmd):
        try:
            subprocess.Popen(
                [mpcmd, "-Scan", "-ScanType", "1"],
                shell=False,
                creationflags=CREATE_NO_WINDOW
            )
            return (
                "Started a Quick Virus Scan via Windows Defender in the background.\n"
                "Results will be registered in Windows Security upon completion."
            )
        except Exception as exc:
            logger.error(f"Windows Defender execution error: {exc}")

    # Safe URI protocol dispatch without shell=True
    try:
        os.startfile("windowsdefender:")
        return "Opened Windows Security center. You can run a Quick Scan directly."
    except Exception as exc:
        return f"Could not launch Windows Security: {exc}"

async def _check_updates() -> str:
    try:
        os.startfile("ms-settings:windowsupdate")
        return (
            "Opened Windows Update Settings.\n"
            "Select 'Check for updates' to ensure system patches are current."
        )
    except Exception as exc:
        return f"Could not open Windows Update: {exc}"

async def _lock_settings() -> str:
    try:
        os.startfile("ms-settings:signinoptions")
        return "Opened Windows Sign-in Options for biometric and credential configuration."
    except Exception as exc:
        return f"Could not open Sign-in Options: {exc}"

async def _security_overview() -> str:
    try:
        os.startfile("windowsdefender:")
        return "Opened Windows Security Dashboard to inspect antivirus, firewall, and device security."
    except Exception as exc:
        return f"Could not open security overview: {exc}"
