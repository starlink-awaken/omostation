#!/usr/bin/env python3
"""P71 R3: 维度权重动态调整 (简化版).

读 .omo/_log/readiness-snapshots.jsonl (P70 持久化), 分析 5 维度变化模式:
- 各维度波动率 (stdev)
- 各维度与总分相关系数
- 异常时段各维度贡献度

输出: 建议权重 (基于历史相关性动态调整)
- 默认: 25/20/20/20/15 (P60)
- P71: 基于历史调整, 高相关维度权重 ↑, 低相关 ↓

使用:
  python3 bin/dim-weight.py
  python3 bin/dim-weight.py --json
  python3 bin/dim-weight.py --reset  # 强制使用默认权重
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_WEIGHTS = {"frontmatter": 25, "drift_low": 20, "commit_closure": 20, "adr_index": 20, "governance_score": 15}


def load_snapshots(root: Path) -> list[dict]:
    """读持久化快照."""
    log = root / ".omo" / "_log" / "readiness-snapshots.jsonl"
    if not log.exists():
        # fallback: readiness-*.json
        log_dir = root / ".omo" / "_log"
        snaps = []
        for f in sorted(log_dir.glob("readiness-*.json"), reverse=True)[:30]:
            try:
                with open(f, encoding="utf-8") as fh:
                    snaps.append(json.load(fh))
            except Exception:
                pass
        return list(reversed(snaps))
    snaps = []
    try:
        with open(log, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    snaps.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return snaps


def compute_weights(snaps):
    """基于历史快照反推各维度权重.

    返回 (weights, analysis) 元组.
    """
    if len(snaps) < 5:
        return DEFAULT_WEIGHTS, "样本不足 (<5), 使用默认权重"

    # 收集各维度时序
    dim_series: dict[str, list[float]] = {
        "frontmatter": [], "drift_low": [], "commit_closure": [], "adr_index": [], "governance_score": []
    }
    total_series = []

    for snap in snaps:
        dims = snap.get("dimensions", {})
        for dim in dim_series:
            val = dims.get(dim, {}).get("score")
            if val is not None:
                dim_series[dim].append(float(val))
        # 总分
        score = snap.get("score")
        if score is not None:
            total_series.append(float(score))

    if not total_series or len(total_series) < 5:
        return DEFAULT_WEIGHTS, "样本不足, 使用默认权重"

    # 计算各维度 stdev 和与总分相关性
    import statistics
    weights = {}
    analysis = {}
    total_weight = sum(DEFAULT_WEIGHTS.values())

    for dim, series in dim_series.items():
        if not series or len(series) < 2:
            weights[dim] = DEFAULT_WEIGHTS.get(dim, 20)
            continue
        # stdev
        stdev = statistics.stdev(series) if len(series) > 1 else 0
        # 简单相关性: 维度变化时总分变化 (按 |delta dim| * |delta total| 求和)
        cov = 0.0
        cnt = 0
        for i in range(1, min(len(series), len(total_series))):
            d_dim = abs(series[i] - series[i-1])
            d_total = abs(total_series[i] - total_series[i-1])
            cov += d_dim * d_total
            cnt += 1
        correlation = cov / cnt if cnt > 0 else 0

        # 综合: 相关性 * 波动率
        score = correlation * (1 + stdev)
        analysis[dim] = {"stdev": round(stdev, 3), "correlation": round(correlation, 3), "score": round(score, 3)}
        weights[dim] = score

    # 归一化
    total_score = sum(weights.values())
    if total_score > 0:
        for dim in weights:
            weights[dim] = round(weights[dim] / total_score * total_weight)

    return weights, analysis


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P71: 维度权重动态调整 (基于历史快照反推)"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--reset", action="store_true", help="强制使用默认权重")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    if args.reset:
        weights = DEFAULT_WEIGHTS
        analysis = {"note": "reset to default"}
    else:
        snaps = load_snapshots(root)
        weights, analysis = compute_weights(snaps)
        if isinstance(analysis, str):
            analysis = {"note": analysis}

    if args.format == "json":
        out = {"weights": weights, "default_weights": DEFAULT_WEIGHTS, "analysis": analysis}
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("⚖️  P71 维度权重动态调整 (基于历史)")
        print("=" * 60)
        print()
        print(f"📁 快照数: {analysis.get('note', 'N/A')}")
        print()
        print(f"{'维度':<22s}{'当前':<8s}{'默认':<8s}{'变化':<10s}")
        print("-" * 60)
        for dim, default in DEFAULT_WEIGHTS.items():
            current = weights.get(dim, default)
            change = current - default
            arrow = "↑" if change > 0 else ("↓" if change < 0 else "=")
            print(f"  {dim:<22s}{current:<8d}{default:<8d}{arrow}{abs(change):<5d}")
        print()
        if "note" not in analysis:
            print("--- 各维度分析 ---")
            for dim, info in analysis.items():
                print(f"  {dim}: stdev={info['stdev']} correlation={info['correlation']} score={info['score']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())