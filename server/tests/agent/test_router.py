import pytest
from agent.nodes.router import router

def test_router_browser_sub():
    state = {"sub_category": "web_search", "next_action": "os", "confidence": 1.0, "needs_hitl": False}
    assert router(state) == "browser_executor"

def test_router_os_sub():
    state = {"sub_category": "file_ops", "next_action": "browser", "confidence": 1.0, "needs_hitl": False}
    assert router(state) == "os_executor"

def test_router_fallback_browser():
    state = {"sub_category": "unknown", "next_action": "browser", "confidence": 1.0, "needs_hitl": False}
    assert router(state) == "browser_executor"

def test_router_fallback_os():
    state = {"sub_category": "unknown", "next_action": "os", "confidence": 1.0, "needs_hitl": False}
    assert router(state) == "os_executor"

def test_router_fallback_reasoning():
    state = {"sub_category": "unknown", "next_action": "reasoning", "confidence": 1.0, "needs_hitl": False}
    assert router(state) == "reasoning_executor"

def test_router_fast_tracked_browser():
    state = {"sub_category": "fast_tracked", "next_action": "browser", "confidence": 1.0, "needs_hitl": False}
    assert router(state) == "browser_executor"

def test_router_fast_tracked_os():
    state = {"sub_category": "fast_tracked", "next_action": "os", "confidence": 1.0, "needs_hitl": False}
    assert router(state) == "os_executor"

def test_router_ambiguous_end():
    state = {"sub_category": "unknown", "next_action": "ambiguous", "confidence": 1.0, "needs_hitl": False}
    assert router(state) == "end"
