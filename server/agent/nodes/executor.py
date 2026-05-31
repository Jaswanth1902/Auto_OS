from typing import Any
import asyncio
import subprocess
import time
import os
import re
import logging
import pyautogui
import psutil
try:
    import pygetwindow as gw
except:
    gw = None
from langchain_core.runnables import RunnableConfig
from agent.state import AgentState
from agent.tools.browser_tool import run_browser_task
from agent.bus import emit_event
from agent.modules import app_module

from utils.logger import agent_logger as logger

# ─────────────────────────────────────────
# DIRECT OS EXECUTOR — No LLM, No Hanging
# ─────────────────────────────────────────

async def launch_app(app_name: str) -> str:
    try:
        # Smart Focus: Check if already running to avoid "duplicate instances"
        try:
            import pygetwindow as gw
            import psutil
            
            # 1. Check for window by name
            windows = [w for w in gw.getAllWindows() if app_name.lower() in w.title.lower() and w.visible]
            if windows:
                windows[0].activate()
                return f"Focused existing {app_name} window."
                
            # 2. Check process list for common app names
            for proc in psutil.process_iter(['name']):
                if app_name.lower() in proc.info['name'].lower():
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

async def create_file_or_folder(name: str, folder_name: str = "desktop", content: str = "", is_folder: bool = False) -> str:
    # Resolve the true Windows path (handling OneDrive)
    user_path = os.path.expanduser("~")
    
    # Priority: 1. OneDrive 2. Local
    candidates = [
        os.path.join(user_path, "OneDrive", folder_name.capitalize()),
        os.path.join(user_path, folder_name.capitalize()),
        os.path.join(user_path, "Desktop") # Fallback
    ]
    
    base_path = next((c for c in candidates if os.path.exists(c)), os.path.expanduser("~/Desktop"))
    
    # Sanitize the name: Windows doesn't allow these: < > : " / \ | ? *
    clean_name = re.sub(r'[<>:"/\\|?*]', '', name).strip()
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
                    import pygetwindow as gw
                    import pyautogui
                    # Try to find the explorer window
                    title = os.path.basename(base_path)
                    wa_windows = [w for w in gw.getWindowsWithTitle(title) if w.visible]
                    if wa_windows:
                        wa_windows[0].activate()
                        pyautogui.press('f5') # Refresh the view
                except:
                    pass
                    
                return f"Successfully created folder at: {full_path}", {"last_folder": full_path, "last_path": full_path}
            return f"Failed to verify folder creation at {full_path}", {}
        else:
            with open(full_path, "w") as f:
                f.write(content)
            # Open explorer and highlight the new file
            subprocess.Popen(f'explorer /select,"{full_path}"', shell=True)
            return f"Successfully created file at: {full_path}", {"last_file": full_path, "last_path": full_path}
    except Exception as e:
        return f"File creation failed: {e}", {}

def compute_in_calculator(expression: str) -> str:
    try:
        import pyautogui
        subprocess.Popen("calc.exe", shell=True)
        time.sleep(2.5)
        # Clean expression - only allow valid calculator chars
        clean = re.sub(r'[^0-9+\-*/().]', '', expression)
        pyautogui.write(clean, interval=0.1)
        time.sleep(0.5)
        pyautogui.press('enter')
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
        cmd = 'Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status | ConvertTo-Json'
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True, text=True, timeout=10
        )
        if not result.stdout.strip():
            return "No Bluetooth devices detected."
        import json
        devices = json.loads(result.stdout)
        if isinstance(devices, dict): devices = [devices]
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
                wa_windows = [w for w in gw.getWindowsWithTitle('WhatsApp') if w.visible]
                if wa_windows:
                    wa_windows[0].activate()
                    await asyncio.sleep(1)
            except: pass
        
        # 3. Search for the contact (Ctrl+F)
        # We try twice to be sure
        for _ in range(2):
            pyautogui.hotkey('ctrl', 'f')
            await asyncio.sleep(0.5)
        
        pyautogui.write(contact_name, interval=0.1)
        await asyncio.sleep(2) # Wait for search results
        
        # 4. Open the chat
        pyautogui.press('enter')
        await asyncio.sleep(1)
        return f"Opened WhatsApp and focused on '{contact_name}'.", {"last_contact": contact_name, "last_app": "whatsapp"}
    except Exception as e:
        return f"Could not open specific chat: {e}", {}

async def quick_send_whatsapp(message: str) -> str:
    try:
        # 1. Bring WhatsApp to front
        await launch_app("whatsapp")
        await asyncio.sleep(1)
        
        # 2. Directly type and send
        pyautogui.write(message, interval=0.05)
        pyautogui.press('enter')
        return f"Sent to active chat: \"{message}\".", {"last_app": "whatsapp"}
    except Exception as e:
        return f"Failed to send quick message: {e}", {}

