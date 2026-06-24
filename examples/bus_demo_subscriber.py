"""Bus demo subscriber — registers a callback via agora.bus facade."""

from __future__ import annotations

import time

from agora.bus import BusEnvelope, subscribe


@subscribe("pipeline:*")
def on_pipeline_event(env: BusEnvelope) -> None:
    print(f"received: {env.type} payload={env.payload}")


def main() -> int:
    print("subscriber registered; press Ctrl-C to exit")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
