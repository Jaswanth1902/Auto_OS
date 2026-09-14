"""
logger.py — Structured Telemetry, Audit Trail & Rich Logging for AutoOS.
Maintains persistent JSON-L audit logs for replay and anti-hallucination analysis,
while emitting clean, high-craft terminal outputs using textualize/rich.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict
from langchain_core.runnables import RunnableConfig

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    rich_available = True
    console = Console()
except ImportError:
    rich_available = False
    console = None

from agent.state import AgentState
from utils.logger import agent_logger as base_logger

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
AUDIT_LOG_FILE = LOG_DIR / "audit_trail.jsonl"

def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def append_audit_entry(entry: Dict[str, Any]) -> None:
    """Appends an event entry to the JSON-L audit trail file."""
    try:
        _ensure_log_dir()
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        base_logger.error(f"Failed to write audit entry: {e}")

def render_rich_summary(step_name: str, status: str, duration_ms: float, details: str) -> None:
    """Renders a tactile, high-craft panel in the terminal using Rich."""
    if not rich_available or not console:
        base_logger.info(f"[{step_name.upper()}] Status: {status} | Latency: {duration_ms:.1f}ms | {details}")
        return

    color = "green" if status in ("done", "success", "completed", "proceed") else "yellow" if status == "awaiting_approval" else "red"
    
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold cyan]Step:[/bold cyan]", step_name)
    table.add_row("[bold cyan]Status:[/bold cyan]", f"[{color}]{status.upper()}[/{color}]")
    table.add_row("[bold cyan]Latency:[/bold cyan]", f"{duration_ms:.1f} ms")
    table.add_row("[bold cyan]Summary:[/bold cyan]", details[:140] + ("..." if len(details) > 140 else ""))

    panel = Panel(
        table,
        title=f"[bold white]AutoOS Trace — {step_name}[/bold white]",
        border_style=color,
        expand=False
    )
    console.print(panel)

async def logger_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    LangGraph Telemetry Node: Records execution metrics and persists session audit trails.
    """
    task = state.get("task", "")
    result = state.get("result", "")
    status = state.get("status", "completed")
    start_time = state.get("start_time", time.time())
    duration_ms = (time.time() - start_time) * 1000.0
    category = state.get("category", "os")

    audit_entry = {
        "timestamp": time.time(),
        "task": task,
        "category": category,
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "result_preview": str(result)[:300],
        "context_keys": list(state.get("context", {}).keys())
    }

    append_audit_entry(audit_entry)
    render_rich_summary(
        step_name=f"{category.upper()} Executor",
        status=status,
        duration_ms=duration_ms,
        details=str(result)
    )

    return {"logged": True, "audit_timestamp": audit_entry["timestamp"]}
