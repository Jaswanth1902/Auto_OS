from fastapi import APIRouter
from pathlib import Path
from datetime import datetime
import json
from utils.logger import api_logger as logger

router = APIRouter(prefix="/system/threads", tags=["Threads"])

def _sanitize_messages(messages: list) -> list:
    """
    Normalize a mixed list of messages to plain {id, role, content, ...} dicts.
    LangGraph's add_messages may store LangChain AIMessage / HumanMessage objects
    whose 'content' field is a list of {type, text, extras} blocks instead of a str.
    This ensures React always receives a plain string in the content field.
    """
    clean = []
    for m in messages:
        # Handle both dict and LangChain BaseMessage objects
        if hasattr(m, "content"):
            role = getattr(m, "type", "agent")          # AIMessage -> "ai"
            role = "agent" if role in ("ai", "assistant") else role
            raw_content = m.content
        elif isinstance(m, dict):
            role = m.get("role", m.get("type", "system"))
            raw_content = m.get("content", "")
        else:
            continue

        # content can be a list of content blocks from multi-modal responses
        if isinstance(raw_content, list):
            parts = []
            for block in raw_content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    parts.append(block.get("text", str(block)))
                else:
                    parts.append(str(block))
            content_str = " ".join(parts)
        elif isinstance(raw_content, str):
            content_str = raw_content
        else:
            content_str = str(raw_content)

        entry = {
            "id": m.get("id", "") if isinstance(m, dict) else getattr(m, "id", ""),
            "role": role,
            "content": content_str,
        }
        # Preserve optional display fields if present
        for field in ("type", "subCategory"):
            val = m.get(field) if isinstance(m, dict) else getattr(m, field, None)
            if val:
                entry[field] = val
        clean.append(entry)
    return clean

@router.post("/save")
async def save_thread(data: dict):
    thread_id = data.get("id", "default")
    messages = _sanitize_messages(data.get("messages", []))

    thread_path = Path("server/knowledge/threads")
    thread_path.mkdir(parents=True, exist_ok=True)

    with open(thread_path / f"{thread_id}.json", "w") as f:
        json.dump({
            "id": thread_id,
            "last_updated": datetime.now().isoformat(),
            "messages": messages
        }, f, indent=2)

    return {"status": "saved"}

@router.get("/latest")
async def get_latest_thread():
    thread_path = Path("server/knowledge/threads")
    if not thread_path.exists():
        return {"messages": [], "id": "new-" + datetime.now().strftime("%Y%m%d%H%M%S")}

    files = list(thread_path.glob("*.json"))
    if not files:
        return {"messages": [], "id": "new-" + datetime.now().strftime("%Y%m%d%H%M%S")}

    # Sort by modification time
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    with open(latest_file, "r") as f:
        return json.load(f)

@router.get("")
async def list_threads():
    thread_path = Path("server/knowledge/threads")
    if not thread_path.exists(): return []

    threads = []
    for f in thread_path.glob("*.json"):
        with open(f, "r") as tf:
            data = json.load(tf)
            threads.append({
                "id": data["id"],
                "last_updated": data["last_updated"],
                "preview": data["messages"][0]["content"] if data["messages"] else "Empty Chat"
            })
    return sorted(threads, key=lambda x: x["last_updated"], reverse=True)
