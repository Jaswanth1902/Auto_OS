"""
router.py — Intelligently routes the agent execution graph based on planner signals,
confidence bounds, and explicit Human-in-the-Loop (HITL) safety requirements.
"""
from __future__ import annotations

from agent.state import AgentState
from utils.logger import agent_logger as logger

# Sub-categories directed to browser automation
_BROWSER_SUBS = {"web_search", "web_form", "media_playback", "gov_portal"}

# Sub-categories directed to local OS primitives
_OS_SUBS = {
    "file_ops",
    "app_launch",
    "hardware",
    "settings",
    "process_mgmt",
    "security",
    "diagnostics",
}

def router(state: AgentState) -> str:
    """
    Evaluates state and determines the execution branch:
      1. Dangerous operations requiring user consent -> 'hitl_gate'
      2. Fine-grained sub-category (browser vs os)
      3. Fallback category (reasoning, browser, os)
    """
    sub = state.get("sub_category", "unknown")
    category = state.get("next_action", "end")
    confidence = state.get("confidence", 1.0)
    needs_hitl = state.get("needs_hitl", False)

    logger.debug(
        "Router: sub=%s category=%s confidence=%.2f needs_hitl=%s",
        sub, category, confidence, needs_hitl,
    )

    # If action requires explicit human verification and hasn't been approved yet
    if needs_hitl and not state.get("approved", False):
        return "hitl_gate"

    # Sub-category primary dispatch
    if sub in _BROWSER_SUBS:
        return "browser_executor"

    if sub in _OS_SUBS:
        return "os_executor"

    # Fallback to category signal
    if category == "browser":
        return "browser_executor"

    if category == "os":
        return "os_executor"

    if category == "reasoning":
        return "reasoning_executor"

    # Ambiguous / Low Confidence
    logger.info("Router defaulted to reasoning_executor for ambiguous input: sub=%s category=%s", sub, category)
    return "reasoning_executor"
