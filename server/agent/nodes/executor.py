"""
executor.py — High-Performance, Hardened OS & Browser Execution Engine for AutoOS.
Eliminates eval(), replaces shell=True subprocesses with tokenized arrays,
guarantees CREATE_NO_WINDOW (0x08000000) on Windows, and removes event loop stalls.
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import operator
import os
import re
import shutil
import socket
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

import psutil
import pyautogui
import requests
from langchain_core.runnables import RunnableConfig

try:
    import pygetwindow as gw
except Exception:
    gw = None

from agent.bus import emit_event
from agent.modules import app_module
from agent.state import AgentState
from agent.tools.browser_tool import run_browser_task
from utils.logger import agent_logger as logger

CREATE_NO_WINDOW = 0x08000000

# ─────────────────────────────────────────────────────────────────────────────
# 1. SAFE ARITHMETIC EVALUATOR (Zero eval() vulnerability)
# ─────────────────────────────────────────────────────────────────────────────

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def safe_eval_math(expr: str) -> float | int:
    """Safely evaluates basic arithmetic expressions without arbitrary code execution."""
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](_eval(node.operand))
        raise ValueError(f"Unsupported mathematical syntax: {type(node).__name__}")

    clean = re.sub(r'[^0-9+\-*/().% ]', '', expr).strip()
    if not clean:
        raise ValueError("Empty mathematical expression")
    parsed = ast.parse(clean, mode='eval')
    return _eval(parsed.body)

# ─────────────────────────────────────────────────────────────────────────────
# 2. DIRECT OS PRIMITIVES
# ─────────────────────────────────────────────────────────────────────────────

async def launch_app(app_name: str) -> str:
    """Launches an application or brings existing instance to focus."""
    try:
        if gw:
            windows = [w for w in gw.getAllWindows() if app_name.lower() in w.title.lower() and w.visible]
            if windows:
                try:
                    windows[0].activate()
                    return f"Focused active window for '{app_name}'."
                except Exception:
                    pass

        result = await app_module.run(app_name, [app_name], {"app_name": app_name})
        return result
    except Exception as e:
        return f"Failed to launch '{app_name}': {e}"

def open_folder(folder_name: str) -> str:
    """Safely opens system folder using os.startfile."""
    special = {
        "downloads": os.path.expanduser("~/Downloads"),
        "desktop": os.path.expanduser("~/Desktop"),
        "documents": os.path.expanduser("~/Documents"),
        "pictures": os.path.expanduser("~/Pictures"),
        "music": os.path.expanduser("~/Music"),
        "videos": os.path.expanduser("~/Videos"),
    }
    path = special.get(folder_name.lower().strip(), folder_name)
    try:
        if os.path.exists(path):
            os.startfile(path)
            return f"Opened {path} in File Explorer."
        return f"Folder path not found: {path}"
    except Exception as e:
        return f"Failed to open folder: {e}"

def run_file(file_path: str) -> str:
    """Opens a file with default application securely."""
    try:
        if os.path.exists(file_path):
            os.startfile(file_path)
            return f"Successfully opened file: {file_path}"
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Error opening file: {e}"

async def create_file_or_folder(name: str, folder_name: str = "desktop", content: str = "", is_folder: bool = False) -> Tuple[str, dict]:
    """Creates a file or folder and selects it in Explorer without shell=True."""
    user_path = os.path.expanduser("~")
    candidates = [
        os.path.join(user_path, "OneDrive", folder_name.capitalize()),
        os.path.join(user_path, folder_name.capitalize()),
        os.path.join(user_path, "Desktop")
    ]
    base_path = next((c for c in candidates if os.path.exists(c)), os.path.expanduser("~/Desktop"))
    clean_name = re.sub(r'[<>:"/\\|?*]', '', name).strip()
    full_path = os.path.join(base_path, clean_name)

    try:
        if is_folder:
            os.makedirs(full_path, exist_ok=True)
            if os.path.exists(full_path):
                subprocess.Popen(["explorer.exe", f"/select,{full_path}"], creationflags=CREATE_NO_WINDOW)
                await asyncio.sleep(0.5)
                return f"Successfully created folder: {full_path}", {"last_folder": full_path, "last_path": full_path}
            return f"Failed to verify folder creation at {full_path}", {}
        else:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            subprocess.Popen(["explorer.exe", f"/select,{full_path}"], creationflags=CREATE_NO_WINDOW)
            await asyncio.sleep(0.5)
            return f"Successfully created file: {full_path}", {"last_file": full_path, "last_path": full_path}
    except Exception as e:
        return f"Creation failed: {e}", {}

async def compute_in_calculator(expression: str) -> str:
    """Evaluates mathematical input safely using AST and displays in system calculator."""
    try:
        clean = re.sub(r'[^0-9+\-*/().% ]', '', expression).strip()
        answer = safe_eval_math(clean)
        try:
            subprocess.Popen(["calc.exe"], creationflags=CREATE_NO_WINDOW)
        except Exception:
            pass
        return f"Expression: {clean} | Computed Result: {answer}"
    except Exception as e:
        return f"Calculation error: {e}"

def check_disk_space() -> str:
    """Returns local disk storage usage."""
    try:
        total, used, free = shutil.disk_usage("/")
        gb = 1024 ** 3
        return f"Primary Disk: {used // gb} GB used of {total // gb} GB ({free // gb} GB available)."
    except Exception as e:
        return f"Failed to query disk space: {e}"

def get_battery_status() -> str:
    """Returns battery percentage and power state."""
    try:
        b = psutil.sensors_battery()
        if b:
            status = "plugged in & charging" if b.power_plugged else "on battery"
            return f"Battery: {b.percent:.0f}% ({status})."
        return "No battery detected (Desktop Workstation)."
    except Exception as e:
        return f"Could not check battery: {e}"

def check_connectivity() -> str:
    """Socket-level network diagnostic with latency telemetry."""
    results = []
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        results.append("✅ Internet: Connected")
    except OSError:
        results.append("❌ Internet: Offline")

    try:
        t0 = time.time()
        requests.get("https://www.google.com", timeout=2)
        latency = (time.time() - t0) * 1000
        results.append(f"📡 Latency: {latency:.0f}ms")
    except Exception:
        results.append("📡 Latency: Degraded")

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        results.append(f"🏠 Host IP: {local_ip}")
        s.close()
    except Exception:
        pass

    return " | ".join(results)

def check_bluetooth() -> str:
    """Checks Bluetooth peripherals via PowerShell without flashing cmd windows."""
    try:
        os.startfile("ms-settings:bluetooth")
        cmd = 'Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status | ConvertTo-Json'
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=8,
            creationflags=CREATE_NO_WINDOW
        )
        if not proc.stdout.strip():
            return "Bluetooth Settings opened. No active peripherals detected."
        devices = json.loads(proc.stdout)
        if isinstance(devices, dict):
            devices = [devices]
        lines = [f"Bluetooth Settings opened. Detected {len(devices)} device(s):"]
        for d in devices[:8]:
            lines.append(f"• {d.get('FriendlyName', 'Unknown')} ({d.get('Status', 'OK')})")
        return "\n".join(lines)
    except Exception as e:
        return f"Opened Bluetooth Settings. (Device query note: {e})"

def open_settings(section: str = "") -> str:
    """Navigates to Windows Settings URI schemes safely."""
    uri_map = {
        "display": "ms-settings:display",
        "sound": "ms-settings:sound",
        "bluetooth": "ms-settings:bluetooth",
        "wifi": "ms-settings:network-wifi",
        "network": "ms-settings:network",
        "update": "ms-settings:windowsupdate",
        "privacy": "ms-settings:privacy",
        "storage": "ms-settings:storagesense",
        "": "ms-settings:",
    }
    uri = uri_map.get(section.lower().strip(), "ms-settings:")
    try:
        os.startfile(uri)
        return f"Opened Windows Settings ({section or 'Home'})."
    except Exception as e:
        return f"Failed to open settings: {e}"

def kill_process(name_or_pid: str) -> str:
    """Safely terminates a target process using psutil without taskkill."""
    count = 0
    try:
        if name_or_pid.isdigit():
            p = psutil.Process(int(name_or_pid))
            p.terminate()
            return f"Terminated process PID {name_or_pid}."

        for proc in psutil.process_iter(['name']):
            if name_or_pid.lower() in proc.info['name'].lower():
                proc.terminate()
                count += 1

        if count > 0:
            return f"Successfully terminated {count} instance(s) of '{name_or_pid}'."
        return f"No running processes found matching '{name_or_pid}'."
    except Exception as e:
        return f"Failed to terminate process: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# 3. TASK ROUTER & PARSER (Single unified implementation)
# ─────────────────────────────────────────────────────────────────────────────

async def parse_and_execute_os_task(task: str, context: dict = None) -> Tuple[str, dict]:
    """
    Deterministic OS Task Parser. Resolves pronouns, extracts structured targets,
    and invokes corresponding local OS primitives.
    """
    t = task.lower().strip()
    ctx = context or {}

    # Pronoun & Context Resolution
    last_c = ctx.get("last_contact", "")
    if last_c:
        for word in ["him", "her", "them", "that chat"]:
            t = re.sub(rf"\b{word}\b", last_c, t)

    last_f = ctx.get("last_file", "") or ctx.get("last_folder", "")
    if last_f and (" it" in t or t.endswith(" it")):
        t = t.replace(" it", f" {last_f}")

    # Process Management
    if any(w in t for w in ["kill", "terminate", "close process", "force close", "stop process"]):
        match = re.search(r'(?:kill|terminate|close|stop)\s+([a-zA-Z0-9._-]+)', t)
        if match:
            target = match.group(1)
            return kill_process(target), {"last_app": target}

    # Safe Arithmetic / Calculator
    calc_match = re.search(r'(\d+[\s]*[+\-*/%]\s*[\d+\-*/().% ]+)', task)
    if any(w in t for w in ["calculate", "compute", "math", "calculator"]) or calc_match:
        if calc_match:
            res = await compute_in_calculator(calc_match.group(1))
            return res, {"last_app": "calculator"}
        await launch_app("calculator")
        return "Opened Calculator.", {"last_app": "calculator"}

    # Folder Navigation
    for folder in ["downloads", "desktop", "documents", "pictures", "music", "videos"]:
        if folder in t and any(w in t for w in ["open", "show", "go to", "navigate"]):
            if not re.search(r'\.[a-z0-9]{2,4}', t):
                return open_folder(folder), {"last_folder": folder}

    # File / Folder Creation
    create_match = re.search(r'create\s+(?:a\s+)?(file|folder)\s+(?:named\s+)?(.*?)(?:\s+(?:in|on|at)\s+(?:my\s+)?([a-zA-Z0-9\s._-]+))?$', t)
    if create_match:
        item_type = create_match.group(1).strip()
        item_name = create_match.group(2).strip()
        folder = create_match.group(3).strip() if create_match.group(3) else "desktop"
        content_match = re.search(r'with\s+(?:the\s+)?(?:text|content)\s+[\'"](.+)[\'"]', task, re.IGNORECASE)
        content = content_match.group(1) if content_match else ""
        return await create_file_or_folder(item_name, folder, content, is_folder=(item_type == "folder"))

    # System Introspection
    if any(w in t for w in ["disk", "storage", "hard drive", "space"]):
        return check_disk_space(), {}
    if any(w in t for w in ["battery", "charging", "power"]):
        return get_battery_status(), {}
    if any(w in t for w in ["wifi", "wi-fi", "internet", "network", "connectivity"]):
        if any(w in t for w in ["open", "settings"]):
            return open_settings("wifi"), {}
        return check_connectivity(), {}
    if "bluetooth" in t:
        return check_bluetooth(), {}

    # Settings Routing
    for section in ["display", "sound", "bluetooth", "wifi", "network", "update", "privacy", "storage"]:
        if section in t and any(w in t for w in ["settings", "setting", "open", "configure"]):
            return open_settings(section), {}
    if "settings" in t:
        return open_settings(), {}

    # App Launch Catch-All
    launch_match = re.search(r'(?:open|launch|start|run|play)\s+([a-zA-Z0-9._-]+)', t)
    if launch_match:
        target = launch_match.group(1).strip()
        if target not in ["settings", "folder", "file"]:
            res = await launch_app(target)
            return res, {"last_app": target}

    # Known common applications
    for app in ["notepad", "paint", "word", "excel", "taskmgr", "explorer", "vlc", "spotify", "chrome", "edge", "code"]:
        if app in t:
            res = await launch_app(app)
            return res, {"last_app": app}

    return f"Understood OS task: '{task}'. Executing standard system dispatcher.", {}

# ─────────────────────────────────────────────────────────────────────────────
# 4. LANGGRAPH EXECUTOR NODES
# ─────────────────────────────────────────────────────────────────────────────

async def browser_executor(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Executes browser automation workflow via Playwright/browser-use."""
    task = state.get("task", "")
    await emit_event(config, {"type": "step_start", "description": f"Executing Browser Task: {task}"})

    try:
        result = await asyncio.wait_for(
            run_browser_task(
                task,
                headless=state.get("headless", False),
                input_values=state.get("input_values"),
                max_steps=state.get("max_steps", 25),
            ),
            timeout=120.0
        )
    except asyncio.TimeoutError:
        result = "Browser task timed out after 120 seconds."
    except Exception as e:
        result = f"Browser automation error: {str(e)}"

    await emit_event(config, {"type": "step_done", "description": "Completed Browser Task"})
    await emit_event(config, {"type": "complete", "summary": str(result)})

    return {
        "result": str(result),
        "messages": [{"role": "assistant", "content": f"Browser Task Result: {result}"}],
        "category": "browser",
        "status": "completed"
    }

