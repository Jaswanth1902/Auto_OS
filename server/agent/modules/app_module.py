"""
app_module.py — Smart application launcher for AutoOS.

Uses action_params.search_aliases from the planner for precise matching.

Strategy (in priority order):
  1. Windows Registry App Paths
  2. Direct .exe search using search_aliases across common install dirs
  3. Start Menu / Desktop shortcut (.lnk) search
  4. Shell Execute with the clean app name / URI scheme
  5. Clipboard-paste into Start Menu (avoids typewrite char-by-char bug)
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from typing import Any

try:
    import winreg
except ImportError:
    winreg = None
from pathlib import Path

import pyautogui

logger = logging.getLogger("AutoOS.app_module")

_SEARCH_ROOTS = [
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("LOCALAPPDATA") or r"C:\Users\Default\AppData\Local")
    / "Programs",
    Path(os.environ.get("APPDATA") or r"C:\Users\Default\AppData\Roaming")
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs",
    Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
    Path(os.path.expanduser("~")) / "Desktop",
    Path(os.path.expanduser("~")) / "AppData" / "Local",
]


async def run(task: str, entities: list[str], action_params: dict[str, Any]) -> str:
    # Prefer structured params from the planner
    app_name: str = action_params.get("app_name") or (entities[0] if entities else task)
    aliases: list[str] = action_params.get("search_aliases") or [app_name]

    logger.info("Launching app: %r aliases=%s", app_name, aliases)

    strategies = [
        lambda: _try_registry(aliases),
        lambda: _try_direct_search(aliases),
        lambda: _try_shortcut_search(aliases),
        lambda: _try_shell_execute(app_name, aliases),
        lambda: _try_start_menu_search(app_name),
    ]

    # Special handling for app interaction (e.g. calculation)
    action: str = action_params.get("action", "").lower()
    input_text: str = action_params.get("input", "")

    for strategy in strategies:
        result = await strategy()
        if result["success"]:
            logger.info("Launch succeeded via %s", result.get("method", "unknown"))

            if action == "interact" or input_text:
                await asyncio.sleep(1.5)  # Wait for app to focus
                return await _interact_with_app(result["message"], input_text)

            return result["message"]

    return (
        f"Could not find '{app_name}' on your computer. "
        "Make sure it is installed and try again."
    )


async def _try_registry(aliases: list[str]) -> dict:
    if not winreg:
        return {"success": False}
    for alias in aliases:
        exe = alias if alias.lower().endswith(".exe") else alias + ".exe"
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}"
                with winreg.OpenKey(hive, key_path) as key:
                    exe_path, _ = winreg.QueryValueEx(key, "")
                    if exe_path and Path(exe_path).exists():
                        subprocess.Popen([exe_path], shell=False)
                        return {
                            "success": True,
                            "method": "registry",
                            "message": f"Launched {aliases[0]} successfully.",
                        }
            except FileNotFoundError:
                continue
            except Exception as exc:
                logger.debug("Registry key error: %s", exc)
    return {"success": False}


async def _try_direct_search(aliases: list[str]) -> dict:
    """Walk install dirs looking for exes matching any alias."""
    terms = [
        a.lower().replace(" ", "").replace("-", "").replace("_", "") for a in aliases
    ]
    candidates: list[Path] = []

    for root in _SEARCH_ROOTS:
        if not root.exists():
            continue
        try:
            # Only search 2 levels deep to avoid hanging
            for p in root.iterdir():
                if p.is_dir():
                    try:
                        for exe in p.glob("*.exe"):
                            stem = (
                                exe.stem.lower()
                                .replace(" ", "")
                                .replace("-", "")
                                .replace("_", "")
                            )
                            if any(t in stem or stem in t for t in terms):
                                candidates.append(exe)
                    except Exception:
                        continue
                elif p.suffix.lower() == ".exe":
                    stem = (
                        p.stem.lower()
                        .replace(" ", "")
                        .replace("-", "")
                        .replace("_", "")
                    )
                    if any(t in stem or stem in t for t in terms):
                        candidates.append(p)
        except Exception:
            continue

    if not candidates:
        return {"success": False}

    target = aliases[0].lower().replace(" ", "").replace("-", "").replace("_", "")

    def score(p):
        stem = p.stem.lower().replace(" ", "").replace("-", "").replace("_", "")
        if stem == target:
            match_score = 0
        elif stem.startswith(target) or stem.endswith(target):
            match_score = 1
        elif target in stem:
            match_score = 2
        else:
            match_score = 3
        return (match_score, len(str(p)))

    best = min(candidates, key=score)
    logger.debug("Direct search matched: %s", best)
    subprocess.Popen([str(best)], shell=False)
    return {
        "success": True,
        "method": "direct_search",
        "message": f"Launched {aliases[0]} from {best.parent.name}.",
    }


async def _try_shortcut_search(aliases: list[str]) -> dict:
    terms = [a.lower() for a in aliases]
    shortcut_roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu",
        Path(r"C:\ProgramData\Microsoft\Windows\Start Menu"),
        Path(os.path.expanduser("~")) / "Desktop",
        Path(r"C:\Users\Public\Desktop"),
    ]
    for root in shortcut_roots:
        if not root.exists():
            continue
        try:
            for lnk in root.rglob("*.lnk"):
                stem_lower = lnk.stem.lower()
                if any(t in stem_lower for t in terms):
                    os.startfile(str(lnk))
                    return {
                        "success": True,
                        "method": "shortcut",
                        "message": f"Launched {aliases[0]} via shortcut.",
                    }
        except Exception as exc:
            logger.debug("Shortcut search error: %s", exc)
    return {"success": False}


async def _try_shell_execute(app_name: str, aliases: list[str]) -> dict:
    # Modern UWP Apps and URI schemes
    uri_map = {
        "calculator": "calc:",
        "calc": "calc:",
        "photos": "ms-photos:",
        "photo": "ms-photos:",
        "settings": "ms-settings:",
        "clock": "ms-clock:",
        "calendar": "outlookcal:",
        "mail": "outlookmail:",
        "store": "ms-windows-store:",
        "weather": "bingweather:",
        "whatsapp": "whatsapp:",
        "spotify": "spotify:",
        "edge": "microsoft-edge:",
        "browser": "https://google.com",
    }

    potential_uris = []
    # Fuzzy match aliases against uri_map
    for alias in aliases + [app_name]:
        a_low = alias.lower().strip()
        # Direct match
        if a_low in uri_map:
            potential_uris.append(uri_map[a_low])
        # Fuzzy match (e.g. "claculator" -> "calculator")
        else:
            for key, uri in uri_map.items():
                if a_low in key or key in a_low:
                    potential_uris.append(uri)
                    break

    import shlex
    import shutil

    candidates = (
        potential_uris
        + [app_name]
        + aliases
        + [
            "calc.exe",
            "mspaint.exe",
            "notepad.exe",
        ]
    )

    for candidate in candidates:
        try:
            if ":" in candidate and any(u in candidate for u in uri_map.values()):
                os.startfile(candidate)
            else:
                args = shlex.split(candidate)
                if not args:
                    continue
                exe_path = shutil.which(args[0])
                if not exe_path:
                    continue
                args[0] = exe_path
                proc = subprocess.Popen(args, shell=False)
                await asyncio.sleep(0.5)
                if proc.poll() is not None:
                    continue

            return {
                "success": True,
                "method": "shell_execute",
                "message": f"Launched {app_name}.",
            }
        except Exception as exc:
            logger.debug("Shell execute '%s' failed: %s", candidate, exc)

    return {"success": False}


async def _try_start_menu_search(app_name: str) -> dict:
    """Last resort: clipboard paste into Start Menu (avoids typewrite bug)."""
    import tkinter as tk

    root_tk = None
    try:
        root_tk = tk.Tk()
        root_tk.withdraw()
        root_tk.clipboard_clear()
        root_tk.clipboard_append(app_name)
        root_tk.update()

        pyautogui.press("win")
        await asyncio.sleep(0.7)
        pyautogui.hotkey("ctrl", "v")
        await asyncio.sleep(1.2)
        pyautogui.press("enter")
        await asyncio.sleep(0.5)

        return {
            "success": True,
            "method": "start_menu",
            "message": f"Searched Start Menu for '{app_name}' and launched the top result.",
        }
    except Exception as exc:
        logger.warning("Start Menu fallback failed: %s", exc)
        return {"success": False}
    finally:
        if root_tk is not None:
            try:
                root_tk.destroy()
            except Exception:
                pass


async def _interact_with_app(launch_msg: str, input_text: str) -> str:
    """Type text into the active window."""
    if not input_text:
        return launch_msg

    try:
        # Sanitize input for calculator if needed
        # (e.g. "5 plus 5" -> "5+5=")
        processed_input = input_text.lower()
        processed_input = processed_input.replace("plus", "+").replace("minus", "-")
        processed_input = processed_input.replace("times", "*").replace(
            "multiplied by", "*"
        )
        processed_input = processed_input.replace("divided by", "/").replace(
            "equals", "="
        )

        if "=" not in processed_input and any(op in processed_input for op in "+-*/"):
            processed_input += "="

        pyautogui.write(processed_input, interval=0.1)
        return f"{launch_msg} I then typed: '{processed_input}'"
    except Exception as exc:
        logger.warning("Interaction failed: %s", exc)
        return f"{launch_msg} (Interaction failed: {exc})"
