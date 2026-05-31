"""
hardware_module.py — Hardware detection and troubleshooting for AutoOS.
Uses action_params.device_type from the planner for precise dispatch.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger("AutoOS.hardware_module")


async def run(task: str, entities: list[str], action_params: dict[str, Any]) -> str:
    device_type: str = action_params.get("device_type", "").lower()

    # Use structured device_type first, fallback to keyword scan
    if device_type in ("usb", "pendrive", "flash_drive", "storage"):
        return await _check_usb()
    if device_type in ("wifi", "wi-fi", "network", "internet"):
        if any(
            w in task.lower() for w in ("available", "nearby", "list", "scan", "show")
        ):
            return await _get_available_wifi_networks()
        if any(
            w in task.lower()
            for w in ("toggle", "turn", "on", "off", "switch", "open", "settings")
        ):
            return await _open_wifi_settings()
        return await _fix_wifi(task.lower())
    if device_type in ("printer", "print"):
        return await _check_printer()
    if device_type in ("sound", "audio", "speaker", "microphone"):
        return await _run_troubleshooter("audio")
    if device_type in ("bluetooth",):
        if (
            "toggle" in task.lower()
            or "turn" in task.lower()
            or "switch" in task.lower()
        ):
            return await _open_bluetooth_settings()
        return await _check_bluetooth()

    # Fallback keyword scan on raw task
    task_lower = task.lower()
    if any(w in task_lower for w in ("usb", "pendrive", "pen drive", "flash drive")):
        return await _check_usb()
    if any(w in task_lower for w in ("wifi", "wi-fi", "internet", "network")):
        import re

        if re.search(r"\b(available|nearby|list|scan|show)\b", task_lower):
            return await _get_available_wifi_networks()
        if re.search(
            r"\b(toggle|turn\s*on|turn\s*off|switch\s*on|switch\s*off|open\s*settings)\b",
            task_lower,
        ):
            return await _open_wifi_settings()
        return await _fix_wifi(task_lower)
    if any(w in task_lower for w in ("printer", "print")):
        return await _check_printer()
    if any(w in task_lower for w in ("sound", "audio", "speaker", "mic")):
        return await _run_troubleshooter("audio")
    if "bluetooth" in task_lower:
        if any(w in task_lower for w in ("toggle", "turn", "on", "off", "switch")):
            return await _open_bluetooth_settings()
        return await _check_bluetooth()

    return await _run_troubleshooter("devices")


async def _check_usb() -> str:
    try:
        import psutil

        partitions = await asyncio.to_thread(psutil.disk_partitions, all=True)
        usb_drives = [
            p
            for p in partitions
            if "removable" in p.opts.lower()
            or p.fstype.lower() in ("fat32", "exfat", "fat")
        ]

        # Open storage settings for the user
        try:
            await asyncio.to_thread(os.startfile, "ms-settings:storagesense")
        except Exception as exc:
            logger.debug("Failed to open storage settings: %s", exc)

        if not usb_drives:
            return (
                "No USB drives are connected right now.\n"
                "Please try unplugging and reconnecting the drive firmly, then ask me again."
            )
        lines = [f"Found {len(usb_drives)} USB drive(s) connected:\n"]
        for p in usb_drives:
            try:
                usage = await asyncio.to_thread(psutil.disk_usage, p.mountpoint)
                gb_free = usage.free / (1024**3)
                gb_total = usage.total / (1024**3)
                lines.append(
                    f"  Drive {p.mountpoint} — {gb_free:.1f} GB free of {gb_total:.1f} GB  ({p.fstype})"
                )
            except Exception:
                lines.append(f"  Drive {p.mountpoint} ({p.fstype})")

        lines.append("\nI have also opened your Storage settings for you.")
        return "\n".join(lines)
    except Exception as exc:
        return f"Could not check USB drives: {exc}"


async def _fix_wifi(task_lower: str) -> str:
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout

        if "disconnected" in output.lower() or not output.strip():
            # Only run non-privileged commands; privileged resets require admin
            flush_result = subprocess.run(
                ["ipconfig", "/flushdns"], capture_output=True, timeout=10
            )
            release_result = subprocess.run(
                ["ipconfig", "/release"], capture_output=True, timeout=10
            )
            renew_result = subprocess.run(
                ["ipconfig", "/renew"], capture_output=True, timeout=20
            )

            if flush_result.returncode == 0:
                return (
                    "Your Wi-Fi appeared disconnected. I flushed the DNS cache and renewed your IP.\n"
                    "Please wait a few seconds and check if your internet is working.\n"
                    "If the issue persists, try running as administrator for a full network reset."
                )
            return (
                "Your Wi-Fi appears disconnected but I couldn't reset the network.\n"
                "Try restarting your Wi-Fi adapter or running this application as administrator."
            )
            subprocess.run(
                ["netsh", "int", "ip", "reset"], capture_output=True, timeout=15
            )
            subprocess.run(["ipconfig", "/release"], capture_output=True, timeout=10)
            subprocess.run(["ipconfig", "/renew"], capture_output=True, timeout=20)
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
            return (
                "Your Wi-Fi appeared disconnected so I reset the network settings.\n"
                "Please wait a few seconds and check if your internet is working.\n"
                "You may need to reconnect to your Wi-Fi network."
            )

        ssid_line = next(
            (l for l in output.splitlines() if "SSID" in l and "BSSID" not in l), None
        )
        signal_line = next((l for l in output.splitlines() if "Signal" in l), None)
        ssid = ssid_line.split(":", 1)[-1].strip() if ssid_line else "Unknown"
        signal = signal_line.split(":", 1)[-1].strip() if signal_line else "Unknown"

        return (
            f"Your Wi-Fi is connected.\n"
            f"  Network: {ssid}\n"
            f"  Signal strength: {signal}\n\n"
            f"If you cannot load websites, try turning your router off and on again."
        )
    except Exception as exc:
        return f"Could not check Wi-Fi status: {exc}"


async def _check_printer() -> str:
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "powershell",
                "-Command",
                "Get-Printer | Select-Object Name,PrinterStatus | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return (
                "No printers found on your computer.\n"
                "Make sure the printer is turned on and connected, then ask me again."
            )
        import json

        printers = json.loads(result.stdout)
        if isinstance(printers, dict):
            printers = [printers]
        lines = [f"Found {len(printers)} printer(s):\n"]

        status_map = {
            0: "Paused",
            1: "Error",
            2: "PendingDeletion",
            3: "Ready",
            4: "PaperJam",
            5: "PaperOut",
            6: "ManualFeed",
        }

        for p in printers:
            status = p.get("PrinterStatus")
            status_text = (
                status_map.get(status, f"Status code: {status}")
                if status is not None
                else "Unknown"
            )
            lines.append(f"  {p.get('Name', 'Unknown')} — {status_text}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Could not check printers: {exc}"


async def _check_bluetooth() -> str:
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "powershell",
                "-Command",
                "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        # Open Bluetooth settings for the user
        try:
            await asyncio.to_thread(os.startfile, "ms-settings:bluetooth")
        except Exception:
            pass

        if result.returncode != 0 or not result.stdout.strip():
            return "No Bluetooth devices found. Make sure Bluetooth is turned on."
        import json

        devices = json.loads(result.stdout)
        if isinstance(devices, dict):
            devices = [devices]
        lines = [f"Found {len(devices)} Bluetooth device(s):\n"]
        for d in devices:
            lines.append(
                f"  {d.get('FriendlyName', 'Unknown')} — {d.get('Status', 'Unknown')}"
            )

        lines.append("\nI have also opened your Bluetooth settings for you.")
        return "\n".join(lines)
    except Exception as exc:
        return f"Could not check Bluetooth: {exc}"


async def _get_available_wifi_networks() -> str:
    try:
        # Open settings first for the user
        os.startfile("ms-settings:network-wifi")

        # Scan for networks
        result = subprocess.run(
            ["netsh", "wlan", "show", "networks"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout

        networks = []
        for line in output.splitlines():
            if "SSID" in line and ":" in line:
                ssid = line.split(":", 1)[1].strip()
                if ssid:
                    networks.append(ssid)

        if not networks:
            return (
                "I couldn't find any available Wi-Fi networks in range.\n"
                "I have opened your Wi-Fi settings so you can check if your Wi-Fi adapter is turned on."
            )

        msg = "I found the following Wi-Fi networks nearby:\n\n"
        msg += "\n".join([f"• {n}" for n in networks])
        msg += "\n\nI have also opened your Wi-Fi settings for you to connect."
        return msg
    except Exception as exc:
        return f"I had trouble listing the networks via text: {exc}"


async def _open_wifi_settings() -> str:
    try:
        os.startfile("ms-settings:network-wifi")
        return "I opened the Wi-Fi settings for you. You can turn Wi-Fi on or off using the switch there."
    except Exception as e:
        logger.exception("Failed to open Wi-Fi settings")
        return f"Failed to open Wi-Fi settings: {e}"


async def _open_bluetooth_settings() -> str:
    try:
        os.startfile("ms-settings:bluetooth")
        return "I opened the Bluetooth settings for you. You can turn Bluetooth on or off there."
    except Exception as e:
        logger.exception("Failed to open Bluetooth settings")
        return f"Failed to open Bluetooth settings: {e}"


async def _run_troubleshooter(category: str) -> str:
    troubleshooter_ids = {
        "audio": "msdt.exe -id AudioPlaybackDiagnostic",
        "internet": "msdt.exe -id NetworkDiagnosticsWeb",
        "printer": "msdt.exe -id PrinterDiagnostic",
        "devices": "msdt.exe -id DeviceDiagnostic",
    }
    import shlex

    cmd = troubleshooter_ids.get(category, "msdt.exe -id DeviceDiagnostic")
    args = shlex.split(cmd)
    try:
        subprocess.Popen(args, shell=False)
        return (
            f"I opened the Windows {category} troubleshooter for you.\n"
            f"Please follow the on-screen steps — it will try to fix the problem automatically."
        )
    except Exception as exc:
        return f"Could not open the troubleshooter: {exc}"
