"""Tests for circuit breaker state machine."""

import time

from gateway.backends.protocol import CircuitBreakerState, CircuitState


class TestCircuitBreakerClosed:
    """Tests for CLOSED state behavior."""

    def test_starts_closed(self):
        cb = CircuitBreakerState()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_success_keeps_closed(self):
        cb = CircuitBreakerState()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_failures_below_threshold_stay_closed(self):
        cb = CircuitBreakerState(failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True


class TestCircuitBreakerOpen:
    """Tests for OPEN state behavior."""

    def test_threshold_failures_opens_circuit(self):
        cb = CircuitBreakerState(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_open_circuit_blocks_requests(self):
        cb = CircuitBreakerState(failure_threshold=2, recovery_timeout=60.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False


class TestCircuitBreakerHalfOpen:
    """Tests for HALF_OPEN state and recovery."""

    def test_recovery_timeout_transitions_to_half_open(self):
        cb = CircuitBreakerState(failure_threshold=2, recovery_timeout=1.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Simulate time passing
        cb.last_failure_time = time.time() - 2.0
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes_circuit(self):
        cb = CircuitBreakerState(
            failure_threshold=2, recovery_timeout=0.0, half_open_max_calls=1
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Trigger half-open
        cb.last_failure_time = time.time() - 1.0
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
