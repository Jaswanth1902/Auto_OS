# AutoOS Agent Core & Orchestration

This directory (`server/agent`) contains the primary decision-making orchestration layer of AutoOS, built on top of **LangGraph**.

## State Transitions
The workflow transitions based on the `AgentState` via the `router.py` edge conditions:
- **`planner`**: Receives an input task and decides the `sub_category`, `next_action`, and parameters. It relies heavily on `server/agent/prompts.py` (modularized). To prevent recursive memory leakage (e.g., in loops or human-in-the-loop overrides), non-reducer fields like `action_params`, `entities`, and `plan` are dynamically cleared or overwritten on every invocation.
- **Fast-Track Check**: The heuristic check at the Gateway entry in `server/main.py` intercepts clear intents before reaching the LLM and forwards directly to the `planner` node via the fast-tracked action mechanism.
- **`router`**: The conditional edge that connects the planner to corresponding executors (`browser_executor` or `os_executor`) based on the highest confidence signal (e.g., prioritizing `sub_category` over `category`).
- **`executor`**: Dispatches the action to either a Playwright agent (via `browser-use`) or an OS agent based on routing results.

## Node Responsibilities
1. **`planner.py`**: A structured LLM node that extracts intents, translates instructions, evaluates confidence, and produces user-facing Plain English descriptions.
2. **`router.py`**: Enforces strict fallback rules and transitions graph edges cleanly based on the Planner outputs.
3. **`fast_track_rules.py`**: Configuration-driven rules to skip LLM analysis for simple commands (like `Open calculator`).

## Key Rotation Policies
To guarantee system stability, AutoOS aggregates Google Gemini API keys into a rotational pool (`LLM_API_KEYS`).
- **`llm_factory.py`**: All tools and nodes must initialize the LLM through `get_llm()` or `invoke_with_fallback()`.
- **429 Rate-Limits**: When the Gemini API encounters `ResourceExhausted` quota limits, `invoke_with_fallback` employs an exponential back-off and transparently retries the query on the next API key in the round-robin lock cycle.
