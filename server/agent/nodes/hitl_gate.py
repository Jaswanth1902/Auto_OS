"""
hitl_gate.py — Human-In-The-Loop (HITL) Gate Node for AutoOS.
Provides deterministic risk classification, cryptographic approval tokens,
and pauses execution when destructive actions are requested.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any, Dict, Optional
from langchain_core.runnables import RunnableConfig

from agent.state import AgentState
from agent.bus import emit_event
from utils.logger import agent_logger as logger

# Ephemeral secret generated per server lifecycle for token integrity
_GATE_SECRET = os.getenv("AUTOOS_GATE_SECRET", os.urandom(32).hex()).encode("utf-8")

# Risk classification definitions
DANGEROUS_ACTIONS = {
    "delete_file", "remove_directory", "kill_process", "format_disk",
    "modify_registry", "shutdown", "reboot", "factory_reset",
    "install_package", "execute_binary", "purchase", "send_email",
    "send_payment"
}

DANGEROUS_KEYWORDS = [
    "delete", "remove", "wipe", "format", "nuke", "kill", "terminate",
    "drop table", "shutdown", "reboot", "rm -rf", "del /f", "del /s"
]

def classify_risk(task: str, action: str = "", plan: Optional[list] = None) -> tuple[str, str]:
    """
    Classifies risk into SAFE, CAUTION, DANGEROUS, or BLOCKED.
    Returns (risk_level, reason).
    """
    text = f"{task} {action}".lower()
    
    # Check for hard blocked attacks
    if any(b in text for b in ["rmdir /s /q c:", "format c:", "drop database", ":(){ :|:& };:"]):
        return "BLOCKED", "Critical destructive payload detected."
        
    # Check for explicit dangerous actions
    if action.lower() in DANGEROUS_ACTIONS or any(kw in text for kw in DANGEROUS_KEYWORDS):
        return "DANGEROUS", f"Action involves potentially destructive operations ({action or 'system modification'})."
        
    # Check for sensitive communications or external sends
    if any(w in text for w in ["send message", "post on", "submit form", "transfer"]):
        return "CAUTION", "Action initiates external communication or state alteration."
        
    return "SAFE", "Read-only or benign OS interaction."

def generate_approval_token(task: str, action: str, request_id: str) -> str:
    """Generates an HMAC-SHA256 signature for approval verification."""
    payload = f"{request_id}:{action}:{task}".encode("utf-8")
    return hmac.new(_GATE_SECRET, payload, hashlib.sha256).hexdigest()

def verify_approval_token(token: str, task: str, action: str, request_id: str) -> bool:
    """Verifies the cryptographically signed user approval."""
    expected = generate_approval_token(task, action, request_id)
    return hmac.compare_digest(token, expected)

async def hitl_gate(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    LangGraph Node: Intercepts dangerous operations before dispatch.
    If the operation is DANGEROUS or BLOCKED and not pre-approved, halts execution
    and issues an approval request payload.
    """
    task = state.get("task", "")
    action = state.get("action", "")
    approved = state.get("approved", False)
    approval_token = state.get("approval_token", "")
    request_id = state.get("request_id", f"req_{int(time.time() * 1000)}")
    
    risk_level, reason = classify_risk(task, action)
    
    if risk_level == "BLOCKED":
        logger.error(f"[HITL GATE] Blocked prohibited command: {task} ({reason})")
        await emit_event(config, {
            "type": "security_violation",
            "risk_level": "BLOCKED",
            "reason": reason
        })
        return {
            "status": "blocked",
            "result": f"Execution halted by AutoOS Security Policy: {reason}",
            "messages": [{"role": "assistant", "content": f"🛡️ Execution Blocked: {reason}"}],
            "requires_hitl": False
        }
        
    if risk_level == "DANGEROUS":
        # Check cryptographic approval token if user sent approval flag
        if approved:
            if approval_token and verify_approval_token(approval_token, task, action, request_id):
                logger.info(f"[HITL GATE] Verified cryptographic approval for {request_id}")
                await emit_event(config, {
                    "type": "hitl_approved",
                    "request_id": request_id,
                    "action": action
                })
                return {"status": "approved", "requires_hitl": False}
            else:
                logger.warning(f"[HITL GATE] Invalid or missing approval token for {request_id}")
                
        # Not approved yet: Generate challenge and request confirmation from frontend
        token = generate_approval_token(task, action, request_id)
        payload = {
            "type": "hitl_request",
            "request_id": request_id,
            "risk_level": "DANGEROUS",
            "reason": reason,
            "action": action,
            "task": task,
            "token": token,
            "timestamp": time.time()
        }
        
        await emit_event(config, payload)
        logger.info(f"[HITL GATE] Emitted approval request {request_id} for task: '{task}'")
        
        return {
            "status": "awaiting_approval",
            "requires_hitl": True,
            "request_id": request_id,
            "approval_token": token,
            "result": f"Action requires explicit user confirmation: {reason}",
            "messages": [{
                "role": "assistant",
                "content": f"⚠️ **Confirmation Required**: The requested task entails system changes ({reason}). Please confirm in the AutoOS HUD to proceed."
            }]
        }

    # SAFE / CAUTION proceed directly
    return {"status": "proceed", "requires_hitl": False}
