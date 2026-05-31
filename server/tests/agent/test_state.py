import pytest
from agent.state import AgentState
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
import operator

# Test that state fields preserve appropriately and that non-reducer fields can be overwritten
def test_agent_state_reducers():
    workflow = StateGraph(AgentState)

    # define simple nodes
    def node_a(state):
        return {
            "task": "old task",
            "next_action": "browser",
            "messages": [{"role": "user", "content": "hello"}]
        }
    def node_b(state):
        return {
            "task": "new task",
            "next_action": "os",
            "messages": [{"role": "assistant", "content": "world"}]
        }

    workflow.add_node("node_a", node_a)
    workflow.add_node("node_b", node_b)
    workflow.set_entry_point("node_a")
    workflow.add_edge("node_a", "node_b")
    workflow.set_finish_point("node_b")
    app = workflow.compile()

    final_state = app.invoke({"task": "initial"})
    assert final_state["task"] == "new task" # Gets overwritten
    assert final_state["next_action"] == "os" # Gets overwritten

    # Messages should be merged/appended correctly by add_messages reducer
    assert len(final_state["messages"]) == 2
    assert final_state["messages"][0].content == "hello"
    assert final_state["messages"][1].content == "world"
