#!/usr/bin/env python3
"""health-predict.py — 提前 7 天预测 ledger drift (B1.3).

基于当前 health.yaml 快照 + retro file drift + ledger 状态,
启发式预测 7 天后的 5 个核心健康维度 (drift / staleness / freshness /
alignment / governance), 输出 RED/YELLOW/GREEN 风险等级 + 建议动作.

设计要点:
  - 不依赖 ML 模型, 纯规则 (P97, F60)
  - 不依赖历史快照 (workspace 只有当前快照)
  - 预测基线 = 当前值 + 启发式趋势 (B1.3 mock 模式可用 --simulate-now <date>)
  - 与 auto-fix-loop 协同: 复用其 FRONTMATTER-MISSING-FIELD / INVALID-METADATA drift 计数

用法:
  python3 bin/ssot/health-predict.py [--horizon-days 7] [--json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
HEALTH = WORKSPACE / ".omo" / "state" / "health.yaml"


def load_health_snapshot() -> dict:
    """简易 YAML 解析: 读 health.yaml 顶层 + 已知 nested 段."""
    if not HEALTH.exists():
        return {}
    out: dict = {}
    in_alignment_detail = False
    for line in HEALTH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("-"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        # 顶层 key
        if not line.startswith(" "):
            if key in {
                "health_score",
                "governance_anomaly_score",
                "freshness_score",
                "drift_score",
                "staleness_score",
                "alignment_score",
            }:
                try:
                    out[key] = float(value)
                except ValueError:
                    pass
    return out


def count_retro_drift() -> dict[str, int]:
    """复用 auto-fix-loop 的 drift 计数 (FRONTMATTER-MISSING-FIELD + INVALID-METADATA on retro).

    强制 SKIP_FIX_LOOP_BRANCH=1, 让 closeout-skip 路径生效, 才能在非 closeout 分支也看到
    retro 漂移计数 (否则 auto-fix-loop 只输出 actionable 漂移).
    """
    env = {"SKIP_FIX_LOOP_BRANCH": "1", "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
    import os

    result = subprocess.run(
        [
            sys.executable,
            str(WORKSPACE / "bin" / "gac" / "auto-fix-loop.py"),
            "--json",
        ],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env={**os.environ, **env},
    )
    counts: dict[str, int] = {"retro_invalid": 0, "retro_missing_field": 0}
    if result.returncode not in (0, 1):
        return counts
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return counts
    for d in parsed.get("drifts", []):
        kind = d.get("kind", "")
        msg = d.get("message", "")
        import re

        n_match = re.search(r"(\d+)\s*个", msg)
        n = int(n_match.group(1)) if n_match else 0
        if kind == "INVALID-METADATA-RETRO-SKIPPED":
            counts["retro_invalid"] = max(counts["retro_invalid"], n)
        elif kind == "FRONTMATTER-MISSING-FIELD-RETRO-SKIPPED":
            counts["retro_missing_field"] = max(counts["retro_missing_field"], n)
    return counts


def predict_horizon(current: dict, retro: dict[str, int], horizon_days: int) -> dict:
    """启发式预测 horizon 天后的健康维度.

    规则:
      - drift_score: 当前值 + retro_invalid * 0.5 (每 retro 文件上修 -0.5分, 累加).
        7 天假设 retro 数量 = 当前数 × (1 + horizon/30) 没问题.
      - staleness_score: 每天 -0.05 (回顾 frontmatter 拉取率), 7 天 = -0.35
      - freshness_score: 每天 -0.05 (commit 衰减), 7 天 = -0.35
      - alignment_score: retro 增长会扩大 spread, 每 retro 文件 +0.05
      - governance_score: 稳定, 不预测
    """
    drift_now = current.get("drift_score", 0)
    stale_now = current.get("staleness_score", 100)
    fresh_now = current.get("freshness_score", 100)
    align_now = current.get("alignment_score", 100)

    retro_invalid = retro.get("retro_invalid", 0)
    retro_missing_field = retro.get("retro_missing_field", 0)
    retro_total = retro_invalid + retro_missing_field

    factor = horizon_days / 30.0  # scale to 30 days

    drift_7d = drift_now + retro_total * 0.5 * factor
    stale_7d = max(0, stale_now - 0.05 * horizon_days)
    fresh_7d = max(0, fresh_now - 0.05 * horizon_days)
    align_7d = max(0, align_now - retro_total * 0.05 * factor)

    def band(score: float, kind: str = "score") -> str:
        if kind == "drift":
            # drift_score 低 = 好 (高 = 多 drift)
            if score < 5:
                return "GREEN"
            if score < 20:
                return "YELLOW"
            return "RED"
        # 其他: 高 = 好
        if score >= 80:
            return "GREEN"
        if score >= 50:
            return "YELLOW"
        return "RED"

    return {
        "drift": {
            "now": drift_now,
            "predicted_7d": round(drift_7d, 1),
            "delta": round(drift_7d - drift_now, 1),
            "band_now": band(drift_now, "drift"),
            "band_predicted": band(drift_7d, "drift"),
        },
        "staleness": {
            "now": stale_now,
            "predicted_7d": round(stale_7d, 1),
            "delta": round(stale_7d - stale_now, 1),
            "band_now": band(stale_now),
            "band_predicted": band(stale_7d),
        },
        "freshness": {
            "now": fresh_now,
            "predicted_7d": round(fresh_7d, 1),
            "delta": round(fresh_7d - fresh_now, 1),
            "band_now": band(fresh_now),
            "band_predicted": band(fresh_7d),
        },
        "alignment": {
            "now": align_now,
            "predicted_7d": round(align_7d, 1),
            "delta": round(align_7d - align_now, 1),
            "band_now": band(align_now),
            "band_predicted": band(align_7d),
        },
    }


def recommend_actions(prediction: dict) -> list[str]:
    """根据预测结果给动作建议."""
    actions: list[str] = []
    for dim, vals in prediction.items():
        if vals["band_now"] == "GREEN" and vals["band_predicted"] == "GREEN":
            continue
        if vals["band_predicted"] == "RED":
            actions.append(
                f"[RED] {dim}: 当前 {vals['now']} → 7d 后 {vals['predicted_7d']} "
                f"(Δ {vals['delta']:+}). 建议: 立即批量 fix."
            )
        elif vals["band_predicted"] == "YELLOW":
            actions.append(
                f"[YELLOW] {dim}: 当前 {vals['now']} → 7d 后 {vals['predicted_7d']} "
                f"(Δ {vals['delta']:+}). 建议: 本周内处理."
            )
    return actions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--horizon-days", type=int, default=7,
                    help="预测窗口天数 (默认 7)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    current = load_health_snapshot()
    if not current:
        print("⚠️ health.yaml 不存在或无有效字段")
        return 1

    retro = count_retro_drift()
    prediction = predict_horizon(current, retro, args.horizon_days)
    actions = recommend_actions(prediction)

    payload = {
        "horizon_days": args.horizon_days,
        "snapshot_at": datetime.now(UTC).isoformat(),
        "retro_drift": retro,
        "current_scores": current,
        "prediction": prediction,
        "actions": actions,
        "summary": {
            "red_count": sum(
                1
                for v in prediction.values()
                if v["band_predicted"] == "RED"
            ),
            "yellow_count": sum(
                1
                for v in prediction.values()
                if v["band_predicted"] == "YELLOW"
            ),
            "green_count": sum(
                1
                for v in prediction.values()
                if v["band_predicted"] == "GREEN"
            ),
        },
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"━━━ health-predict (horizon {args.horizon_days}d) ━━━\n")
        for name_d, vals in prediction.items():
            arrow = (
                "↑"
                if vals["delta"] > 0
                else "↓"
                if vals["delta"] < 0
                else "→"
            )
            print(
                f"  {name_d:12} {vals['now']:>6.1f} {arrow} {vals['predicted_7d']:>6.1f}  "
                f"[{vals['band_now']} → {vals['band_predicted']}]"
            )
        print()
        if actions:
            print("建议:")
            for a in actions:
                print(f"  • {a}")
        else:
            print("✅ 无需立即处理 — 7 天预测全 GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())