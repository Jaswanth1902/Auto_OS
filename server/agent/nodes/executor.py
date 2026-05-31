import asyncio
import logging
import os
import re
import subprocess
import time
from typing import Any

import psutil
import pyautogui

try:
    import pygetwindow as gw
except:
    gw = None
from agent.bus import emit_event
from agent.modules import app_module
from agent.state import AgentState
from agent.tools.browser_tool import run_browser_task
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger("AutoOS.executor")

# ─────────────────────────────────────────
# DIRECT OS EXECUTOR — No LLM, No Hanging
# ─────────────────────────────────────────


async def launch_app(app_name: str) -> str:
    try:
        # Smart Focus: Check if already running to avoid "duplicate instances"
        try:
            import psutil
            import pygetwindow as gw

            # 1. Check for window by name
            windows = [
                w
                for w in gw.getAllWindows()
                if app_name.lower() in w.title.lower() and w.visible
            ]
            if windows:
                windows[0].activate()
                return f"Focused existing {app_name} window."

            # 2. Check process list for common app names
            for proc in psutil.process_iter(["name"]):
                if app_name.lower() in proc.info["name"].lower():
                    # Process is running but maybe window is hidden/minimized
                    # Try to bring it up via shell execute (most apps will focus existing if already running)
                    break
        except:
            pass

        # Use the robust app_module to find and launch the app
        result = await app_module.run(app_name, [app_name], {"app_name": app_name})
        return result
    except Exception as e:
        return f"Failed to open {app_name}: {e}"


def open_folder(folder_name: str) -> str:
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
        subprocess.Popen(f'explorer "{path}"', shell=True)
        time.sleep(1.5)
        return f"Opened {path} in File Explorer."
    except Exception as e:
        return f"Failed to open folder: {e}", {}


def run_file(file_path: str) -> str:
    try:
        if os.path.exists(file_path):
            os.startfile(file_path)
            return f"Successfully opened: {file_path}"
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Error opening file: {e}"


async def create_file_or_folder(
    name: str, folder_name: str = "desktop", content: str = "", is_folder: bool = False
) -> str:
    # Resolve the true Windows path (handling OneDrive)
    user_path = os.path.expanduser("~")

    # Priority: 1. OneDrive 2. Local
    candidates = [
        os.path.join(user_path, "OneDrive", folder_name.capitalize()),
        os.path.join(user_path, folder_name.capitalize()),
        os.path.join(user_path, "Desktop"),  # Fallback
    ]

    base_path = next(
        (c for c in candidates if os.path.exists(c)), os.path.expanduser("~/Desktop")
    )

    # Sanitize the name: Windows doesn't allow these: < > : " / \ | ? *
    clean_name = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    full_path = os.path.join(base_path, clean_name)

    try:
        if is_folder:
            os.makedirs(full_path, exist_ok=True)
            if os.path.exists(full_path):
                # Open explorer and highlight the new folder
                subprocess.Popen(f'explorer /select,"{full_path}"', shell=True)
                await asyncio.sleep(1.5)

                # Use "Desktop DOM" (Window Management) to focus and refresh
                try:
                    import pyautogui
                    import pygetwindow as gw

                    # Try to find the explorer window
                    title = os.path.basename(base_path)
                    wa_windows = [w for w in gw.getWindowsWithTitle(title) if w.visible]
                    if wa_windows:
                        wa_windows[0].activate()
                        pyautogui.press("f5")  # Refresh the view
                except:
                    pass

                return f"Successfully created folder at: {full_path}", {
                    "last_folder": full_path,
                    "last_path": full_path,
                }
            return f"Failed to verify folder creation at {full_path}", {}
        else:
            with open(full_path, "w") as f:
                f.write(content)
            # Open explorer and highlight the new file
            subprocess.Popen(f'explorer /select,"{full_path}"', shell=True)
            return f"Successfully created file at: {full_path}", {
                "last_file": full_path,
                "last_path": full_path,
            }
    except Exception as e:
        return f"File creation failed: {e}", {}


