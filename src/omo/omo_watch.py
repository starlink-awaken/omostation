"""omo watch — 实时监控模式.

定期运行 doctor 检查，监控系统健康状态变化.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime

from omo.omo_doctor import cmd_doctor


def _run_doctor_json() -> dict:
    """运行 doctor 检查并返回 JSON."""
    import io

    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        cmd_doctor(json_output=True)
        output = buffer.getvalue()
        return json.loads(output)
    except Exception as e:
        return {"error": str(e)}
    finally:
        sys.stdout = old_stdout


def cmd_watch(interval: int = 60, max_iterations: int | None = None) -> int:
    """实时监控模式."""
    print(f"Starting omo watch (interval: {interval}s)")
    print("Press Ctrl+C to stop\n")

    iteration = 0
    last_status = None

    try:
        while max_iterations is None or iteration < max_iterations:
            iteration += 1
            now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

            result = _run_doctor_json()

            if "error" in result:
                print(f"[{now}] ERROR: {result['error']}")
            else:
                summary = result.get("summary", {})
                ok = summary.get("ok", 0)
                warn = summary.get("warn", 0)
                fail = summary.get("fail", 0)

                # Detect changes
                current_status = f"{ok}/{warn}/{fail}"
                status_changed = (
                    last_status is not None and current_status != last_status
                )
                last_status = current_status

                if status_changed:
                    print(f"[{now}] CHANGED: {ok} ok, {warn} warn, {fail} fail")
                elif fail > 0:
                    print(f"[{now}] DEGRADED: {ok} ok, {warn} warn, {fail} fail")
                elif warn > 0:
                    print(f"[{now}] WARNING: {ok} ok, {warn} warn, {fail} fail")
                else:
                    print(f"[{now}] OK: {ok} ok, {warn} warn, {fail} fail")

            if max_iterations is None or iteration < max_iterations:
                time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nWatch stopped.")

    return 0