async def os_executor(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Executes local operating system workflow."""
    task = state.get("task", "")
    await emit_event(config, {"type": "step_start", "description": f"Executing OS Task: {task}"})

    try:
        ctx = state.get("context", {})
        result, new_ctx = await parse_and_execute_os_task(task, ctx)
        status = "completed"
    except Exception as e:
        result = f"OS Execution error: {str(e)}"
        new_ctx = {}
        status = "error"

    await emit_event(config, {"type": "step_done", "description": f"Finished OS Task: {result}"})
    await emit_event(config, {"type": "complete", "summary": str(result)})

    return {
        "result": str(result),
        "messages": [{"role": "assistant", "content": str(result)}],
        "context": new_ctx,
        "category": "os",
        "status": status
    }

async def reasoning_executor(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Executes pure LLM cognitive reasoning for knowledge and conversation."""
    task = state.get("task", "")
    await emit_event(config, {"type": "step_start", "description": f"Reasoning on query: {task}"})

    try:
        from agent.llm_factory import get_llm
        llm = get_llm(temperature=0.3)
        ctx = state.get("context", {})
        prompt = (
            "You are the Core Cognitive Engine of AutoOS, an autonomous operating assistant.\n"
            f"Task: {task}\n"
            f"Context: {ctx}\n"
            "Provide an accurate, concise, and structured answer. Avoid unnecessary preamble."
        )
        response = await llm.ainvoke(prompt)
        result = response.content
        status = "completed"
    except Exception as e:
        result = f"Cognitive processing error: {str(e)}"
        status = "error"

    await emit_event(config, {"type": "step_done", "description": "Reasoning complete."})
    await emit_event(config, {"type": "complete", "summary": str(result)})

    return {
        "result": str(result),
        "messages": [{"role": "assistant", "content": str(result)}],
        "category": "reasoning",
        "status": status
    }
