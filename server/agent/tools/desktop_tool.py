"""
desktop_tool.py — OS task dispatcher for AutoOS.
Routes to the correct module based on sub_category.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("AutoOS.desktop")


async def run_os_task(
    task: str,
    sub_category: str = "unknown",
    entities: list[str] | None = None,
    action_params: dict | None = None,
) -> str:
    entities = entities or []
    action_params = action_params or {}
    logger.info(
        "OS dispatch: sub=%s entities=%s params=%s",
        sub_category,
        entities,
        action_params,
    )

    match sub_category:
        case "app_launch":
            from agent.modules import app_module

            return await app_module.run(task, entities, action_params)
        case "file_ops":
            from agent.modules import file_module

            return await file_module.run(task, entities, action_params)
        case "hardware":
            from agent.modules import hardware_module

            return await hardware_module.run(task, entities, action_params)
        case "settings":
            from agent.modules import settings_module

            return await settings_module.run(task, entities, action_params)
        case "process_mgmt":
            from agent.modules import process_module

            return await process_module.run(task, entities, action_params)
        case "security":
            from agent.modules import security_module

            return await security_module.run(task, entities, action_params)
        case "diagnostics":
            from agent.modules import diag_module

            return await diag_module.run(task, entities, action_params)
        case "vision":
            from agent.modules import visual_module

            return await visual_module.run(task, entities, action_params)
        case "app_control":
            from agent.modules import app_module

            return await app_module.run(task, entities, action_params)
        case _:
            logger.warning("Unknown sub_category '%s', trying app_launch", sub_category)
            from agent.modules import app_module

            return await app_module.run(task, entities, action_params)
