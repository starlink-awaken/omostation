"""MetricsCollector — Prometheus-style metrics accumulator."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _MetricEntry:
    """Internal representation of a single metric family."""

    name: str
    type: str  # counter / gauge / histogram
    help: str = ""
    values: list[tuple[dict[str, str], float]] = field(default_factory=list)
    # For histogram: accumulated raw observations (so we can compute buckets)
    observations: list[float] = field(default_factory=list)
    sum_val: float = 0.0
    count: int = 0


# Default histogram buckets (Prometheus-compatible, milliseconds-friendly)
_DEFAULT_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    25.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    float("inf"),
)


def _labels_key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


def _format_labels(labels: dict[str, str] | None) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return "{" + inner + "}"


def _escape_help(help_text: str) -> str:
    return help_text.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class MetricsCollector:
    """In-memory metrics collector that can dump Prometheus text format.

    Usage::

        mc = MetricsCollector()
        mc.counter("http_requests_total", {"method": "GET"})
        mc.gauge("memory_bytes", 1048576)
        mc.histogram("request_latency_ms", 12.5)
        mc.histogram("request_latency_ms", 45.0)
        print(mc.to_prometheus())
    """

    def __init__(self) -> None:
        self._metrics: dict[str, _MetricEntry] = {}

    def _get_or_create(self, name: str, mtype: str, help_text: str = "") -> _MetricEntry:
        if name not in self._metrics:
            self._metrics[name] = _MetricEntry(name=name, type=mtype, help=help_text)
        return self._metrics[name]

    # -- public API ----------------------------------------------------------

    def counter(self, name: str, labels: dict[str, str] | None = None, help_text: str = "") -> None:
        """Increment (or create) a counter by 1.

        If the metric already exists for the same label-set its value is incremented;
        otherwise a new label-set is added with value 1.
        """
        entry = self._get_or_create(name, "counter", help_text)
        key = _labels_key(labels)
        for i, (existing_labels, val) in enumerate(entry.values):
            if _labels_key(existing_labels) == key:
                entry.values[i] = (existing_labels, val + 1.0)
                return
        entry.values.append((labels or {}, 1.0))

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None, help_text: str = "") -> None:
        """Set a gauge to *value*.

        Overwrites any previous value for the same label-set.
        """
        entry = self._get_or_create(name, "gauge", help_text)
        key = _labels_key(labels)
        for i, (existing_labels, _) in enumerate(entry.values):
            if _labels_key(existing_labels) == key:
                entry.values[i] = (existing_labels, value)
                return
        entry.values.append((labels or {}, value))

    def histogram(self, name: str, value: float, help_text: str = "") -> None:
        """Record a histogram observation.

        Accumulates observations; bucket counts are computed on-demand in :meth:`to_prometheus`.
        """
        entry = self._get_or_create(name, "histogram", help_text)
        entry.observations.append(value)
        entry.sum_val += value
        entry.count += 1

    def to_prometheus(self) -> str:
        """Render all accumulated metrics in Prometheus text exposition format."""
        lines: list[str] = []

        for name, entry in sorted(self._metrics.items()):
            # HELP line
            help_str = _escape_help(entry.help or name)
            lines.append(f"# HELP {name} {help_str}")
            # TYPE line
            lines.append(f"# TYPE {name} {entry.type}")

            if entry.type == "histogram":
                # Compute buckets from observations
                buckets = list(_DEFAULT_BUCKETS)
                bucket_counts = [0] * len(buckets)
                for obs in entry.observations:
                    for bi, upper in enumerate(buckets):
                        if obs <= upper:
                            bucket_counts[bi] += 1
                            break

                for upper, bc in zip(buckets, bucket_counts):
                    lines.append(f'{name}_bucket{{le="{_fmt_bucket(upper)}"}} {_fmt_val(bc)}')
                lines.append(f'{name}_bucket{{le="+Inf"}} {_fmt_val(entry.count)}')
                lines.append(f"{name}_sum {_fmt_val(entry.sum_val)}")
                lines.append(f"{name}_count {_fmt_val(entry.count)}")
            else:
                for labels, val in entry.values:
                    lbl = _format_labels(labels)
                    lines.append(f"{name}{lbl} {_fmt_val(val)}")

        return "\n".join(lines) + "\n"


def _fmt_val(v: float) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if v == float("inf"):
        return "+Inf"
    if v == float("-inf"):
        return "-Inf"
    if v != v:  # NaN
        return "Nan"
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return f"{v:g}"


def _fmt_bucket(v: float) -> str:
    if v == float("inf"):
        return "+Inf"
    if v == int(v) and abs(v) < 1e15:
        return f"{int(v)}.0"
    return f"{v:g}"