async def send_whatsapp_message(contact_name: str, message: str, context: dict = None) -> str:
    try:
        # Optimization: If we are already in this chat, skip navigation!
        ctx = context or {}
        last_c = ctx.get("last_contact", "").lower()
        if contact_name.lower() == last_c and last_c != "":
            return await quick_send_whatsapp(message)

        # 1. Open the chat first
        res, ctx_nav = await open_whatsapp_chat(contact_name)
        if "Could not" in res: return res, {}
        await asyncio.sleep(1.5)
        # 2. Type and send
        pyautogui.write(message, interval=0.05)
        pyautogui.press('enter')
        return f"Sent message to '{contact_name}': \"{message}\".", {"last_contact": contact_name, "last_app": "whatsapp"}
    except Exception as e:
        return f"Failed to send message: {e}", {}

# ─────────────────────────────────────────
# SMART TASK PARSER — No LLM needed
# ─────────────────────────────────────────

async def parse_and_execute_os_task(task: str, context: dict = None) -> tuple[str, dict]:
    t = task.lower().strip()
    ctx = context or {}
    new_ctx = {}

    # 1. CONTEXT RESOLUTION (Pronouns)
    # Be aggressive about replacing pronouns if we have context
    last_c = ctx.get("last_contact", "").lower()
    for word in ["him", "her", "them", "that chat", "the chat"]:
        pattern = rf"\b{word}\b"
        if re.search(pattern, t) and last_c:
            t = re.sub(pattern, last_c, t)
    
    if " it " in f" {t} " or t.endswith(" it"):
        last_f = ctx.get("last_folder", "").lower() or ctx.get("last_file", "").lower()
        if last_f:
            t = t.replace(" it", f" {last_f}").replace(" it ", f" {last_f} ")
    
    # 2. EXECUTION LOGIC
    # Calculator
    calc_match = re.search(r'(\d+[\s]*[+\-*/][\s]*\d+[\s]*[+\-*/\d\s]*)', task)
    if any(w in t for w in ["calculator", "calculate", "compute", "math"]) or calc_match:
        if calc_match: return compute_in_calculator(calc_match.group(1).replace(" ", "")), {"last_app": "calculator"}
        else: return await launch_app("calculator"), {"last_app": "calculator"}
    
    # Folder opening - refined to avoid swallowing file requests
    for folder in ["downloads", "desktop", "documents", "pictures", "music", "videos"]:
        # Only match if the task doesn't look like a specific file request (no extensions)
        if folder in t and any(w in t for w in ["open", "show", "go to", "navigate"]):
            if not re.search(r'\.[a-z0-9]{2,4}', t):
                res = open_folder(folder)
                return res, {"last_folder": folder}
    
    # Specific File Opening
    file_open_match = re.search(r'open\s+(.*?)\s+(?:in|on|at|inside)\s+(?:my\s+)?(downloads|desktop|documents|pictures|music|videos)', t)
    if file_open_match:
        filename = file_open_match.group(1).strip()
        folder_name = file_open_match.group(2).strip()
        
        # Resolve path
        user_path = os.path.expanduser("~")
        candidates = [
            os.path.join(user_path, "OneDrive", folder_name.capitalize()),
            os.path.join(user_path, folder_name.capitalize())
        ]
        base_path = next((c for c in candidates if os.path.exists(c)), os.path.expanduser(f"~/{folder_name.capitalize()}"))
        full_path = os.path.join(base_path, filename)
        
        return run_file(full_path), {"last_file": full_path, "last_folder": folder_name}
    
    # File/Folder Creation
    # Catch "create [file/folder] [name] in/on [folder]"
    # Added [^a-zA-Z0-9]* at end to ignore trailing quotes/garbage
    create_match = re.search(r'create\s+(?:a\s+)?(file|folder)\s+(?:named\s+)?(.*?)(?:\s+(?:in|on|at)\s+(?:my\s+)?([a-zA-Z0-9\s._-]+))?[^a-zA-Z0-9]*$', t)
    if create_match:
        item_type = create_match.group(1).strip()
        item_name = create_match.group(2).strip()
        # Clean up "my " if it leaked into the name
        if item_name.endswith(" on my"): item_name = item_name[:-6].strip()
        if item_name.endswith(" in my"): item_name = item_name[:-6].strip()
        
        folder = create_match.group(3).strip() if create_match.group(3) else "desktop"
        content_match = re.search(r'with\s+(?:the\s+)?(?:text|content)\s+[\'"](.+)[\'"]', task, re.IGNORECASE)
        content = content_match.group(1) if content_match else ""
        return await create_file_or_folder(item_name, folder, content, is_folder=(item_type == "folder"))

    # App launching & Messaging
    # 0. Catch "open [site] on [browser]" (Cross-platform)
    browser_launch_match = re.search(r'(?:open|launch|start|run|play)\s+(.*?)\s+(?:on|in|using)\s+(brave|chrome|edge|firefox|opera)', t)
    if browser_launch_match:
        target = browser_launch_match.group(1).strip()
        browser = browser_launch_match.group(2).strip()
        
        # Resolve common services to URLs
        url_map = {
            "spotify": "https://open.spotify.com",
            "youtube": "https://www.youtube.com",
            "netflix": "https://www.netflix.com",
            "whatsapp": "https://web.whatsapp.com",
            "gmail": "https://mail.google.com",
            "chatgpt": "https://chat.openai.com",
            "github": "https://github.com",
        }
        url = url_map.get(target.lower(), target if "." in target else f"https://www.google.com/search?q={target}")
        
        # Launch browser with URL
        try:
            if browser == "brave":
                # Try standard 'start brave', then try explicit paths
                brave_paths = [
                    "brave", # If in PATH
                    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                    os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe")
                ]
                launched = False
                for b_path in brave_paths:
                    try:
                        subprocess.Popen(f'"{b_path}" "{url}"', shell=True)
                        launched = True
                        break
                    except: continue
                if not launched: os.startfile(url)
            elif browser == "chrome":
                subprocess.Popen(f'start chrome "{url}"', shell=True)
            elif browser == "edge":
                subprocess.Popen(f'start msedge "{url}"', shell=True)
            else:
                os.startfile(url) # Fallback to default
            return f"Opening {target} in {browser.capitalize()}...", {"last_app": browser, "last_url": url}
        except:
            return f"Found the request but failed to launch {browser}. Opening in default browser instead.", {}

    # 1. Catch "send [message] to [name] on whatsapp" (with target)
    # Using .*? (non-greedy) for the message part
    wa_send_to_match = re.search(r'(?:send|text|message|ping|tell)\s+(.*?)\s+to\s+([a-zA-Z0-9\s._-]+)(?:\s+(?:on|in)\s+whatsapp)?', t)
    if wa_send_to_match:
        msg = wa_send_to_match.group(1).strip()
        contact = wa_send_to_match.group(2).strip()
        # Safety: If we still have a pronoun here, it means resolution failed
        if contact in ["him", "her", "them", "it"] and "last_contact" in ctx:
            contact = ctx["last_contact"]
        return await send_whatsapp_message(contact, msg, ctx)

    # 2. Catch "send [message]" or "text [message]" (implicit target)
    wa_quick_send_match = re.search(r'^(?:send|text|message|say|tell|ping)\s+(.+)$', t)
    if wa_quick_send_match and (ctx.get("last_app") == "whatsapp" or "last_contact" in ctx):
        msg = wa_quick_send_match.group(1).strip()
        # If it contains "to ", it's not a quick send
        if " to " not in msg:
            return await quick_send_whatsapp(msg)

    # 3. Catch "open [name]'s chat in whatsapp" or "open whatsapp and navigate to [name] chat"
    wa_chat_match = re.search(r'(?:open|navigate|go to|search)\s+(?:whatsapp\s+and\s+)?(?:navigate\s+to\s+|find\s+)?([a-zA-Z0-9\s._-]+)\s+chat(?:\s+in\s+whatsapp)?', t)
    if wa_chat_match:
        return await open_whatsapp_chat(wa_chat_match.group(1).strip())

    # Catch "open [app]", "launch [app]", "start [app]"
    launch_match = re.search(r'(?:open|launch|start|run|play)\s+([a-zA-Z0-9\s._-]+)', t)
    if launch_match:
        target_app = launch_match.group(1).strip()
        # Exclude folders and settings from app launch catch-all
        if not any(f in target_app for f in ["downloads", "desktop", "documents", "pictures", "music", "videos", "settings"]):
            return await launch_app(target_app)

    # Fallback keyword match for specific common apps
    for app in ["notepad", "paint", "word", "excel", "cmd", "powershell", "taskmgr", "taskmanager", "explorer", "vlc", "spotify", "whatsapp", "chrome", "edge"]:
        if app in t:
            return await launch_app(app)
    
    # System checks
    if any(w in t for w in ["disk", "storage", "space", "memory"]):
        return check_disk_space()
    
    if any(w in t for w in ["battery", "charging", "power"]):
        return get_battery_status()
    
