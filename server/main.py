import os
import uuid
import logging
import asyncio
from typing import Dict
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from agent.graph import app_graph
from agent.bus import manager, emit_event
from routers.face_auth import router as face_auth_router
from routers.voice import router as voice_router
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AutoOS")

load_dotenv(Path(__file__).with_name(".env"), override=True)
load_dotenv(override=True)

app = FastAPI(title="AutoOS Gateway API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(face_auth_router)
app.include_router(voice_router)

# ── Static Files ─────────────────────────────────────────────────────────────
os.makedirs(os.path.join(os.path.dirname(__file__), "screenshots"), exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "screenshots")), name="screenshots")

# ── Running task registry ─────────────────────────────────────────────────────
# Maps execution_id → asyncio.Task so we can cancel it on demand.
_running_tasks: Dict[str, asyncio.Task] = {}


class TaskRequest(BaseModel):
    task: str
    headless: bool | None = None
    input_values: dict[str, str] | None = None
    max_steps: int | None = None


class TaskResponse(BaseModel):
    status: str
    classification: str
    result: str


@app.post("/executions")
async def create_execution(request: TaskRequest):
    execution_id = str(uuid.uuid4())
    return {"id": execution_id}


@app.post("/executions/{execution_id}/stop")
async def stop_execution(execution_id: str):
    """Cancel a running execution by its ID."""
    task = _running_tasks.pop(execution_id, None)
    if task and not task.done():
        task.cancel()
        logger.info("Cancelled execution %s via REST", execution_id)
        return {"status": "stopped"}
    return {"status": "not_found"}


@app.websocket("/ws/execution/{execution_id}")
async def websocket_endpoint(websocket: WebSocket, execution_id: str):
    await manager.connect(execution_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "start":
                task_text = data.get("task")
                # Run as a proper background task so the WS loop stays alive
                # and can receive a "stop" message while the agent is running.
                agent_task = asyncio.create_task(
                    _run_agent_task(execution_id, task_text, data)
                )
                _running_tasks[execution_id] = agent_task

                # When the task finishes (normally or cancelled) clean up registry
                def _cleanup(fut: asyncio.Task):
                    _running_tasks.pop(execution_id, None)

                agent_task.add_done_callback(_cleanup)

            elif data.get("type") == "stop":
                task = _running_tasks.pop(execution_id, None)
                if task and not task.done():
                    task.cancel()
                    logger.info("Cancelled execution %s via WebSocket stop message", execution_id)
                # Let _run_agent_task's CancelledError handler notify the frontend
    except WebSocketDisconnect:
        # If the user closes the window, cancel any running task automatically
        task = _running_tasks.pop(execution_id, None)
        if task and not task.done():
            task.cancel()
        manager.disconnect(execution_id)


async def _run_agent_task(execution_id: str, task_text: str, params: dict | None = None):
    """Run the LangGraph agent as a cancellable asyncio task."""
    try:
        from agent.fast_track_rules import get_fast_track_category
        fast_cat = get_fast_track_category(task_text)

        initial_state = {
            "task": task_text,
            "messages": [],
            "next_action": fast_cat if fast_cat else "",
            "sub_category": "fast_tracked" if fast_cat else "",
            "entities": [],
            "action_params": {},
            "plain_english_plan": "",
            "confidence": 1.0,
            "needs_hitl": False,
            "plan": [],
            "result": "",
            "context": {},
            "headless": params.get("headless") if params else None,
            "max_steps": params.get("max_steps") if params else None,
            "input_values": params.get("input_values") if params else None,
        }

        await app_graph.ainvoke(
            initial_state,
            config={"configurable": {"execution_id": execution_id}},
        )

    except asyncio.CancelledError:
        # Task was cancelled via the stop button — notify frontend
        logger.info("Agent task %s was cancelled", execution_id)
        try:
            await manager.send_message(execution_id, {
                "type": "stopped",
                "message": "Task stopped by user.",
            })
        except Exception:
            # WebSocket may already be closed
            pass
    except Exception as e:
        logger.error("Agent task error: %s", e, exc_info=True)
        await manager.send_message(execution_id, {"type": "step_error", "error": str(e)})


@app.post("/api/automate/task", response_model=TaskResponse)
async def automate_browser_task(request: TaskRequest):
    """Extension-friendly direct browser automation endpoint."""
    from agent.tools.browser_tool import BrowserAutomationRunner

    try:
        logger.info("Received browser automation task: %s", request.task)
        result = await BrowserAutomationRunner(headless=request.headless).run_task(
            request.task,
            sensitive_data=request.input_values,
            max_steps=request.max_steps,
        )
        return TaskResponse(
            status="success" if result.success else "failed",
            classification="browser",
            result=result.as_text(),
        )
    except Exception as e:
        logger.error("Error during browser automation: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system/health")
async def get_system_health():
    import psutil
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()

    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            if info['cpu_percent'] is not None:
                processes.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "cpu_percent": round(info['cpu_percent'], 1),
                    "memory_percent": round(info['memory_percent'] or 0.0, 1),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    processes = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:15]

    return {
        "cpu": cpu,
        "ram": ram,
        "battery": {
            "percent": battery.percent if battery else 100,
            "power_plugged": battery.power_plugged if battery else True
        } if battery else None,
        "disk": psutil.disk_usage('/').percent,
        "processes": processes,
    }

