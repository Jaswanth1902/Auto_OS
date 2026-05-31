import os
from datetime import datetime

from agent.state import AgentState

MEMORY_FILE = "server/knowledge/MEMORY.md"
HABITS_FILE = "server/knowledge/HABITS.md"


def memory_consolidator(state: AgentState):
    """
    Reflects on the completed task and updates the local Markdown memory/habits.
    """
    task = state.get("task", "")
    result = state.get("result", "")
    category = state.get("category", "unknown")

    # 1. Update Recent Tasks in MEMORY.md
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            content = f.read()

        # Simple appending to 'Recent Tasks' section
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n- [{timestamp}] {task} -> {result[:50]}..."

        if "## Recent Tasks" in content:
            updated_content = content.replace(
                "## Recent Tasks", f"## Recent Tasks{new_entry}"
            )
            with open(MEMORY_FILE, "w") as f:
                f.write(updated_content)

    # 2. Pattern recognition for HABITS.md
    if os.path.exists(HABITS_FILE):
        # Basic logic: If a keyword appears frequently, note it
        keywords = ["whatsapp", "calc", "browser", "downloads"]
        found = [k for k in keywords if k in task.lower()]

        if found:
            with open(HABITS_FILE, "a") as f:
                f.write(f"\n- Observed usage of {', '.join(found)} at {datetime.now()}")

    return state
