#!/usr/bin/env python3
"""BET-Y1Q3-T3-01: MOS 双栈一致性观察器.

同一 query 分别经 MOS (mos package recall) 与旧双栈 (KOS search via cockpit
`search` 命令) 检索, 对比结果集一致性 (Jaccard 相似度 ≥ 99% 目标, 连续 8 周).

用法:
  python3 bin/ssot/mos-dual-stack-consistency.py                    # 跑一次并落盘
  python3 bin/ssot/mos-dual-stack-consistency.py --json             # 输出 JSON
  python3 bin/ssot/mos-dual-stack-consistency.py --query "关键词"    # 指定 query
  python3 bin/ssot/mos-dual-stack-consistency.py --weekly          # 生成周报 (含 8 周滚动)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

# 周报落盘目录
AUDITS_DIR = WORKSPACE_ROOT / ".omo" / "_knowledge" / "audits"
REPORT_DIR = AUDITS_DIR / "mos-dual-stack-consistency"

# 默认 query 集 (从 knowledge 检索场景抽样, 覆盖多领域)
DEFAULT_QUERIES = [
    "借调政策",
    "Memory OS",
    "治理规则",
    "债务管理",
    "工作流",
    "知识检索",
    "Agent 协作",
    "决策记录",
]

# 一致性目标
TARGET_SIMILARITY = 0.99


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _week_tag() -> str:
    now = datetime.now(UTC)
    # ISO 周号
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _run_mos_recall(query: str) -> dict:
    """调 MOS recall via cockpit memory CLI (--json)."""
    proc = subprocess.run(
        [
            "uv", "run", "--project", str(WORKSPACE_ROOT / "projects/cockpit"),
            "python", "-m", "cockpit.cli", "memory", "recall", query, "--json",
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        cwd=WORKSPACE_ROOT,
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "error": proc.stdout[-200:] or proc.stderr[-200:], "hits": []}
    hits = payload.get("hits") or []
    return {
        "ok": payload.get("ok", True),
        "count": payload.get("count", len(hits)),
        "ids": sorted(str(h.get("id", "")) for h in hits if h.get("id")),
        "backend": payload.get("backend_status", {}),
    }


def _run_kos_search(query: str) -> dict:
    """调 KOS search via cockpit `search` 命令 (降级路径, 返回结果标题/来源)."""
    proc = subprocess.run(
        [
            "uv", "run", "--project", str(WORKSPACE_ROOT / "projects/cockpit"),
            "python", "-m", "cockpit.cli", "search", query,
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        cwd=WORKSPACE_ROOT,
    )
    out = proc.stdout or ""
    ids: list[str] = []
    skip_prefixes = ("⚠", "·", "提示", "query:", "zone:", "📚", "┌", "└", "│")
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith(skip_prefixes):
            continue
        ids.append(line)
    return {"ok": proc.returncode == 0 or bool(ids), "count": len(ids), "ids": sorted(set(ids))}


def _jaccard(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0  # both empty → consistent
    sa, sb = set(a), set(b)
    inter, union = len(sa & sb), len(sa | sb)
    return inter / union if union else 1.0


def _compare_one(query: str) -> dict:
    mos = _run_mos_recall(query)
    kos = _run_kos_search(query)
    similarity = _jaccard(mos["ids"], kos["ids"])
    return {
        "query": query,
        "mos_count": mos["count"],
        "kos_count": kos["count"],
        "jaccard": round(similarity, 4),
        "consistent": similarity >= TARGET_SIMILARITY,
        "mos_ids": mos["ids"][:10],
        "kos_ids": kos["ids"][:10],
        "mos_error": mos.get("error"),
        "backend": mos.get("backend", {}),
    }


def _run_all(queries: list[str]) -> dict:
    results = [_compare_one(q) for q in queries]
    consistent = sum(1 for r in results if r["consistent"])
    return {
        "schema": "mos-dual-stack-consistency/v1",
        "week": _week_tag(),
        "observed_at": _now(),
        "queries_count": len(results),
        "consistent_count": consistent,
        "consistency_ratio": round(consistent / len(results), 4) if results else 1.0,
        "target": TARGET_SIMILARITY,
        "results": results,
    }


def _write_report(report: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{report['week']}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _render_weekly(history: list[dict]) -> str:
    lines = [
        f"# MOS 双栈一致性周报 ({_week_tag()})",
        "",
        f"- 观察期: 8 周 (目标一致性 ≥ {TARGET_SIMILARITY:.0%})",
        f"- 本轮 queries: {len(history[-1]['results'])} 条",
        f"- 本轮一致性: {history[-1]['consistency_ratio']:.2%} ({history[-1]['consistent_count']}/{history[-1]['queries_count']})",
        "",
        "## 8 周滚动",
        "",
        "| 周 | 一致性 | 结果 |",
        "|---|---|---|",
    ]
    for h in history:
        ok = "✅" if h["consistency_ratio"] >= TARGET_SIMILARITY else "❌"
        lines.append(f"| {h['week']} | {h['consistency_ratio']:.2%} | {ok} |")
    lines.append("")
    lines.append("> 本场景产出永不记入价值指标 (BET-Y1Q3-T3-01 non_goals)")
    lines.append("")
    return "\n".join(lines)


def _load_history() -> list[dict]:
    if not REPORT_DIR.exists():
        return []
    history = []
    for p in sorted(REPORT_DIR.glob("*.json")):
        try:
            history.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            # 跳过损坏的历史周报, 不影响当前观察
            continue
    return history


def main() -> int:
    ap = argparse.ArgumentParser(description="MOS 双栈一致性观察器 (BET-Y1Q3-T3-01)")
    ap.add_argument("--query", action="append", default=[], help="指定 query (可多次)")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--weekly", action="store_true", help="生成周报 (含 8 周滚动)")
    ap.add_argument("--dry-run", action="store_true", help="不落盘")
    args = ap.parse_args()

    queries = args.query or DEFAULT_QUERIES
    report = _run_all(queries)
    if not args.dry_run:
        _write_report(report)
    history = _load_history()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.weekly:
        print(_render_weekly(history))
        return 0

    print(f"MOS 双栈一致性 ({report['week']}):")
    print(f"  一致性: {report['consistency_ratio']:.2%} ({report['consistent_count']}/{report['queries_count']})")
    for r in report["results"]:
        mark = "✅" if r["consistent"] else "❌"
        print(f"  {mark} {r['query']}: Jaccard={r['jaccard']:.3f} (MOS={r['mos_count']} KOS={r['kos_count']})")
    if not args.dry_run:
        print(f"\n  报告已落盘: {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
