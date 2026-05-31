"""
planner.py — Rich intent classification for AutoOS Gateway.

Returns a fully structured TaskPlan so executors receive zero-ambiguity
parameters — no raw string parsing happens downstream.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from agent.bus import emit_event
from agent.llm_factory import get_llm, invoke_with_fallback
from agent.state import AgentState

from utils.logger import agent_logger as logger


# ── Structured output schema ──────────────────────────────────────────────────

class TaskPlan(BaseModel):
    category: Literal["browser", "os", "reasoning", "ambiguous"] = Field(
        description="Top-level route: 'browser' needs the web, 'os' is local, 'reasoning' is for math/logic/knowledge."
    )
    sub_category: Literal[
        "web_search", "web_form", "media_playback", "gov_portal",
        "file_ops", "app_launch", "hardware", "settings",
        "process_mgmt", "security", "diagnostics", "vision", "app_control", 
        "knowledge", "math", "unknown",
    ] = Field(description="The specific intent within the chosen category.")
    plain_english_plan: str = Field(
        description=(
            "One short sentence (max 20 words) describing what will happen. "
            "Zero jargon. Write for someone who is not tech-savvy."
        )
    )
    entities: list[str] = Field(
        default_factory=list,
        description=(
            "Key nouns extracted from the request — app name, file name, "
            "website, setting name, device type. Keep entries short and exact."
        ),
    )
    action_params: dict = Field(
        default_factory=dict,
        description=(
            "Structured parameters for the executor. The schema depends on sub_category:\n"
            "  app_launch   → {app_name: str, search_aliases: list[str]}\n"
            "  file_ops     → {keywords: list[str], file_types: list[str], time_hint: str, action: str}\n"
            "  hardware     → {device_type: str}\n"
            "  settings     → {setting: str, direction: str, mode: str}\n"
            "  media_playback → {platform: str, content_type: str, query: str}\n"
            "  web_search   → {query: str}\n"
            "  web_form     → {site: str, action: str}\n"
            "  gov_portal   → {portal: str, action: str}\n"
            "  process_mgmt → {action: str, targets: list[str]}\n"
            "  security     → {action: str}\n"
            "  diagnostics  → {check_type: str}\n"
            "  vision       → {action: str}\n"
            "  app_control  → {app_name: str, action: str, input: str}"
        ),
    )
    needs_hitl: bool = Field(
        default=False,
        description=(
            "True if the action is IRREVERSIBLE or DESTRUCTIVE — deleting files, "
            "killing a system process, modifying system settings, submitting forms."
        ),
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in this classification (0.0-1.0).",
    )


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are the routing brain of AutoOS, a desktop assistant for non-technical users.

Your ONLY job is to classify the user's task as either "browser" or "os" and create a step-by-step plan.

═══════════════════════════════════
CLASSIFICATION RULES — READ CAREFULLY
═══════════════════════════════════

ALWAYS "browser" if the task needs the INTERNET:
✓ YouTube, Google, Gmail, any website
✓ "Play a song on YouTube"
✓ "Search for news"
✓ "Open twitter / instagram / any social media"
✓ "Check weather online"
✓ "Book a ticket / flight / hotel"
✓ "Download something from a website"

ALWAYS "os" if the task uses LOCAL COMPUTER:
✓ "Open calculator" → os (NEVER open google.com/calc)
✓ "Open notepad / paint / word / excel" → os
✓ "Open my downloads / desktop / documents folder" → os
✓ "Calculate 15+30" → os (use Windows Calculator)
✓ "Check my storage / disk space" → os
✓ "Check battery" → os
✓ "Check wifi / internet connection" → os
✓ "Open settings" → os
✓ "Open file explorer" → os

ALWAYS "reasoning" if the task is a QUESTION, MATH, or LOGIC:
✓ "Solve for X in 2x + 5 = 15" → reasoning
✓ "Explain how gravity works" → reasoning
✓ "A stone is thrown downward..." → reasoning
✓ "How many days until Christmas?" → reasoning
✓ "What is my plan for today?" → reasoning (check local memory)

═══════════════════════════════════
PLAN FORMAT — ALWAYS PLAIN ENGLISH
═══════════════════════════════════

Write the plan as simple steps a grandparent can understand.
NO technical jargon. NO code. NO file paths.

Good example for "open calculator and compute 15+30":
1. This is a local computer task — opening Windows Calculator
2. Opening the Calculator app on your computer
3. Typing 15+30 into the calculator
4. Showing you the result: 45

Good example for "open youtube and play trending songs":
1. This is an internet task — opening your browser
2. Going to YouTube website
3. Searching for trending songs in India
4. Playing the top trending song for you

═══════════════════════════════════
STRICT RULES
═══════════════════════════════════

1. Calculator = ALWAYS "os". Never "browser". Never google.com/calc.
2. Any local app = ALWAYS "os"
3. Any website / internet = ALWAYS "browser"
4. Keep plan steps short — max 6 steps
5. Never use words like: "exe", "subprocess", "API", "DOM", "render"
6. Always write as if speaking to an elderly person who is not tech-savvy
7. STICKY CONTEXT: If the user is already on a specific website (check 'last_url' in CURRENT CONTEXT), and asks to "play", "search", or "do something", ALWAYS use that same website unless they mention a new one. 
   - Example: If last_url was 'spotify.com', "play hit songs" → browser_executor (Spotify).
   - Example: If last_url was 'amazon.com', "find shoes" → browser_executor (Amazon).
8. USE PRONOUNS: If the user refers to "it", "him", or "that chat", look at the entities in CURRENT CONTEXT to resolve the target.
"""


# ── Planner node ──────────────────────────────────────────────────────────────

async def planner(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """
    Classifies the user task into a rich TaskPlan and stores it in AgentState.
    """
    task = state.get("task", "").strip()
    if not task:
        return {
            "next_action": "end",
            "sub_category": "unknown",
            "entities": [],
            "action_params": {},
            "plain_english_plan": "No task was provided.",
            "confidence": 1.0,
            "needs_hitl": False,
            "result": "No task provided.",
        }

    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(TaskPlan)
    
    # Inject persistent context for chaining
    ctx = state.get("context", {})
    ctx_str = f"\n\nCURRENT CONTEXT: {ctx}" if ctx else ""
    prompt = f'{_SYSTEM_PROMPT}{ctx_str}\n\nUser request: "{task}"'

    logger.info("Classifying task: %s", task)
    plan: TaskPlan = await invoke_with_fallback(structured_llm, prompt)
    logger.info(
        "Plan → category=%s sub=%s params=%s hitl=%s",
        plan.category, plan.sub_category, plan.action_params, plan.needs_hitl,
    )

    await emit_event(config, {
        "type": "classification",
        "category": plan.category,
        "sub_category": plan.sub_category,
        "plain_english_plan": plan.plain_english_plan,
        "confidence": plan.confidence,
        "needs_hitl": plan.needs_hitl,
    })

    return {
        "next_action": plan.category,
        "sub_category": plan.sub_category,
        "entities": plan.entities,
        "action_params": plan.action_params,
        "plain_english_plan": plan.plain_english_plan,
        "confidence": plan.confidence,
        "needs_hitl": plan.needs_hitl,
        "messages": [{
            "role": "assistant",
            "content": (
                f"[Planner] {plan.category}/{plan.sub_category} — "
                f"{plan.plain_english_plan}"
            ),
        }],
    }