def compute_in_calculator(expression: str) -> str:
    try:
        import pyautogui

        subprocess.Popen("calc.exe", shell=True)
        time.sleep(2.5)
        # Clean expression - only allow valid calculator chars
        clean = re.sub(r"[^0-9+\-*/().]", "", expression)
        pyautogui.write(clean, interval=0.1)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(0.5)
        # Also compute answer in Python
        answer = eval(clean)
        return f"Opened calculator and entered '{clean}'. The answer is {answer}."
    except Exception as e:
        return f"Calculator failed: {e}"


def check_disk_space() -> str:
    import shutil

    total, used, free = shutil.disk_usage("/")
    return (
        f"Your disk — "
        f"Total: {total // (2**30)} GB, "
        f"Used: {used // (2**30)} GB, "
        f"Free: {free // (2**30)} GB"
    )


def get_battery_status() -> str:
    try:
        import psutil

        b = psutil.sensors_battery()
        if b:
            status = "charging" if b.power_plugged else "not charging"
            return f"Battery is at {b.percent:.0f}% and is {status}."
        return "No battery found (desktop PC)."
    except Exception as e:
        return f"Could not check battery: {e}"


def check_connectivity() -> str:
    """
    Terminal-free network diagnostic using Python's socket and requests.
    """
    import socket

    import requests

    results = []

    # 1. Check Local Gateway
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        results.append("✅ Internet: Connected")
    except OSError:
        results.append("❌ Internet: Offline")

    # 2. Check Latency (Google)
    try:
        start = time.time()
        requests.get("https://www.google.com", timeout=3)
        latency = (time.time() - start) * 1000
        results.append(f"📡 Latency: {latency:.0f}ms")
    except:
        results.append("📡 Latency: Timeout")

    # 3. Get Local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        results.append(f"🏠 Local IP: {local_ip}")
        s.close()
    except:
        pass

    return " | ".join(results)


def check_bluetooth() -> str:
    try:
        # Open settings as requested by the user
        os.startfile("ms-settings:bluetooth")
        # Run PowerShell to get devices
        cmd = "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status | ConvertTo-Json"
        result = subprocess.run(
            ["powershell", "-Command", cmd], capture_output=True, text=True, timeout=10
        )
        if not result.stdout.strip():
            return "No Bluetooth devices detected."
        import json

        devices = json.loads(result.stdout)
        if isinstance(devices, dict):
            devices = [devices]
        lines = [f"Found {len(devices)} Bluetooth device(s):"]
        for d in devices[:10]:
            lines.append(f"• {d.get('FriendlyName')} ({d.get('Status')})")
        return "\n".join(lines)
    except Exception as e:
        return f"Bluetooth check failed: {e}"


def open_settings(section: str = "") -> str:
    try:
        uri_map = {
            "display": "ms-settings:display",
            "sound": "ms-settings:sound",
            "bluetooth": "ms-settings:bluetooth",
            "wifi": "ms-settings:network-wifi",
            "update": "ms-settings:windowsupdate",
            "privacy": "ms-settings:privacy",
            "storage": "ms-settings:storagesense",
            "": "ms-settings:",
        }
        uri = uri_map.get(section.lower().strip(), "ms-settings:")
        os.startfile(uri)
        time.sleep(1.5)
        return f"Opened Windows Settings{(' - ' + section) if section else ''}."
    except Exception as e:
        return f"Failed to open settings: {e}"


async def open_whatsapp_chat(contact_name: str) -> str:
    try:
        # 1. Launch/Show WhatsApp
        await launch_app("whatsapp")
        await asyncio.sleep(5)

        # 2. Force window focus
        if gw:
            try:
                wa_windows = [
                    w for w in gw.getWindowsWithTitle("WhatsApp") if w.visible
                ]
                if wa_windows:
                    wa_windows[0].activate()
                    await asyncio.sleep(1)
            except:
                pass

        # 3. Search for the contact (Ctrl+F)
        # We try twice to be sure
        for _ in range(2):
            pyautogui.hotkey("ctrl", "f")
            await asyncio.sleep(0.5)

        pyautogui.write(contact_name, interval=0.1)
        await asyncio.sleep(2)  # Wait for search results

        # 4. Open the chat
        pyautogui.press("enter")
        await asyncio.sleep(1)
        return f"Opened WhatsApp and focused on '{contact_name}'.", {
            "last_contact": contact_name,
            "last_app": "whatsapp",
        }
    except Exception as e:
        return f"Could not open specific chat: {e}", {}


