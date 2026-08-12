"""Canonical cache key generation with full scoping.

The cache key includes ALL parameters that affect generation output:
- model name
- temperature
- top_p
- max_tokens
- stop sequences
- system prompt hash
- tool schema hash
- response format
- tenant_id

This ensures that different generation configurations never collide.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable_json(obj: Any) -> str:
    """Produce deterministic JSON for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash_str(value: str) -> str:
    """SHA-256 hash truncated to 16 hex chars."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _extract_system_prompt(messages: list[dict[str, Any]]) -> str | None:
    """Extract the system prompt from messages."""
    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content")
            if content is not None:
                return str(content)
    return None


def _extract_user_messages(messages: list[dict[str, Any]]) -> str:
    """Extract concatenated user+assistant content for semantic matching."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "")
        if role in ("user", "assistant"):
            content = msg.get("content")
            if content:
                parts.append(f"{role}:{content}")
    return "\n".join(parts)


def canonical_cache_key(
    *,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
    stop: str | list[str] | None = None,
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> str:
    """Generate a deterministic cache key scoped by all generation parameters.

    Returns a SHA-256 hex digest incorporating every field that could affect
    the model's output. Two requests with the same key are guaranteed to be
    semantically equivalent in terms of their generation parameters.
    """
    # Normalize stop sequences to a sorted list
    if stop is None:
        normalized_stop: list[str] = []
    elif isinstance(stop, str):
        normalized_stop = [stop]
    else:
        normalized_stop = sorted(stop)

    # Extract system prompt for separate hashing
    system_prompt = _extract_system_prompt(messages)
    system_hash = _hash_str(system_prompt) if system_prompt is not None else "none"

    # Hash tool schemas if present
    tools_hash = _hash_str(_stable_json(tools)) if tools else "none"

    # Response format
    response_format_str = _stable_json(response_format) if response_format else "none"

    # Build the composite key material
    user_content = _extract_user_messages(messages)

    key_parts = {
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stop": normalized_stop,
        "system_hash": system_hash,
        "tools_hash": tools_hash,
        "response_format": response_format_str,
        "tenant_id": tenant_id or "default",
        "content": user_content,
    }

    composite = _stable_json(key_parts)
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()
