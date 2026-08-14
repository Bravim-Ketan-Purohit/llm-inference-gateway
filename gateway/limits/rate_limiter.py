"""Token bucket rate limiter with Redis-backed distributed state."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """In-memory token bucket for rate limiting.

    Uses the classic token bucket algorithm:
    - Tokens are added at `refill_rate` tokens/second
    - Bucket can hold at most `capacity` tokens
    - Each request consumes tokens; rejected if insufficient
    """

    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.last_refill = time.time()

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate limited."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    @property
    def available_tokens(self) -> float:
        """Current available tokens (after refill)."""
        self._refill()
        return self.tokens


class TokenBucketRateLimiter:
    """Per-tenant rate limiter using in-memory token buckets.

    Each tenant gets their own bucket with configurable capacity
    and refill rate.
    """

    def __init__(
        self,
        capacity: float = 100.0,
        refill_rate: float = 10.0,
    ) -> None:
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._buckets: dict[str, TokenBucket] = {}

    def _get_bucket(self, tenant_id: str) -> TokenBucket:
        """Get or create a bucket for a tenant."""
        if tenant_id not in self._buckets:
            self._buckets[tenant_id] = TokenBucket(
                capacity=self._capacity,
                refill_rate=self._refill_rate,
            )
        return self._buckets[tenant_id]

    def allow(self, tenant_id: str, tokens: float = 1.0) -> bool:
        """Check if a request is allowed for the given tenant.

        Returns True if allowed, False if rate-limited.
        """
        bucket = self._get_bucket(tenant_id)
        return bucket.consume(tokens)

    def remaining(self, tenant_id: str) -> float:
        """Return remaining token count for a tenant."""
        bucket = self._get_bucket(tenant_id)
        return bucket.available_tokens

    def reset(self, tenant_id: str) -> None:
        """Reset a tenant's bucket to full capacity."""
        if tenant_id in self._buckets:
            del self._buckets[tenant_id]
