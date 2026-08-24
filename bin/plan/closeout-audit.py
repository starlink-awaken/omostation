#!/usr/bin/env python3
"""closeout-audit: agent-workflow run 与 bet 绑定的诊断/修复工具.

BET-Y1Q3-T10-08 落地 (G8 自进化债 — S1/S5/CONV-3 三次 blocked 实证).

问题: 大量 agent-workflow run 缺少 bet_id 字段, 在 closeout 时被 chain_bind 硬门
halt, 导致 closeout 流程被回避, run 状态机积累失修.

此工具:
1. 扫描所有 .omo/_delivery/agent-workflows/runs/ 下的 run
2. 诊断 unbound 状态 (按 workflow_id 和 status 分类)
3. 提供修复建议:
   - bet-execution runs: 从 objective 自动提取 bet_id (regex BET-Y?-Q?-T?-??)
   - governance-state-mutation / governance-audit: 标记为 governance-evolve (G8 豁免)
   - 其他: 标记为 manual-review (不自动改)

用法:
  python3 bin/plan/closeout-audit.py --report      # 仅报告
  python3 bin/plan/closeout-audit.py --json       # JSON 输出
  python3 bin/plan/closeout-audit.py --bind-known  # 自动绑定 (仅高置信度)
  python3 bin/plan/closeout-audit.py --bind-all    # 自动绑定 (含中等置信度)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

WS_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = WS_ROOT / ".omo" / "_delivery" / "agent-workflows" / "runs"

# G8 (T10-08) governance-evolve workflows — closeout 允许无业务 bet
GOVERNANCE_EVOLVE_WORKFLOWS = frozenset(
    {"governance-state-mutation", "governance-audit", "governance-phase-closeout"}
)

# bet_id 模式: BET-Y[1-3]Q[1-4]-T[0-9]{1,2}-[0-9]{2} 或 Y3H[12]-T[0-9]{1,2}-[0-9]{2}
BET_ID_PATTERN = re.compile(r"BET-Y\dQ\d-T\d{1,2}-\d{2}|BET-Y3H[12]-T\d{1,2}-\d{2}")
RUNS_FILE_PATTERN = re.compile(r"^(?P<ts>\d{8}T\d{6}Z)-(?P<wf>[\w-]+)-(?P<hash>[0-9a-f]{8})\.yaml$")


def _load_yaml_simple(path: Path) -> dict[str, Any]:
    """Tiny YAML reader — sufficient for run records (mostly flat)."""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        body = docs[-1] if len(docs) > 1 else docs[0]
        return body if isinstance(body, dict) else {}
    except ImportError:
        return {}


def _atomic_write_yaml(path: Path, body: dict[str, Any]) -> None:
    """Write YAML atomically (tmp + rename). Preserves formatting better than dump."""
    import yaml
    text = yaml.safe_dump(body, allow_unicode=True, sort_keys=False, default_flow_style=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _is_unbound(record: dict[str, Any]) -> bool:
    """A run is 'unbound' if it has no top-level bet_id and is not exempt."""
    wf = str(record.get("workflow_id") or "")
    if wf in GOVERNANCE_EVOLVE_WORKFLOWS:
        return False
    if str(record.get("bet_id") or "").strip():
        return False
    return True


def _extract_bet_id_from_text(text: str) -> str | None:
    """Find a BET-ID anywhere in a string. Returns first match or None."""
    m = BET_ID_PATTERN.search(text)
    return m.group(0) if m else None


def _proposed_bind(record: dict[str, Any]) -> dict[str, Any]:
    """Suggest a binding strategy for an unbound run."""
    wf = str(record.get("workflow_id") or "")
    objective = str(record.get("objective") or "")
    title = str((record.get("plan") or {}).get("title") or "")

    # Strategy 1: bet-execution runs — extract from objective
    if wf == "bet-execution":
        for src in (objective, title):
            bet_id = _extract_bet_id_from_text(src)
            if bet_id:
                return {
                    "strategy": "auto-bind-from-objective",
                    "bet_id": bet_id,
                    "source": "objective" if src == objective else "plan.title",
                    "confidence": "high",
                }
        return {
            "strategy": "manual-review",
            "reason": "bet-execution run but no BET-ID in objective/title",
            "confidence": "none",
        }

    # Strategy 2: governance workflows — exempt
    if wf in GOVERNANCE_EVOLVE_WORKFLOWS:
        return {
            "strategy": "governance-evolve-exempt",
            "reason": "G8 governance-evolve workflow, no business bet needed",
            "confidence": "high",
        }

    # Strategy 3: any BET reference in objective/plan — medium confidence
    for src in (objective, title):
        bet_id = _extract_bet_id_from_text(src)
        if bet_id:
            return {
                "strategy": "auto-bind-from-objective-medium",
                "bet_id": bet_id,
                "source": "objective" if src == objective else "plan.title",
                "confidence": "medium",
            }

    # Strategy 4: workflow name suggests bet linkage (project-code-change, etc.)
    return {
        "strategy": "manual-review",
        "reason": f"workflow {wf} has no BET-ID hint in objective/title; needs operator judgement",
        "confidence": "none",
    }


def collect_runs() -> list[dict[str, Any]]:
    """Read all run records with proposed bindings and unbound status."""
    out: list[dict[str, Any]] = []
    if not RUNS_DIR.is_dir():
        return out
    for p in sorted(RUNS_DIR.glob("*.yaml")):
        m = RUNS_FILE_PATTERN.match(p.name)
        if not m:
            continue
        record = _load_yaml_simple(p)
        unbound = _is_unbound(record)
        proposed = _proposed_bind(record) if unbound else None
        out.append({
            "path": str(p),
            "run_id": record.get("run_id") or p.stem,
            "workflow_id": record.get("workflow_id"),
            "status": record.get("status"),
            "objective": str(record.get("objective") or "")[:120],
            "has_bet_id": bool(record.get("bet_id")),
            "unbound": unbound,
            "proposed": proposed,
        })
    return out


def render_report(runs: list[dict[str, Any]]) -> str:
    total = len(runs)
    unbound = [r for r in runs if r["unbound"]]
    by_strategy: Counter[str] = Counter()
    for r in unbound:
        if r["proposed"]:
            by_strategy[r["proposed"]["strategy"]] += 1
    by_wf: Counter[str] = Counter(r["workflow_id"] for r in unbound)
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("closeout-audit: agent-workflow run 与 bet 绑定诊断")
    lines.append("=" * 72)
    lines.append(f"total_runs: {total}")
    lines.append(f"unbound:    {len(unbound)}")
    lines.append("")
    lines.append("unbound by workflow:")
    for wf, n in by_wf.most_common(10):
        lines.append(f"  {wf:<32} {n}")
    lines.append("")
    lines.append("unbound by strategy (proposed):")
    for strat, n in by_strategy.most_common():
        lines.append(f"  {strat:<40} {n}")
    lines.append("")
    if unbound:
        lines.append("first 10 unbound (sample):")
        for r in unbound[:10]:
            proposed = r["proposed"] or {}
            bet = proposed.get("bet_id", "-")
            conf = proposed.get("confidence", "-")
            strat = proposed.get("strategy", "-")
            lines.append(
                f"  [{r['status']:<8}] {r['run_id'][:40]:<40} wf={r['workflow_id']:<28} "
                f"proposed={strat} (bet={bet}, conf={conf})"
            )
    return "\n".join(lines)


def bind_known(only_high: bool = True) -> dict[str, int]:
    """Auto-bind runs based on proposed strategy.

    only_high=True: only auto-bind from bet-execution (high confidence).
    only_high=False: also bind medium-confidence runs from any workflow with
    BET-ID in objective/title.
    """
    counts = {"applied": 0, "skipped_manual": 0, "no_change": 0, "errors": 0}
    for r in collect_runs():
        if not r["unbound"]:
            counts["no_change"] += 1
            continue
        proposed = r["proposed"] or {}
        strat = proposed.get("strategy", "")
        conf = proposed.get("confidence", "none")
        bet_id = proposed.get("bet_id")
        path = Path(r["path"])
        # Decide whether to apply
        if strat == "auto-bind-from-objective":
            pass
        elif strat == "auto-bind-from-objective-medium" and not only_high:
            pass
        elif strat == "governance-evolve-exempt":
            # No bet to bind; just record status — nothing to do here.
            continue
        else:
            counts["skipped_manual"] += 1
            continue
        # Apply: load, set bet_id, write
        try:
            record = _load_yaml_simple(path)
            if not isinstance(record, dict):
                counts["errors"] += 1
                continue
            record["bet_id"] = bet_id
            _atomic_write_yaml(path, record)
            counts["applied"] += 1
        except Exception:
            counts["errors"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="closeout-audit: 诊断 + 修复 agent-workflow run 的 bet 绑定"
    )
    parser.add_argument("--report", action="store_true", help="只生成报告")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--bind-known", action="store_true", help="仅高置信度自动绑定 (bet-execution)")
    parser.add_argument("--bind-all", action="store_true", help="高 + 中置信度自动绑定")
    args = parser.parse_args()

    runs = collect_runs()

    if args.bind_known or args.bind_all:
        only_high = args.bind_known
        counts = bind_known(only_high=only_high)
        if args.json:
            print(json.dumps({"counts": counts, "total_runs": len(runs)}, ensure_ascii=False, indent=2))
        else:
            print("=" * 72)
            print(f"closeout-audit: bind (only_high={only_high})")
            print("=" * 72)
            for k, v in counts.items():
                print(f"  {k:<20} {v}")
        return 0

    if args.json:
        out = {
            "total_runs": len(runs),
            "unbound": sum(1 for r in runs if r["unbound"]),
            "runs": runs,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(render_report(runs))
    return 0


if __name__ == "__main__":
    sys.exit(main())