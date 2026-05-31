"""
process_module.py — Running process management for AutoOS.
Uses action_params.action and action_params.targets from the planner.
"""
from __future__ import annotations

import logging

import psutil

from utils.logger import agent_logger as logger
_MAX_LIST = 15


_SKIP_PROCESSES = {
    "system idle process", "system", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe",
    "smss", "csrss", "wininit", "services", "lsass", "svchost", "explorer"
}

async def run(task: str, entities: list[str], action_params: dict) -> str:
    action: str = action_params.get("action", "list").lower()
    targets: list[str] = action_params.get("targets") if "targets" in action_params else entities
    task_lower = task.lower()

    if action == "kill" or any(w in task_lower for w in ("close", "kill", "stop", "end", "terminate")):
        return await _kill_process(targets)
    return await _list_processes()


async def _list_processes() -> str:
    procs = []
    for p in psutil.process_iter(["name", "cpu_percent", "memory_info"]):
        try:
            name = p.info.get("name")
            if not name:
                continue
            if name.lower() in _SKIP_PROCESSES:
                continue
            
            mem_info = p.info.get("memory_info")
            mem_mb = mem_info.rss / (1024 * 1024) if mem_info else 0
            procs.append((mem_mb, name))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(reverse=True)
    lines = [f"Top {_MAX_LIST} running applications by memory usage:\n"]
    for mem, name in procs[:_MAX_LIST]:
        lines.append(f"  {name}  ({mem:.0f} MB)")
    return "\n".join(lines)


async def _kill_process(targets: list[str]) -> str:
    if not targets:
        return "Which application would you like me to close? Please say the name."
        
    killed = []
    not_found = []
    skipped = []
    
    for target in targets:
        target_lower = target.lower().replace(".exe", "")
        found = False
        for p in psutil.process_iter(["name", "pid"]):
            try:
                name = p.info.get("name")
                if not name:
                    continue
                proc_name = name.lower().replace(".exe", "")
                
                if target_lower in proc_name or proc_name in target_lower:
                    if name.lower() in _SKIP_PROCESSES or proc_name in _SKIP_PROCESSES:
                        skipped.append(name)
                        found = True
                        continue
                        
                    p.terminate()
                    killed.append(name)
                    found = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if not found:
            not_found.append(target)

    lines = []
    if killed:
        lines.append(f"Closed: {', '.join(set(killed))}")
    if skipped:
        lines.append(f"Skipped critical system processes: {', '.join(set(skipped))}")
    if not_found:
        lines.append(f"Could not find: {', '.join(not_found)}")
        
    return "\n".join(lines) if lines else "No matching applications found."