def kill_process(name_or_pid: str) -> str:
    """
    Safely terminates a process using psutil (No taskkill needed).
    """
    import psutil
    count = 0
    try:
        # Check if PID
        if name_or_pid.isdigit():
            p = psutil.Process(int(name_or_pid))
            p.terminate()
            return f"Terminated process with PID {name_or_pid}."
            
        # Check by name
        for proc in psutil.process_iter(['name']):
            if name_or_pid.lower() in proc.info['name'].lower():
                proc.terminate()
                count += 1
        
        if count > 0:
            return f"Successfully closed {count} instances of '{name_or_pid}'."
        return f"No active process found named '{name_or_pid}'."
    except Exception as e:
        return f"Failed to kill process: {e}"

async def parse_and_execute_os_task(task: str, context: dict = None) -> tuple[str, dict]:
    t = task.lower().strip()
    ctx = context or {}
    new_ctx = {}

    # 1. CONTEXT RESOLUTION (Pronouns)
    # ... (rest of logic) ...
    
    # 2. EXECUTION LOGIC
    # Process Management
    if any(w in t for w in ["kill", "terminate", "close process", "force close"]):
        # Extract app name after the verb
        match = re.search(r'(?:kill|terminate|close|stop)\s+([a-zA-Z0-9.]+)', t)
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
    for section in ["display", "sound", "bluetooth", "wifi", "update", "privacy", "storage"]:
        if section in t and any(w in t for w in ["settings", "setting", "open", "go to", "turn", "on", "off"]):
            return open_settings(section)
    if "settings" in t:
        return open_settings(), {}

    return f"I understood this is an OS task but I'm not sure how to handle: '{task}'. Please be more specific.", {}

