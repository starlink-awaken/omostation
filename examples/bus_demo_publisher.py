"""Bus demo publisher — publishes 3 sample events via agora.bus facade."""

from __future__ import annotations

import time
import uuid

from agora.bus import BusEnvelope, EventType, publish


def main() -> int:
    for i in range(3):
        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,  # type: ignore[reportCallIssue]
            source="bus_demo_publisher",  # type: ignore[reportCallIssue]
            payload={"iteration": i, "uuid": str(uuid.uuid4())},
            trace_id=f"demo-trace-{i}",
        )
        event_id = publish(env)
        print(f"published {i}: event_id={event_id}")
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
