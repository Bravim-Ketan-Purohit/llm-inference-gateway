"""Tests for the token bucket rate limiter."""

import time

import pytest

from gateway.limits.rate_limiter import TokenBucket, TokenBucketRateLimiter


class TestTokenBucket:
    """Token bucket algorithm tests."""

    def test_starts_at_full_capacity(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        assert bucket.available_tokens == pytest.approx(10.0, abs=0.1)

    def test_consume_reduces_tokens(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        assert bucket.consume(5.0) is True
        assert bucket.available_tokens == pytest.approx(5.0, abs=0.2)

    def test_consume_fails_when_insufficient(self):
        bucket = TokenBucket(capacity=5.0, refill_rate=1.0)
        assert bucket.consume(10.0) is False

    def test_refill_over_time(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=100.0)
        bucket.consume(10.0)
        time.sleep(0.05)  # 50ms → expect ~5 tokens back
        assert bucket.available_tokens >= 3.0  # Allow for timing variance

    def test_capacity_is_max(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1000.0)
        time.sleep(0.1)
        assert bucket.available_tokens <= 10.0


class TestTokenBucketRateLimiter:
    """Rate limiter with per-tenant buckets."""

    def test_allows_initial_request(self):
        limiter = TokenBucketRateLimiter(capacity=10.0, refill_rate=1.0)
        assert limiter.allow("tenant-1") is True

    def test_blocks_after_exhaustion(self):
        limiter = TokenBucketRateLimiter(capacity=3.0, refill_rate=0.0)
        assert limiter.allow("tenant-1") is True
        assert limiter.allow("tenant-1") is True
        assert limiter.allow("tenant-1") is True
        assert limiter.allow("tenant-1") is False

    def test_separate_buckets_per_tenant(self):
        limiter = TokenBucketRateLimiter(capacity=2.0, refill_rate=0.0)
        # Exhaust tenant-1
        limiter.allow("tenant-1")
        limiter.allow("tenant-1")
        assert limiter.allow("tenant-1") is False
        # tenant-2 still has tokens
        assert limiter.allow("tenant-2") is True

    def test_reset_refills_bucket(self):
        limiter = TokenBucketRateLimiter(capacity=2.0, refill_rate=0.0)
        limiter.allow("tenant-1")
        limiter.allow("tenant-1")
        assert limiter.allow("tenant-1") is False
        limiter.reset("tenant-1")
        assert limiter.allow("tenant-1") is True

    def test_remaining_reports_tokens(self):
        limiter = TokenBucketRateLimiter(capacity=10.0, refill_rate=0.0)
        limiter.allow("tenant-1", tokens=3.0)
        assert limiter.remaining("tenant-1") == pytest.approx(7.0, abs=0.1)