async def background_heartbeat():
    """
    Proactive Guardian Mode: Checks system status every 60 seconds 
    and broadcasts alerts to the UI.
    """
    import psutil
    while True:
        try:
            # Check CPU
            cpu = psutil.cpu_percent(interval=1)
            if cpu > 90:
                await manager.broadcast({
                    "type": "guardian_alert", 
                    "message": f"High CPU Load detected ({cpu}%). Suggest closing background apps."
                })
            
            # Check Battery
            battery = psutil.sensors_battery()
            if battery and battery.percent < 20 and not battery.power_plugged:
                await manager.broadcast({
                    "type": "guardian_alert",
                    "message": f"Low Battery ({battery.percent}%). Please connect a charger."
                })
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    # Start the proactive guardian heartbeat
    asyncio.create_task(background_heartbeat())

@app.post("/system/processes/kill")
async def kill_process_api(data: dict):
    from agent.nodes.executor import kill_process
    target = data.get("target")
    if not target:
        raise HTTPException(status_code=400, detail="Missing target process name or PID")
    
    result = kill_process(str(target))
    if "Failed" in result or "No active" in result:
        raise HTTPException(status_code=400, detail=result)
    return {"message": result}

from pathlib import Path
from datetime import datetime
import json

def _sanitize_messages(messages: list) -> list:
    """
    Normalize a mixed list of messages to plain {id, role, content, ...} dicts.
    LangGraph's add_messages may store LangChain AIMessage / HumanMessage objects
    whose 'content' field is a list of {type, text, extras} blocks instead of a str.
    This ensures React always receives a plain string in the content field.
    """
    clean = []
    for m in messages:
        # Handle both dict and LangChain BaseMessage objects
        if hasattr(m, "content"):
            role = getattr(m, "type", "agent")          # AIMessage -> "ai"
            role = "agent" if role in ("ai", "assistant") else role
            raw_content = m.content
        elif isinstance(m, dict):
            role = m.get("role", m.get("type", "system"))
            raw_content = m.get("content", "")
        else:
            continue

        # content can be a list of content blocks from multi-modal responses
        if isinstance(raw_content, list):
            parts = []
            for block in raw_content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    parts.append(block.get("text", str(block)))
                else:
                    parts.append(str(block))
            content_str = " ".join(parts)
        elif isinstance(raw_content, str):
            content_str = raw_content
        else:
            content_str = str(raw_content)

        entry = {
            "id": m.get("id", "") if isinstance(m, dict) else getattr(m, "id", ""),
            "role": role,
            "content": content_str,
        }
        # Preserve optional display fields if present
        for field in ("type", "subCategory"):
            val = m.get(field) if isinstance(m, dict) else getattr(m, field, None)
            if val:
                entry[field] = val
        clean.append(entry)
    return clean


@app.post("/system/threads/save")
async def save_thread(data: dict):
    thread_id = data.get("id", "default")
    messages = _sanitize_messages(data.get("messages", []))

    thread_path = Path("server/knowledge/threads")
    thread_path.mkdir(parents=True, exist_ok=True)

    with open(thread_path / f"{thread_id}.json", "w") as f:
        json.dump({
            "id": thread_id,
            "last_updated": datetime.now().isoformat(),
            "messages": messages
        }, f, indent=2)

    return {"status": "saved"}

@app.get("/system/threads/latest")
async def get_latest_thread():
    thread_path = Path("server/knowledge/threads")
    if not thread_path.exists():
        return {"messages": [], "id": "new-" + datetime.now().strftime("%Y%m%d%H%M%S")}
    
    files = list(thread_path.glob("*.json"))
    if not files:
        return {"messages": [], "id": "new-" + datetime.now().strftime("%Y%m%d%H%M%S")}
    
    # Sort by modification time
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    with open(latest_file, "r") as f:
        return json.load(f)

@app.get("/system/threads")
async def list_threads():
    thread_path = Path("server/knowledge/threads")
    if not thread_path.exists(): return []
    
    threads = []
    for f in thread_path.glob("*.json"):
        with open(f, "r") as tf:
            data = json.load(tf)
            threads.append({
                "id": data["id"],
                "last_updated": data["last_updated"],
                "preview": data["messages"][0]["content"] if data["messages"] else "Empty Chat"
            })
    return sorted(threads, key=lambda x: x["last_updated"], reverse=True)

@app.get("/system/workflows")
async def list_workflows():
    wf_path = Path("server/knowledge/workflows")
    if not wf_path.exists(): return []
    
    workflows = []
    for f in wf_path.glob("*.json"):
        with open(f, "r") as wf:
            workflows.append(json.load(wf))
    return workflows

@app.post("/system/workflows/save")
async def save_workflow(data: dict):
    wf_path = Path("server/knowledge/workflows")
    wf_path.mkdir(parents=True, exist_ok=True)
    
    wf_id = data.get("id", "wf_" + datetime.now().strftime("%H%M%S"))
    with open(wf_path / f"{wf_id}.json", "w") as f:
        json.dump(data, f, indent=2)
    return {"status": "saved"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("AUTOFLOW_PORT", 8765))
    uvicorn.run(app, host="0.0.0.0", port=port)
