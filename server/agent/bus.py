from typing import Dict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, execution_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[execution_id] = websocket

    def disconnect(self, execution_id: str):
        if execution_id in self.active_connections:
            del self.active_connections[execution_id]

    async def send_message(self, execution_id: str, message: dict):
        if execution_id in self.active_connections:
            await self.active_connections[execution_id].send_json(message)


manager = ConnectionManager()


async def emit_event(config: dict, event: dict):
    """
    Helper for nodes to send messages to the frontend via WebSocket.
    """
    # config is the LangGraph config object
    configurable = config.get("configurable", {})
    execution_id = configurable.get("execution_id")
    if execution_id:
        await manager.send_message(execution_id, event)
