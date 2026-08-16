"""Pattern Learner — 从行为数据中学习周期性模式

从 Iris 连接器数据 (OpenHuman/微信) 中:
  - 检测每日固定时间出现的事件 (如: 每天9:00 有邮件)
  - 检测每周固定日期出现的事件 (如: 每周五下班前填周报)
  - 输出 Pattern → ops_event
"""

import json
import os
import subprocess
import textwrap
from collections import Counter
from datetime import datetime


class Pattern:
    def __init__(self, pattern_type: str, confidence: float, description: str, suggestion: str = ""):
        self.type = pattern_type  # "daily" | "weekly" | "weekday"
        self.confidence = confidence
        self.description = description
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "confidence": round(self.confidence, 2),
            "description": self.description,
            "suggestion": self.suggestion,
        }


class PatternLearner:
    def __init__(self) -> None:
        self.patterns: list[Pattern] = []

    def learn_from_iris(self, iris_data: list[dict]) -> list[dict]:
        """Analyze timestamped events to find patterns"""
        if not iris_data:
            return []

        # Extract hours and weekdays from timestamps
        hour_counts: Counter[int] = Counter()
        weekday_counts: Counter[int] = Counter()

        for entry in iris_data:
            ts = entry.get("time", entry.get("timestamp", ""))
            try:
                dt: datetime | None = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                assert dt is not None
                hour_counts[dt.hour] += 1
                weekday_counts[dt.weekday()] += 1
                dt = None
            except Exception:
                pass

        # Detect daily patterns (same hour, repeated daily)
        total = sum(hour_counts.values())
        if total > 0:
            peak_hour = hour_counts.most_common(1)[0]
            if peak_hour[1] / max(total, 1) > 0.2:  # 20%+ events at this hour
                self.patterns.append(
                    Pattern(
                        "daily",
                        peak_hour[1] / max(total, 1),
                        f"Peak activity at {peak_hour[0]}:00 ({peak_hour[1]} events)",
                        f"Consider scheduling tasks around {peak_hour[0]}:00",
                    )
                )

        # Detect weekly patterns
        if sum(weekday_counts.values()) > 0:
            peak_day = weekday_counts.most_common(1)[0]
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            if peak_day[1] / max(sum(weekday_counts.values()), 1) > 0.2:
                self.patterns.append(
                    Pattern(
                        "weekly",
                        peak_day[1] / max(sum(weekday_counts.values()), 1),
                        f"Peak activity on {days[peak_day[0]]} ({peak_day[1]} events)",
                        f"Consider prepping on {days[peak_day[0] - 1] if peak_day[0] > 0 else 'Sun'}",
                    )
                )

        return [p.to_dict() for p in self.patterns]

    def simulate(self) -> list[dict]:
        """Generate sample patterns for testing without Iris connector"""
        sample_data = []
        for i in range(14):
            for h in [9, 10, 14, 15]:
                sample_data.append({"time": f"2026-05-{14 + i // 2:02d}T{h:02d}:00:00", "source": "simulated"})
        return self.learn_from_iris(sample_data)

    def emit_to_ops(self, patterns: list[dict]) -> None:
        """Send patterns to hermes-ops as MCP events"""
        hermes_src = os.path.expanduser("~/Workspace/ops/src")
        for p in patterns:
            try:
                script = textwrap.dedent("""\
                    import sys, json, os
                    sys.path.insert(0, os.environ["HERMES_SRC"])
                    from hermes_ops.events import emit
                    emit("PATTERN_DETECTED", json.loads(os.environ["PATTERN_PAYLOAD"]))
                """)
                subprocess.run(
                    ["python3", "-c", script],
                    env={**os.environ, "HERMES_SRC": hermes_src, "PATTERN_PAYLOAD": json.dumps(p)},
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass
