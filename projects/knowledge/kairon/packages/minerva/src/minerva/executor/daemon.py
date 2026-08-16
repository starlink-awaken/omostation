"""Minerva daemon — background process for scheduled/watch execution modes."""

from __future__ import annotations

import asyncio
import contextlib
import signal
import time
from typing import Any


def main() -> Any:
    """Start Minerva daemon with scheduled + watch execution loops."""
    print("Minerva daemon starting...")
    return asyncio.run(_run_daemon())


async def _run_daemon() -> int:
    """Main daemon event loop with graceful shutdown."""
    from minerva.init import create_default_executor

    executor = create_default_executor()

    # Restore persisted state
    restored = executor.restore_state()
    print(f"Restored {restored['scheduled']} scheduled, {restored['watch']} watch tasks.")

    # Handle shutdown
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        print("\nShutting down daemon...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _signal_handler)

    # Status heartbeat
    async def _heartbeat() -> None:
        while not shutdown_event.is_set():
            status = executor.health_check()
            print(
                f"[daemon] {time.strftime('%H:%M:%S')} scheduled={status['scheduled']} watch={status['watch']} budget_used=${status['budget_used']:.2f}"
            )
            await asyncio.sleep(60)

    heartbeat_task = asyncio.create_task(_heartbeat())

    print("Daemon ready. Scheduled + watch modes active.")
    await shutdown_event.wait()

    # Graceful cleanup
    heartbeat_task.cancel()
    executor.persist_state()
    print("Daemon stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
