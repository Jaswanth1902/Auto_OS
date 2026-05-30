"""
llm_factory.py — Centralised LLM creation with round-robin key rotation.

All nodes must import `get_llm()` from here instead of instantiating
ChatGoogleGenerativeAI directly.  This ensures all three API keys in
LLM_API_KEYS are used evenly and that a 429/ResourceExhausted on one key
automatically falls through to the next.
"""
from __future__ import annotations

import asyncio
import itertools
import logging
import os
import threading
import time
from typing import Iterator, Callable, Any

from langchain_google_genai import ChatGoogleGenerativeAI

from utils.logger import agent_logger as logger

# ---------------------------------------------------------------------------
# Key pool — built once at import time from the environment
# ---------------------------------------------------------------------------

def _load_keys() -> list[str]:
    keys_csv = os.getenv("LLM_API_KEYS", "")
    keys = [k.strip() for k in keys_csv.split(",") if k.strip()]
    # Also accept a bare GOOGLE_API_KEY as a fallback
    single = os.getenv("GOOGLE_API_KEY", "").strip()
    if single and single not in keys:
        keys.append(single)
    if not keys:
        raise RuntimeError(
            "No Gemini API keys found. Set LLM_API_KEYS or GOOGLE_API_KEY in server/.env"
        )
    logger.info("LLM key pool loaded: %d key(s)", len(keys))
    return keys


_KEY_POOL: list[str] = []
_KEY_CYCLE: Iterator[str] | None = None
_KEY_LOCK = threading.Lock()

def _get_cycle() -> Iterator[str]:
    global _KEY_POOL, _KEY_CYCLE
    with _KEY_LOCK:
        if _KEY_CYCLE is None:
            _KEY_POOL = _load_keys()
            _KEY_CYCLE = itertools.cycle(_KEY_POOL)
        return _KEY_CYCLE

def _next_key() -> str:
    with _KEY_LOCK:
        return next(_get_cycle())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_llm(
    *,
    temperature: float = 0.1,
    model: str | None = None,
) -> ChatGoogleGenerativeAI:
    """
    Return a ChatGoogleGenerativeAI instance using the next key in rotation.
    Call this fresh for each LLM invocation so keys are distributed evenly.
    """
    model_name = model or os.getenv("LLM_MODEL", "gemini-1.5-flash")
    api_key = _next_key()
    logger.debug("Using LLM model=%s key=...%s", model_name, api_key[-6:])
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=temperature,
        convert_system_message_to_human=True,
    )


async def invoke_with_fallback(chain_factory: Callable[[], Any], prompt: str, retries: int | None = None):
    """
    Invoke an LLM chain (structured or plain) with automatic key fallback.

    On a 429 / ResourceExhausted the call is retried using the next key.
    `retries` defaults to the number of keys in the pool.
    """
    _get_cycle()  # Ensure key pool is initialized safely
    max_tries = retries if retries is not None else len(_KEY_POOL)
    
    if max_tries < 1:
        max_tries = 1
        
    last_exc: Exception | None = None

    for attempt in range(max_tries):
        try:
            chain = chain_factory()
            return await chain.ainvoke(prompt)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            is_rate_limit = any(
                marker in msg for marker in ("429", "resourceexhausted", "quota", "rate limit")
            )
            if is_rate_limit and attempt < max_tries - 1:
                logger.warning(
                    "Rate limit on attempt %d/%d — switching to next key", attempt + 1, max_tries
                )
                last_exc = exc
                # Small back-off before rotating
                await asyncio.sleep(1.5)
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No LLM key loaders succeeded.")
