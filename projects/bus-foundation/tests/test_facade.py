"""Test bus_foundation facade — publish/subscribe/schedule."""

from __future__ import annotations

from bus_foundation import BusEnvelope, EventType, publish, schedule, subscribe


class TestFacadeSubscribe:
    def test_subscribe_decorator_registers_callback(self) -> None:
        received: list[BusEnvelope] = []

        @subscribe("facade-test:*")
        def cb(env: BusEnvelope) -> None:
            received.append(env)

        env = BusEnvelope(type="facade-test:ping", source="test", payload={"k": "v"})
        publish(env)
        assert len(received) == 1
        assert received[0].id == env.id


class TestFacadeSchedule:
    def test_schedule_decorator_accepts_expr(self) -> None:
        @schedule("every 5m")
        def heartbeat() -> None:
            pass

        # If scheduling didn't raise, the decorator worked.
        assert callable(heartbeat)


class TestFacadePublish:
    def test_publish_dispatches_via_default_backend(self) -> None:
        received: list[BusEnvelope] = []

        @subscribe("pipeline:*")
        def cb(env: BusEnvelope) -> None:
            received.append(env)

        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="facade-test",
            payload={"id": 1},
        )
        event_id = publish(env)
        assert event_id == env.id
        assert len(received) == 1
        assert received[0].id == env.id
