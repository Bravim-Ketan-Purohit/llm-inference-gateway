"""Backend pool with health checks and circuit breakers."""

from __future__ import annotations

import logging
from typing import Any

from gateway.api.schemas import ChatCompletionRequest, ChatCompletionResponse
from gateway.backends.protocol import CircuitBreakerState

logger = logging.getLogger(__name__)


class BackendPool:
    """Manages multiple LLM backends with health checks and failover.

    Backends are tried in priority order. Circuit breakers prevent
    cascading failures to unhealthy backends.
    """

    def __init__(self, backends: list[Any]) -> None:
        self._backends: list[Any] = backends
        self._circuit_breakers: dict[str, CircuitBreakerState] = {
            b.name: CircuitBreakerState() for b in backends
        }

    @property
    def backends(self) -> list[Any]:
        """All registered backends."""
        return self._backends

    @property
    def circuit_breakers(self) -> dict[str, CircuitBreakerState]:
        """Circuit breaker states for monitoring."""
        return self._circuit_breakers

    def get_available_backend(self) -> Any | None:
        """Return the first available backend whose circuit is not open."""
        for backend in self._backends:
            if not backend.is_available:
                continue
            cb = self._circuit_breakers[backend.name]
            if cb.can_execute():
                return backend
        return None

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Route request to the first healthy backend."""
        errors: list[str] = []

        for backend in self._backends:
            if not backend.is_available:
                continue
            cb = self._circuit_breakers[backend.name]
            if not cb.can_execute():
                continue

            try:
                result = await backend.chat(request)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure()
                errors.append(f"{backend.name}: {e}")
                logger.warning("Backend %s failed: %s", backend.name, e)
                continue

        raise RuntimeError(f"All backends failed: {'; '.join(errors)}")

    async def health_check_all(self) -> dict[str, bool]:
        """Run health checks on all backends."""
        results: dict[str, bool] = {}
        for backend in self._backends:
            try:
                results[backend.name] = await backend.health_check()
            except Exception:
                results[backend.name] = False
        return results
