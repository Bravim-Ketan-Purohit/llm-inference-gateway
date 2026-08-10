"""Backend protocol and circuit breaker implementation."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from gateway.api.schemas import ChatCompletionRequest, ChatCompletionResponse


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerState:
    """Tracks circuit breaker state for a single backend.

    The circuit breaker pattern prevents cascading failures by stopping
    requests to unhealthy backends.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 1

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    half_open_calls: int = 0
    _successes_in_half_open: int = field(default=0, init=False)

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self._successes_in_half_open += 1
            if self._successes_in_half_open >= self.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self._successes_in_half_open = 0
                self.half_open_calls = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call, potentially opening the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open immediately opens
            self.state = CircuitState.OPEN
            self.half_open_calls = 0
            self._successes_in_half_open = 0
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if a request is allowed through."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                self._successes_in_half_open = 0
                return True
            return False

        # HALF_OPEN: allow limited calls
        if self.half_open_calls < self.half_open_max_calls:
            self.half_open_calls += 1
            return True
        return False


@runtime_checkable
class LLMBackend(Protocol):
    """Protocol for LLM backend adapters."""

    @property
    def name(self) -> str:
        """Backend identifier."""
        ...

    @property
    def is_available(self) -> bool:
        """Whether the backend is configured and reachable."""
        ...

    async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Send a chat completion request."""
        ...

    async def chat_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[str]:
        """Stream a chat completion request, yielding SSE data lines."""
        ...

    async def health_check(self) -> bool:
        """Check backend health."""
        ...