# ─────────────────────────────────────────
# BROWSER EXECUTOR
# ─────────────────────────────────────────

async def browser_executor(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    task = state.get("task", "")
    
    await emit_event(config, {
        "type": "step_start",
        "description": f"Starting browser task: {task}"
    })

    try:
        result = await asyncio.wait_for(
            run_browser_task(
                task,
                headless=state.get("headless"),
                input_values=state.get("input_values"),
                max_steps=state.get("max_steps"),
            ),
            timeout=120.0
        )
    except asyncio.TimeoutError:
        result = "Browser task timed out after 2 minutes. Please try again."
    except Exception as e:
        result = f"Browser task failed: {str(e)}"

    await emit_event(config, {"type": "step_done", "description": "Completed browser task"})
    await emit_event(config, {"type": "complete", "summary": result})

    # Detect current platform for context persistence
    new_ctx = {}
    if "spotify.com" in str(result).lower() or "spotify" in task.lower():
        new_ctx["last_url"] = "https://open.spotify.com"
        new_ctx["last_app"] = "spotify"
    elif "youtube.com" in str(result).lower() or "youtube" in task.lower():
        new_ctx["last_url"] = "https://www.youtube.com"
        new_ctx["last_app"] = "youtube"

    return {
        "result": result,
        "messages": [{"role": "assistant", "content": f"Browser Task Result: {result}"}],
        "context": new_ctx
    }

# ─────────────────────────────────────────
# OS EXECUTOR — Direct execution, no LLM
# ─────────────────────────────────────────

# ─────────────────────────────────────────
# REASONING EXECUTOR
# ─────────────────────────────────────────

async def reasoning_executor(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    task = state.get("task", "")
    
    await emit_event(config, {
        "type": "step_start",
        "description": f"Thinking about: {task}"
    })

    try:
        from agent.llm_factory import get_llm
        llm = get_llm(temperature=0.7) # Slightly higher temperature for "creative" reasoning
        
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

    return {
        "result": result,
        "messages": [{"role": "assistant", "content": result}]
    }

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

    await emit_event(config, {
        "type": "classification",
        "category": "os",
        "description": status_msg
    })

    await emit_event(config, {
        "type": "step_start",
        "description": status_msg
    })

    try:
        # Get existing context
        ctx = state.get("context", {})
        # Run directly since it's already async and fast
        result, new_ctx = await parse_and_execute_os_task(task, ctx)
    except Exception as e:
        result = f"Something went wrong: {str(e)}"
        new_ctx = {}

    await emit_event(config, {
        "type": "step_done",
        "description": f"Done! {result}"
    })
    await emit_event(config, {"type": "complete", "summary": result})

    return {
        "result": result,
        "messages": [{"role": "assistant", "content": result}],
        "context": new_ctx # Update context for the next turn
    }
