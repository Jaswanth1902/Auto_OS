from agent.nodes.executor import (browser_executor, os_executor,
                                  reasoning_executor)
from agent.nodes.memory import memory_consolidator
from agent.nodes.planner import planner
from agent.nodes.router import router
from agent.state import AgentState
from langgraph.graph import END, StateGraph


def create_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("planner", planner)
    workflow.add_node("browser_executor", browser_executor)
    workflow.add_node("os_executor", os_executor)
    workflow.add_node("reasoning_executor", reasoning_executor)
    workflow.add_node("memory_consolidator", memory_consolidator)

    # Set Entry Point
    workflow.set_entry_point("planner")

    # Add Conditional Edges (The Gateway)
    workflow.add_conditional_edges(
        "planner",
        router,
        {
            "browser_executor": "browser_executor",
            "os_executor": "os_executor",
            "reasoning_executor": "reasoning_executor",
            "end": "memory_consolidator",
        },
    )

    # Transitions to Memory then END
    workflow.add_edge("browser_executor", "memory_consolidator")
    workflow.add_edge("os_executor", "memory_consolidator")
    workflow.add_edge("reasoning_executor", "memory_consolidator")
    workflow.add_edge("memory_consolidator", END)

    return workflow.compile()


# Singleton instance
app_graph = create_graph()
