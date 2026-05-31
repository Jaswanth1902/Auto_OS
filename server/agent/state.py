from typing import Annotated, List, Optional, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # ── Core conversation ────────────────────────────────────────────────────
    messages: Annotated[List[dict[str, str]], add_messages]
    task: str

    # ── Planner output — rich classification ─────────────────────────────────
    # Top-level route: "browser" | "os" | "ambiguous"
    next_action: str
    # Fine-grained intent — drives sub-routing and executor dispatch
    sub_category: str
    # Key nouns the planner extracted (app names, file types, settings, …)
    entities: List[str]
    # Structured parameters extracted by the planner for the executor
    action_params: dict[str, str]
    # One plain-English sentence describing what will happen
    plain_english_plan: str
    # 0.0–1.0 planner confidence; below 0.5 → HITL
    confidence: float
    # True when the action is irreversible (delete, kill process, OS update, …)
    needs_hitl: bool

    # ── Runtime options (passed from the frontend POST body) ─────────────────
    headless: Optional[bool]
    input_values: Optional[dict[str, str]]
    max_steps: Optional[int]

    # ── Final result ─────────────────────────────────────────────────────────
    result: str
    plan: List[str]
    # Persistent context for chaining (e.g. last_folder, last_app, last_contact)
    context: Annotated[dict, lambda old, new: {**old, **new}]