async def quick_send_whatsapp(message: str) -> str:
    try:
        # 1. Bring WhatsApp to front
        await launch_app("whatsapp")
        await asyncio.sleep(1)

        # 2. Directly type and send
        pyautogui.write(message, interval=0.05)
        pyautogui.press("enter")
        return f'Sent to active chat: "{message}".', {"last_app": "whatsapp"}
    except Exception as e:
        return f"Failed to send quick message: {e}", {}


async def send_whatsapp_message(
    contact_name: str, message: str, context: dict[str, str] | None = None
) -> str:
    try:
        # Optimization: If we are already in this chat, skip navigation!
        ctx = context or {}
        last_c = ctx.get("last_contact", "").lower()
        if contact_name.lower() == last_c and last_c != "":
            return await quick_send_whatsapp(message)

        # 1. Open the chat first
        res, ctx_nav = await open_whatsapp_chat(contact_name)
        if "Could not" in res:
            return res, {}
        await asyncio.sleep(1.5)
        # 2. Type and send
        pyautogui.write(message, interval=0.05)
        pyautogui.press("enter")
        return f"Sent message to '{contact_name}': \"{message}\".", {
            "last_contact": contact_name,
            "last_app": "whatsapp",
        }
    except Exception as e:
        return f"Failed to send message: {e}", {}


# ─────────────────────────────────────────
# SMART TASK PARSER — No LLM needed
# ─────────────────────────────────────────


async def parse_and_execute_os_task( # type: ignore
    
    task: str, context: dict[str, str] | None = None
) -> tuple[str, dict]:
    t = task.lower().strip()
    ctx = context or {}
    new_ctx: dict[str, str] = {}

    # 1. CONTEXT RESOLUTION (Pronouns)
    # ... (rest of logic) ...

    # 2. EXECUTION LOGIC
    # Process Management
    if any(w in t for w in ["kill", "terminate", "close process", "force close"]):
        # Extract app name after the verb
        match = re.search(r"(?:kill|terminate|close|stop)\s+([a-zA-Z0-9.]+)", t)
        if match:
            return kill_process(match.group(1)), {"last_app": match.group(1)}

    # Calculator
    # ...

    # Wifi/Network
    if any(w in t for w in ["wifi", "wi-fi", "internet", "network", "connection"]):
        if any(w in t for w in ["turn", "on", "off", "toggle", "switch", "connect"]):
            return open_settings("wifi"), {}
        return check_connectivity(), {}

    if "bluetooth" in t:
        if any(w in t for w in ["turn", "on", "off", "toggle", "switch", "connect"]):
            return open_settings("bluetooth")
        return check_bluetooth()

    # Settings
    for section in [
        "display",
        "sound",
        "bluetooth",
        "wifi",
        "update",
        "privacy",
        "storage",
    ]:
        if section in t and any(
            w in t
            for w in ["settings", "setting", "open", "go to", "turn", "on", "off"]
        ):
            return open_settings(section)
    if "settings" in t:
        return open_settings(), {}

    return (
        f"I understood this is an OS task but I'm not sure how to handle: '{task}'. Please be more specific.",
        {},
    )


# ─────────────────────────────────────────
# BROWSER EXECUTOR
# ─────────────────────────────────────────


