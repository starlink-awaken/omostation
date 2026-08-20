#!/usr/bin/env python3
"""Generate an evidence-backed three-axis attribution report.

The report is a projection, not a metrics authority.  It accepts a durable
``value-truth-snapshot/v1`` receipt and derives engineering BET counts from
the existing ledger.  Metrics without a live receipt remain explicitly
``UNPROVABLE``; constants never manufacture tokens, speedups, savings, cache
hit rates, safety results, or integrity claims.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_SCHEMA = "compound-attribution-report/v2"
VALUE_SCHEMA = "value-truth-snapshot/v1"
UNPROVEN_METRICS = (
    "parallel_acceleration_ratio",
    "local_tokens_substituted",
    "commercial_cost_saved_usd",
    "ttft_speedup_ratio",
    "chaos_interception_rate",
    "regulatory_violations",
    "merkle_integrity",
)
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _utc_now() -> str:
    # timezone.utc keeps this root CLI compatible with the deployed Python 3.9.
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")  # noqa: UP017


def _valid_value_truth(value: object) -> bool:
    if not isinstance(value, Mapping) or value.get("schema") != VALUE_SCHEMA:
        return False
    source = value.get("source")
    axes = value.get("truth_axes")
    return (
        isinstance(source, Mapping)
        and _SHA256_RE.fullmatch(str(source.get("query_digest") or "")) is not None
        and isinstance(axes, Mapping)
    )


def _load_value_truth(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not _valid_value_truth(value):
        return None
    return value


def _load_bet_summary(path: Path) -> dict[str, Any]:
    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (ImportError, OSError, ValueError):
        return {"total": 0, "by_status": {}, "status": "unprovable"}
    bets = payload.get("bets") if isinstance(payload, Mapping) else None
    if not isinstance(bets, list):
        return {"total": 0, "by_status": {}, "status": "unprovable"}
    statuses = Counter(str(item.get("status") or "unknown") for item in bets if isinstance(item, Mapping))
    return {"total": len(bets), "by_status": dict(sorted(statuses.items())), "status": "observed"}


def generate_attribution_data(
    *,
    value_truth: Mapping[str, Any] | None,
    bet_summary: Mapping[str, Any],
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Build a report from explicit evidence inputs; never infer missing data."""
    valid_value = _valid_value_truth(value_truth)
    axes = value_truth.get("truth_axes") if valid_value else None
    if not isinstance(axes, Mapping):
        axes = {}
    truth_axes = {
        "engineering_delivery": "observed" if bet_summary.get("status", "observed") == "observed" else "unprovable",
        "operational_proof": str(axes.get("operational_proof") or "unprovable"),
        "personal_value": str(axes.get("personal_value") or "unprovable"),
    }
    overall = "unprovable" if "unprovable" in truth_axes.values() else str(value_truth.get("status") or "unprovable")
    return {
        "schema": REPORT_SCHEMA,
        "status": overall,
        "observed_at": observed_at or _utc_now(),
        "truth_axes": truth_axes,
        "engineering": {
            "bets": {
                "total": int(bet_summary.get("total") or 0),
                "by_status": dict(bet_summary.get("by_status") or {}),
                "source": "repo://docs/plans/3y-bet-ledger.yaml",
            },
            "note": "BET state is engineering evidence only; it is not personal value.",
        },
        "personal_value": {
            "status": truth_axes["personal_value"],
            "source": dict(value_truth.get("source") or {}) if valid_value else None,
            "metrics": dict(value_truth.get("metrics") or {}) if valid_value else {},
        },
        "unproven_claims": {key: {"status": "unprovable", "value": None} for key in UNPROVEN_METRICS},
    }


def render_markdown_report(data: Mapping[str, Any]) -> str:
    """Render a deliberately plain report that preserves uncertainty."""
    axes = data["truth_axes"]
    bets = data["engineering"]["bets"]
    by_status = ", ".join(f"{key}={value}" for key, value in sorted(bets["by_status"].items())) or "none"
    personal = data["personal_value"]
    metrics = personal.get("metrics") or {}
    current = metrics.get("current_week_qualifying_outcomes", "UNPROVABLE")
    unproven_rows = "\n".join(
        f"| `{key}` | UNPROVABLE | no bound live receipt |" for key in sorted(data["unproven_claims"])
    )
    return f"""# 3Y 战略三轴事实归因报告

> 报告时间: {data["observed_at"]}
> 总体状态: **{data["status"]}**

## 三轴状态

- 工程交付轴: **{axes["engineering_delivery"]}**
- 运行证明轴: **{axes["operational_proof"]}**
- 个人价值轴: **{axes["personal_value"]}**

三轴互不自动晋升。PR、测试与 BET 状态不能代替真实人类 Outcome。

## 工程事实

- BET 总数: {bets["total"]}
- 状态分布: {by_status}
- 来源: `{bets["source"]}`

## 个人价值事实

- 当前周合格 Outcome: {current}
- 四周价值门: **{metrics.get("four_week_value_gate", "UNPROVABLE")}**
- 查询回执: `{(personal.get("source") or {}).get("query_digest", "UNPROVABLE")}`

## 未证明指标

| 指标 | 状态 | 原因 |
|---|---|---|
{unproven_rows}

只有绑定实时来源、观测窗口和查询摘要的后续 receipt 才能替换这些
`UNPROVABLE` 项；本报告不会从常量构造成功。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--value-truth-receipt", type=Path)
    parser.add_argument(
        "--bet-ledger",
        type=Path,
        default=REPO_ROOT / "docs" / "plans" / "3y-bet-ledger.yaml",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "docs" / "reports" / "2026-compound-attribution-report.md",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = generate_attribution_data(
        value_truth=_load_value_truth(args.value_truth_receipt),
        bet_summary=_load_bet_summary(args.bet_ledger),
    )
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_markdown_report(data), encoding="utf-8")
        print(f"attribution report generated: {args.output}")
    return 2 if data["status"] == "unprovable" else 0


if __name__ == "__main__":
    raise SystemExit(main())
