"""Prometheus-compatible CLI metrics collector with file-backed persistence.

Implements BET-Y1Q4-T8-14 for comprehensive command observability, latency histograms,
and Prometheus text exposition without requiring heavyweight daemons.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


class MetricsCollector:
    """Collects and aggregates CLI execution telemetry."""

    def __init__(self, storage_path: Path | None = None, max_records: int = 1000):
        if storage_path is None:
            home = Path.home()
            storage_path = home / ".workspace" / "telemetry" / "cockpit_metrics.json"
        self.storage_path = storage_path
        self.max_records = max_records
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        """Load persisted metrics or initialize fresh store."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "counters" in data:
                        return data
            except Exception:
                pass
        return {
            "counters": {},  # "command:domain:exit_code": count
            "durations": [],  # list of float durations
            "errors": {},  # "command:domain:exit_code": count
            "history": [],  # ring buffer of recent command events
        }

    def _save(self) -> None:
        """Atomically persist metrics to storage path."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.storage_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.storage_path)
        except Exception:
            # Observability must never crash the main CLI
            pass

    def record_command(
        self,
        command: str,
        domain: str,
        exit_code: int,
        duration_seconds: float,
        error: str | None = None,
    ) -> None:
        """Record a single command execution."""
        key = f"{command}:{domain}:{exit_code}"
        self._data["counters"][key] = self._data["counters"].get(key, 0) + 1

        self._data["durations"].append(round(duration_seconds, 4))
        # Keep only the latest 1000 durations for percentiles
        if len(self._data["durations"]) > self.max_records:
            self._data["durations"] = self._data["durations"][-self.max_records :]

        if exit_code != 0 or error:
            err_key = f"{command}:{domain}:{exit_code}"
            self._data["errors"][err_key] = self._data["errors"].get(err_key, 0) + 1

        # Append to history ring buffer
        entry = {
            "ts": int(time.time()),
            "command": command,
            "domain": domain,
            "exit_code": exit_code,
            "duration": round(duration_seconds, 4),
        }
        if error:
            entry["error"] = error[:100]

        self._data["history"].append(entry)
        if len(self._data["history"]) > self.max_records:
            self._data["history"] = self._data["history"][-self.max_records :]

        self._save()

    def get_summary(self) -> dict[str, Any]:
        """Aggregate summary metrics for CLI inspection."""
        total_invocations = sum(self._data["counters"].values())
        total_errors = sum(self._data["errors"].values())
        durations = sorted(self._data.get("durations", []))

        p50 = 0.0
        p90 = 0.0
        p99 = 0.0
        avg_dur = 0.0
        if durations:
            n = len(durations)
            p50 = durations[int(n * 0.50)]
            p90 = durations[min(int(n * 0.90), n - 1)]
            p99 = durations[min(int(n * 0.99), n - 1)]
            avg_dur = round(sum(durations) / n, 4)

        domain_breakdown: dict[str, int] = {}
        for key, count in self._data["counters"].items():
            parts = key.split(":")
            domain = parts[1] if len(parts) > 1 else "unknown"
            domain_breakdown[domain] = domain_breakdown.get(domain, 0) + count

        return {
            "total_invocations": total_invocations,
            "total_errors": total_errors,
            "error_rate": round(total_errors / max(1, total_invocations), 4),
            "latency_seconds": {
                "avg": avg_dur,
                "p50": p50,
                "p90": p90,
                "p99": p99,
            },
            "domain_distribution": domain_breakdown,
            "recent_invocations": len(self._data["history"]),
        }

    def export_prometheus_text(self) -> str:
        """Export metrics in standard Prometheus exposition format."""
        lines = [
            "# HELP cockpit_command_total Total number of cockpit command invocations.",
            "# TYPE cockpit_command_total counter",
        ]
        for key, count in sorted(self._data["counters"].items()):
            parts = key.split(":")
            cmd = parts[0] if len(parts) > 0 else "unknown"
            dom = parts[1] if len(parts) > 1 else "unknown"
            code = parts[2] if len(parts) > 2 else "0"
            lines.append(
                f'cockpit_command_total{{command="{cmd}",domain="{dom}",exit_code="{code}"}} {count}'
            )

        lines.extend([
            "",
            "# HELP cockpit_command_errors_total Total number of command invocation failures.",
            "# TYPE cockpit_command_errors_total counter",
        ])
        for key, count in sorted(self._data["errors"].items()):
            parts = key.split(":")
            cmd = parts[0] if len(parts) > 0 else "unknown"
            dom = parts[1] if len(parts) > 1 else "unknown"
            code = parts[2] if len(parts) > 2 else "1"
            lines.append(
                f'cockpit_command_errors_total{{command="{cmd}",domain="{dom}",exit_code="{code}"}} {count}'
            )

        durations = sorted(self._data.get("durations", []))
        total_count = len(durations)
        total_sum = round(sum(durations), 4)

        p50 = durations[int(total_count * 0.50)] if durations else 0.0
        p90 = durations[min(int(total_count * 0.90), total_count - 1)] if durations else 0.0
        p99 = durations[min(int(total_count * 0.99), total_count - 1)] if durations else 0.0

        lines.extend([
            "",
            "# HELP cockpit_command_duration_seconds Command execution latency in seconds.",
            "# TYPE cockpit_command_duration_seconds summary",
            f'cockpit_command_duration_seconds{{quantile="0.5"}} {p50}',
            f'cockpit_command_duration_seconds{{quantile="0.9"}} {p90}',
            f'cockpit_command_duration_seconds{{quantile="0.99"}} {p99}',
            f"cockpit_command_duration_seconds_sum {total_sum}",
            f"cockpit_command_duration_seconds_count {total_count}",
        ])
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Reset all metrics."""
        self._data = {
            "counters": {},
            "durations": [],
            "errors": {},
            "history": [],
        }
        self._save()


_GLOBAL_COLLECTOR: MetricsCollector | None = None


def get_metrics_collector(storage_path: Path | None = None) -> MetricsCollector:
    """Retrieve or initialize the global MetricsCollector singleton."""
    global _GLOBAL_COLLECTOR
    if _GLOBAL_COLLECTOR is None or storage_path is not None:
        _GLOBAL_COLLECTOR = MetricsCollector(storage_path=storage_path)
    return _GLOBAL_COLLECTOR


def record_command_metric(
    command: str,
    domain: str,
    exit_code: int,
    duration_seconds: float,
    error: str | None = None,
) -> None:
    """Global helper to record a command execution metric."""
    collector = get_metrics_collector()
    collector.record_command(command, domain, exit_code, duration_seconds, error=error)
