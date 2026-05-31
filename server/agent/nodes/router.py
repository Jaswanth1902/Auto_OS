"""
router.py — Routes the graph to the correct executor based on the planner's
sub_category, category, confidence, and needs_hitl flag.
"""
from __future__ import annotations

import logging

from agent.state import AgentState

from utils.logger import agent_logger as logger

# Sub-categories that go to the browser executor
_BROWSER_SUBS = {"web_search", "web_form", "media_playback", "gov_portal"}

# Sub-categories that go to the OS executor
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
    Decides the next node based on:
      1. The fine-grained sub_category (preferred signal)
      2. The top-level category as a fallback
      3. Low confidence / needs_hitl → 'end' (HITL not wired yet, safe fail)
    """
    sub = state.get("sub_category", "unknown")
    category = state.get("next_action", "end")
    confidence = state.get("confidence", 1.0)
    needs_hitl = state.get("needs_hitl", False)

    logger.debug(
        "Router: sub=%s category=%s confidence=%.2f hitl=%s",
        sub, category, confidence, needs_hitl,
    )

    # Sub-category is the primary signal ─────────────────────────────────────
    if sub in _BROWSER_SUBS:
        return "browser_executor"

    if sub in _OS_SUBS:
        return "os_executor"

    # Fallback: use top-level category ────────────────────────────────────────
    if category == "browser":
        return "browser_executor"

    if category == "os":
        return "os_executor"

    if category == "reasoning":
        return "reasoning_executor"

    # Ambiguous / low confidence / unknown ────────────────────────────────────
    logger.warning("Router could not route: sub=%s category=%s — ending", sub, category)
    return "end"
