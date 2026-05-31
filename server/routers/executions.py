from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from sqlmodel import Session, select
from typing import Dict, List, Optional
import asyncio
import uuid
from datetime import datetime

from db import get_session
from models.execution import Execution, ExecutionCreate, ExecutionRead
from agent.graph import app_graph
from agent.bus import manager
from pydantic import BaseModel
from utils.logger import api_logger as logger

router = APIRouter(tags=["Executions"])

# Maps execution_id -> asyncio.Task
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

@router.post("/executions", response_model=ExecutionRead)
async def create_execution(request: TaskRequest, session: Session = Depends(get_session)):
    execution_id = str(uuid.uuid4())
    execution = Execution(id=execution_id, status="pending")
    try:
        session.add(execution)
        session.commit()
        session.refresh(execution)
        return execution
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create execution record: {e}")
        raise HTTPException(status_code=500, detail="Failed to create execution")

@router.get("/executions", response_model=List[ExecutionRead])
async def list_executions(session: Session = Depends(get_session)):
    try:
        executions = session.exec(select(Execution)).all()
        return executions
    except Exception as e:
        logger.error(f"Failed to list executions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch executions")

@router.post("/executions/{execution_id}/stop")
async def stop_execution(execution_id: str):
    """Cancel a running execution by its ID."""
    task = _running_tasks.pop(execution_id, None)
    if task and not task.done():
        task.cancel()
        logger.info("Cancelled execution %s via REST", execution_id)
        return {"status": "stopped"}
    return {"status": "not_found"}

async def _run_agent_task(execution_id: str, task_text: str, params: dict | None = None):
    """Run the LangGraph agent as a cancellable asyncio task."""
    try:
        initial_state = {
            "task": task_text,
            "messages": [],
            "next_action": "",
            "sub_category": "",
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
        logger.info("Agent task %s was cancelled", execution_id)
        try:
            await manager.send_message(execution_id, {
                "type": "stopped",
                "message": "Task stopped by user.",
            })
        except Exception:
            pass
    except Exception as e:
        logger.error("Agent task error: %s", e, exc_info=True)
        await manager.send_message(execution_id, {"type": "step_error", "error": str(e)})
    finally:
        # Step 4: Fix WebSocket Memory Leaks
        # Ensure we always remove from _running_tasks to prevent memory leaks
        _running_tasks.pop(execution_id, None)


@router.websocket("/ws/execution/{execution_id}")
async def websocket_endpoint(websocket: WebSocket, execution_id: str):
    await manager.connect(execution_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "start":
                task_text = data.get("task")
                agent_task = asyncio.create_task(
                    _run_agent_task(execution_id, task_text, data)
                )
                _running_tasks[execution_id] = agent_task

                def _cleanup(fut: asyncio.Task):
                    _running_tasks.pop(execution_id, None)

                agent_task.add_done_callback(_cleanup)

            elif data.get("type") == "stop":
                task = _running_tasks.pop(execution_id, None)
                if task and not task.done():
                    task.cancel()
                    logger.info("Cancelled execution %s via WebSocket stop message", execution_id)

    except WebSocketDisconnect:
        task = _running_tasks.pop(execution_id, None)
        if task and not task.done():
            task.cancel()
    finally:
        manager.disconnect(execution_id)

@router.post("/api/automate/task", response_model=TaskResponse)
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
