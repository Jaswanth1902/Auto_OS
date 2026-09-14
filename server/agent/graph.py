"""
graph.py — StateGraph definition for AutoOS.
Wires planner, router, hitl_gate, executors, logger_node, and memory_consolidator.
"""
from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.planner import planner
from agent.nodes.router import router
from agent.nodes.hitl_gate import hitl_gate
from agent.nodes.executor import browser_executor, os_executor, reasoning_executor
from agent.nodes.logger import logger_node
from agent.nodes.memory import memory_consolidator

def hitl_router(state: AgentState) -> str:
    """Routes post-HITL gate state based on approval status."""
    status = state.get("status", "")
    if status == "approved":
        category = state.get("category", state.get("next_action", "os"))
        if category == "browser":
            return "browser_executor"
        return "os_executor"
    # If awaiting approval or blocked, skip execution and proceed to logging/memory
    return "logger_node"

def create_graph():
    workflow = StateGraph(AgentState)

    # 1. Register Nodes
    workflow.add_node("planner", planner)
    workflow.add_node("hitl_gate", hitl_gate)
    workflow.add_node("browser_executor", browser_executor)
    workflow.add_node("os_executor", os_executor)
    workflow.add_node("reasoning_executor", reasoning_executor)
    workflow.add_node("logger_node", logger_node)
    workflow.add_node("memory_consolidator", memory_consolidator)

    # 2. Set Entry Point
    workflow.set_entry_point("planner")

    # 3. Decision Gateway (Planner -> Router)
    workflow.add_conditional_edges(
        "planner",
        router,
        {
            "hitl_gate": "hitl_gate",
            "browser_executor": "browser_executor",
            "os_executor": "os_executor",
            "reasoning_executor": "reasoning_executor",
            "end": "logger_node"
        }
    )

    # 4. HITL Evaluation Gate
    workflow.add_conditional_edges(
        "hitl_gate",
        hitl_router,
        {
            "browser_executor": "browser_executor",
            "os_executor": "os_executor",
            "logger_node": "logger_node"
        }
    )

    # 5. Executors stream into telemetry logger
    workflow.add_edge("browser_executor", "logger_node")
    workflow.add_edge("os_executor", "logger_node")
    workflow.add_edge("reasoning_executor", "logger_node")

    # 6. Telemetry streams into long-term memory, then completes
    workflow.add_edge("logger_node", "memory_consolidator")
    workflow.add_edge("memory_consolidator", END)

    return workflow.compile()

# Singleton graph instance
app_graph = create_graph()
