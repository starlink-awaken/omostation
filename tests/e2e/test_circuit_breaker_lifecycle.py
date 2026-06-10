"""E2E test: Circuit breaker lifecycle — CLOSED → OPEN → HALF_OPEN → CLOSED."""

from agora.core.registry import Service, ServiceRegistry


def _new_registry(**kwargs):
    import tempfile
    from pathlib import Path

    return ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-cb.json"), **kwargs)


class TestCircuitBreakerLifecycle:
    """Verify the complete circuit breaker state machine."""

    def test_closed_to_open(self):
        """3 failures should open the circuit."""
        r = _new_registry()
        r.register(Service("test-cb"))
        for _ in range(3):
            r.mark_failure("test-cb")
        svc = r.get("test-cb")
        assert svc.circuit_state == "OPEN"
        assert not svc.healthy

    def test_gradual_recovery(self):
        """4 successes should close the circuit (gradual decay)."""
        r = _new_registry()
        r.register(Service("test-cb"))
        for _ in range(3):
            r.mark_failure("test-cb")
        assert r.get("test-cb").circuit_state == "OPEN"
        for _ in range(4):
            r.mark_success("test-cb")
        svc = r.get("test-cb")
        assert svc.circuit_state == "CLOSED"
        assert svc.healthy

    def test_circuit_state_persistence_only_static(self):
        """Only static config should be persisted, not runtime state."""
        import tempfile
        from pathlib import Path

        path = Path(tempfile.mkdtemp()) / "test-cb.json"
        r = ServiceRegistry(storage_path=str(path))
        r.register(Service("test-cb"))
        r.mark_failure("test-cb")
        # Reload from disk
        r2 = ServiceRegistry(storage_path=str(path))
        svc = r2.get("test-cb")
        assert svc.healthy  # Should be True (default), not persisted