async def browser_executor(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    task = state.get("task", "")

    await emit_event(
        config, {"type": "step_start", "description": f"Starting browser task: {task}"}
    )

    try:
        result = await asyncio.wait_for(
            run_browser_task(
                task,
                headless=state.get("headless"),
                input_values=state.get("input_values"),
                max_steps=state.get("max_steps"),
            ),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        result = "Browser task timed out after 2 minutes. Please try again."
    except Exception as e:
        result = f"Browser task failed: {str(e)}"

    await emit_event(
        config, {"type": "step_done", "description": "Completed browser task"}
    )
    await emit_event(config, {"type": "complete", "summary": result})

    # Detect current platform for context persistence
    new_ctx: dict[str, str] = {}
    if "spotify.com" in str(result).lower() or "spotify" in task.lower():
        new_ctx["last_url"] = "https://open.spotify.com"
        new_ctx["last_app"] = "spotify"
    elif "youtube.com" in str(result).lower() or "youtube" in task.lower():
        new_ctx["last_url"] = "https://www.youtube.com"
        new_ctx["last_app"] = "youtube"

    return {
        "result": result,
        "messages": [
            {"role": "assistant", "content": f"Browser Task Result: {result}"}
        ],
        "context": new_ctx,
    }


# ─────────────────────────────────────────
# OS EXECUTOR — Direct execution, no LLM
# ─────────────────────────────────────────

# ─────────────────────────────────────────
# REASONING EXECUTOR
# ─────────────────────────────────────────


async def reasoning_executor(
    state: AgentState, config: RunnableConfig
) -> dict[str, Any]:
    task = state.get("task", "")

    await emit_event(
        config, {"type": "step_start", "description": f"Thinking about: {task}"}
    )

    try:
        from agent.llm_factory import get_llm

        llm = get_llm(
            temperature=0.7
        )  # Slightly higher temperature for "creative" reasoning

        # Pull in context from Memory to help reasoning
        ctx = state.get("context", {})

        prompt = f"""You are the Reasoning Engine of AutoOS. 
        Current Task: {task}
        Context: {ctx}
        
        Provide a clear, helpful, and accurate response. If this is a math or physics problem, show your work briefly.
        Keep it friendly and concise."""

        response = await llm.ainvoke(prompt)
        result = response.content
    except Exception as e:
        result = f"Reasoning failed: {str(e)}"

    await emit_event(config, {"type": "step_done", "description": "Finished thinking."})
    await emit_event(config, {"type": "complete", "summary": result})

    return {"result": result, "messages": [{"role": "assistant", "content": result}]}


async def os_executor(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    task = state.get("task", "")
    t = task.lower()

    # Human-friendly status message
    if "calculator" in t or any(op in task for op in ["+", "-", "*", "/"]):
        status_msg = "Opening your calculator now..."
    elif any(f in t for f in ["downloads", "desktop", "documents", "folder"]):
        status_msg = "Opening that folder for you..."
    elif "notepad" in t:
        status_msg = "Opening Notepad for you..."
    elif "settings" in t:
        status_msg = "Opening Settings for you..."
    elif "wifi" in t or "wi-fi" in t or "internet" in t:
        status_msg = "Checking your internet connection..."
    elif "battery" in t:
        status_msg = "Checking your battery status..."
    elif "disk" in t or "storage" in t:
        status_msg = "Checking your storage space..."
    else:
        status_msg = f"Working on: {task}"

    await emit_event(
        config, {"type": "classification", "category": "os", "description": status_msg}
    )

    await emit_event(config, {"type": "step_start", "description": status_msg})

    try:
        # Get existing context
        ctx = state.get("context", {})
        # Run directly since it's already async and fast
        result, new_ctx = await parse_and_execute_os_task(task, ctx)
    except Exception as e:
        result = f"Something went wrong: {str(e)}"
        new_ctx: dict[str, str] = {}

    await emit_event(config, {"type": "step_done", "description": f"Done! {result}"})
    await emit_event(config, {"type": "complete", "summary": result})

    return {
        "result": result,
        "messages": [{"role": "assistant", "content": result}],
        "context": new_ctx,  # Update context for the next turn
    }


def kill_process(target: str) -> str:
    import psutil

    target_lower = target.lower()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if target_lower in proc.info["name"].lower():
                proc.kill()
                return f"Successfully killed process {proc.info['name']} (PID: {proc.info['pid']})"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return f"Failed: No active process matching '{target}' was found."
