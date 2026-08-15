"""Request router dispatching to backend pool with caching."""

from __future__ import annotations

import logging
import time
from typing import Any

from gateway.api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    UsageInfo,
)
from gateway.backends.pool import BackendPool
from gateway.config import Settings

logger = logging.getLogger(__name__)


class Router:
    """Routes chat completion requests through cache and backend layers.

    Flow:
    1. Check semantic cache for hit
    2. If miss, route to backend pool
    3. Store response in cache for future hits
    4. Record usage metrics
    """

    def __init__(
        self,
        backend_pool: BackendPool,
        settings: Settings,
        semantic_cache: Any | None = None,
        usage_accountant: Any | None = None,
    ) -> None:
        self._pool = backend_pool
        self._settings = settings
        self._cache = semantic_cache
        self._usage = usage_accountant

    async def route(
        self,
        request: ChatCompletionRequest,
        tenant_id: str = "default",
    ) -> ChatCompletionResponse:
        """Route a request through cache and backend layers."""
        start = time.time()
        messages_raw = [{"role": m.role, "content": m.content} for m in request.messages]

        # Check cache
        if self._cache and not request.stream:
            try:
                cached, cache_key = await self._cache.lookup(
                    model=request.model,
                    messages=messages_raw,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    max_tokens=request.max_tokens,
                    stop=request.stop,
                    tools=[t.model_dump() for t in request.tools] if request.tools else None,
                    response_format=(
                        request.response_format.model_dump() if request.response_format else None
                    ),
                    tenant_id=tenant_id,
                )
            except Exception as e:
                logger.warning("Cache lookup failed: %s", e)
                cached = None
                cache_key = ""

            if cached:
                latency_ms = (time.time() - start) * 1000
                if self._usage:
                    await self._usage.record_usage(
                        tenant_id=tenant_id,
                        model=request.model,
                        prompt_tokens=0,
                        completion_tokens=0,
                        cached=True,
                        backend="cache",
                        latency_ms=latency_ms,
                    )
                return ChatCompletionResponse(
                    model=request.model,
                    choices=[Choice(message=ChoiceMessage(content=cached))],
                    usage=UsageInfo(),
                    system_fingerprint="cache-hit",
                )

        # Route to backend
        response = await self._pool.chat(request)
        latency_ms = (time.time() - start) * 1000

        # Store in cache
        if self._cache and not request.stream and response.choices:
            content = response.choices[0].message.content or ""
            if content:
                try:
                    await self._cache.store(
                        cache_key=cache_key,
                        messages=messages_raw,
                        response_content=content,
                        metadata={"model": request.model, "tenant_id": tenant_id},
                    )
                except Exception as e:
                    logger.warning("Cache store failed: %s", e)

        # Record usage
        if self._usage:
            backend = self._pool.get_available_backend()
            await self._usage.record_usage(
                tenant_id=tenant_id,
                model=request.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                cached=False,
                backend=backend.name if backend else "unknown",
                latency_ms=latency_ms,
            )

        return response
