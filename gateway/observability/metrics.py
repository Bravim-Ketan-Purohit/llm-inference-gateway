"""Prometheus metrics instrumentation."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ─── Request metrics ────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "gateway_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ─── Cache metrics ──────────────────────────────────────────────────────────

CACHE_HITS = Counter(
    "gateway_cache_hits_total",
    "Total cache hits",
    ["layer"],  # "exact" or "semantic"
)

CACHE_MISSES = Counter(
    "gateway_cache_misses_total",
    "Total cache misses",
)

CACHE_LATENCY = Histogram(
    "gateway_cache_lookup_seconds",
    "Cache lookup latency",
    ["layer"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
)

# ─── Backend metrics ────────────────────────────────────────────────────────

BACKEND_REQUEST_COUNT = Counter(
    "gateway_backend_requests_total",
    "Total backend requests",
    ["backend", "status"],
)

BACKEND_LATENCY = Histogram(
    "gateway_backend_duration_seconds",
    "Backend request latency",
    ["backend"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# ─── Token metrics ──────────────────────────────────────────────────────────

TOKENS_PROCESSED = Counter(
    "gateway_tokens_total",
    "Total tokens processed",
    ["type", "model"],  # type: "prompt" or "completion"
)

# ─── Rate limiting metrics ──────────────────────────────────────────────────

RATE_LIMIT_REJECTIONS = Counter(
    "gateway_rate_limit_rejections_total",
    "Requests rejected by rate limiter",
    ["tenant_id"],
)

# ─── Circuit breaker metrics ────────────────────────────────────────────────

CIRCUIT_BREAKER_STATE = Gauge(
    "gateway_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["backend"],
)
