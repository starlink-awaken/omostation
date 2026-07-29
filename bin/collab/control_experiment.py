#!/usr/bin/env python3
"""P84 K4 对照实验 harness — 协作并行 vs 单 agent 顺序 (能力轨, 场景库).

批次定义 (strat-p84 W2.3 / K4):
- batch3: 有冲突任务 (A_conflict 场景)
- batch4: 失败注入 (B_failure_injection 场景)

度量: 墙钟 / pass 率 / silent_loss / 加速比.
协作 = ThreadPool 并行跑场景子集; 单 agent = 顺序同一集合.

🔴 协作劣于单 → 如实记录 (P84 §F), 不掩盖.
🔴 构造场景只计能力轨.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bin" / "collab"))
from scenario_lib import load_scenario, run_scenario  # noqa: E402

SCN_DIR = REPO / ".omo" / "_delivery" / "collab-scenarios"


@dataclass
class ModeResult:
    mode: str
    wall_s: float
    n_scenarios: int
    n_passed: int
    silent_loss_total: int
    scenario_ids: list[str]


def _select_paths(batch: str) -> list[Path]:
    """按批次选场景 (能力轨构造场景, 合规)."""
    paths = sorted(SCN_DIR.glob("*.yaml"))
    out: list[Path] = []
    for p in paths:
        sc = load_scenario(p)
        cat = sc.get("category", "")
        if batch == "batch3":
            # 有冲突: A 类 + 手写 ADV 冲突/认领/串通
            if cat == "A_conflict" or p.name.startswith(
                ("ADV07", "ADV11", "ADV13", "A01")
            ):
                out.append(p)
        elif batch == "batch4":
            if cat == "B_failure_injection" or p.name.startswith(
                ("ADV09", "ADV17", "B01")
            ):
                out.append(p)
        else:
            raise ValueError(f"unknown batch: {batch}")
    # 去重保序
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        if p.name not in seen:
            seen.add(p.name)
            uniq.append(p)
    return uniq


def _run_one(path: Path) -> dict:
    sc = load_scenario(path)
    r = run_scenario(sc)
    return {
        "id": sc["id"],
        "passed": r.passed,
        "silent_loss": r.silent_loss,
        "events": len(r.events),
    }


def run_sequential(paths: list[Path]) -> ModeResult:
    t0 = time.perf_counter()
    results = [_run_one(p) for p in paths]
    wall = time.perf_counter() - t0
    return ModeResult(
        mode="single_agent_sequential",
        wall_s=round(wall, 4),
        n_scenarios=len(results),
        n_passed=sum(1 for r in results if r["passed"]),
        silent_loss_total=sum(r["silent_loss"] for r in results),
        scenario_ids=[r["id"] for r in results],
    )


def run_parallel(paths: list[Path], workers: int) -> ModeResult:
    t0 = time.perf_counter()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_run_one, p): p for p in paths}
        for fut in as_completed(futs):
            results.append(fut.result())
    wall = time.perf_counter() - t0
    # 稳定顺序 for ids
    order = {p.stem: i for i, p in enumerate(paths)}
    results.sort(key=lambda r: order.get(r["id"].split("/")[-1], 0))
    return ModeResult(
        mode="collab_parallel",
        wall_s=round(wall, 4),
        n_scenarios=len(results),
        n_passed=sum(1 for r in results if r["passed"]),
        silent_loss_total=sum(r["silent_loss"] for r in results),
        scenario_ids=[r["id"] for r in results],
    )


def compare(batch: str, workers: int = 4) -> dict:
    paths = _select_paths(batch)
    if not paths:
        raise SystemExit(f"no scenarios for {batch} under {SCN_DIR}")
    single = run_sequential(paths)
    collab = run_parallel(paths, workers=min(workers, len(paths)))
    speedup = (
        round(single.wall_s / collab.wall_s, 3) if collab.wall_s > 0 else None
    )
    collab_better = collab.wall_s < single.wall_s
    verdict = "collab_better" if collab_better else "collab_worse_or_tie"
    return {
        "batch": batch,
        "n_paths": len(paths),
        "paths": [p.name for p in paths],
        "single": asdict(single),
        "collab": asdict(collab),
        "speedup_single_over_collab": speedup,  # >1 = 单更快; <1 = 协作更快
        "speedup_collab_over_single": (
            round(single.wall_s / collab.wall_s, 3) if collab.wall_s else None
        ),
        "collab_wall_better": collab_better,
        "verdict": verdict,
        "silent_loss_ok": single.silent_loss_total == 0
        and collab.silent_loss_total == 0,
        "pass_rate_single": round(single.n_passed / max(single.n_scenarios, 1), 3),
        "pass_rate_collab": round(collab.n_passed / max(collab.n_scenarios, 1), 3),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P84 K4 control experiment")
    ap.add_argument(
        "--batch",
        choices=("batch3", "batch4", "both"),
        default="both",
    )
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--md-out", type=Path, default=None)
    args = ap.parse_args(argv)

    batches = ["batch3", "batch4"] if args.batch == "both" else [args.batch]
    reports = [compare(b, workers=args.workers) for b in batches]

    # 跑 3 次取中位墙钟, 降抖动 (可复现对照)
    for i, b in enumerate(batches):
        walls_s, walls_c = [], []
        for _ in range(3):
            r = compare(b, workers=args.workers)
            walls_s.append(r["single"]["wall_s"])
            walls_c.append(r["collab"]["wall_s"])
        walls_s.sort()
        walls_c.sort()
        mid_s, mid_c = walls_s[1], walls_c[1]
        reports[i]["single"]["wall_s_median3"] = mid_s
        reports[i]["collab"]["wall_s_median3"] = mid_c
        reports[i]["speedup_collab_over_single_median3"] = (
            round(mid_s / mid_c, 3) if mid_c > 0 else None
        )
        reports[i]["collab_wall_better_median3"] = mid_c < mid_s
        reports[i]["verdict_median3"] = (
            "collab_better" if mid_c < mid_s else "collab_worse_or_tie"
        )

    payload = {"experiments": reports, "schema": "p84-k4-control-v1"}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")

    if args.md_out:
        lines = [
            "---",
            "status: active",
            "lifecycle: audit",
            "owner: governance-team",
            "last-reviewed: 2026-07-28",
            "---",
            "# P84 K4 批次3/4 对照实验（冲突 / 失败注入）",
            "",
            "> 上位: strat-p84 W2.3 · ADR-0253 路由表 · K4 泛化验证",
            "> 🔴 红线: 协作劣如实上报 (P84 §F); 场景只计能力轨",
            "",
            "## 方法",
            "- **协作**: ThreadPool 并行跑场景子集 (模拟多 worker 并行能力轨任务)",
            "- **单 agent**: 同集合顺序跑",
            "- 墙钟取 **3 次中位** 降抖动; 质量 = pass 率 + silent_loss",
            "",
        ]
        for r in reports:
            b = r["batch"]
            title = "批次3 有冲突 (A_conflict)" if b == "batch3" else "批次4 失败注入 (B_failure)"
            better = r.get("collab_wall_better_median3")
            flag = "✅ 协作优" if better else "🔴 协作劣/平"
            lines += [
                f"## {title}",
                "",
                f"| 模式 | 墙钟中位 (s) | pass | silent_loss |",
                f"|------|-------------|------|-------------|",
                f"| 协作并行 | {r['collab'].get('wall_s_median3')} | "
                f"{r['collab']['n_passed']}/{r['collab']['n_scenarios']} | "
                f"{r['collab']['silent_loss_total']} |",
                f"| 单 agent 顺序 | {r['single'].get('wall_s_median3')} | "
                f"{r['single']['n_passed']}/{r['single']['n_scenarios']} | "
                f"{r['single']['silent_loss_total']} |",
                "",
                f"- 加速比 T_single/T_collab ( **>1 协作更快** ): "
                f"**{r.get('speedup_collab_over_single_median3')}**",
                f"- 判定: **{flag}** (`{r.get('verdict_median3')}`)",
                f"- 场景数: {r['n_paths']} (silent_loss 硬红线 ok={r['silent_loss_ok']})",
                "",
            ]
        # 综合
        b3 = next(x for x in reports if x["batch"] == "batch3")
        b4 = next((x for x in reports if x["batch"] == "batch4"), None)
        lines += [
            "## 综合 (对照 ADR-0253 路由表)",
            "",
            "| 批次 | 任务类型 | 协作 vs 单 | 与路由表一致性 |",
            "|------|---------|-----------|----------------|",
        ]
        b3_better = b3.get("collab_wall_better_median3")
        lines.append(
            f"| 3 冲突 | 有冲突/双写 | "
            f"{'协作优' if b3_better else '协作劣/平'} | "
            f"{'需修订路由' if b3_better else '符合: 冲突类偏单/串行或机制内处理'} |"
        )
        if b4:
            b4_better = b4.get("collab_wall_better_median3")
            lines.append(
                f"| 4 失败注入 | 超时/失败 | "
                f"{'协作优' if b4_better else '协作劣/平'} | "
                f"{'协作容错并行有收益' if b4_better else '符合: 失败路径未必并行受益'} |"
            )
        lines += [
            "",
            "## 诚实记录",
            "",
        ]
        for r in reports:
            if not r.get("collab_wall_better_median3"):
                lines.append(
                    f"- 🔴 **{r['batch']} 协作劣/平**: 中位墙钟协作 "
                    f"{r['collab'].get('wall_s_median3')}s ≥ 单 "
                    f"{r['single'].get('wall_s_median3')}s — 不掩盖"
                )
            else:
                lines.append(
                    f"- ✅ **{r['batch']} 协作优**: 加速比 "
                    f"{r.get('speedup_collab_over_single_median3')}"
                )
        lines += [
            "",
            "## 对 ADR-0253 的 implication",
            "",
            "- 独立并行批量: 仍优先协作 (batch5 等量墙钟; 5.4x 已作废)",
            "- 冲突/失败注入: 本 harness 验证 **墙钟并行收益**; 机制正确性已由 ADR-0254 检测器覆盖",
            "- 路由表维持: 简单分析→单; 独立批量→协作; 冲突/失败→先机制检测再决定是否并行 fan-out",
            "",
        ]
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {args.md_out}", file=sys.stderr)

    # exit 0 always (experiment is measurement, not gate); silent_loss violation → 1
    if any(not r["silent_loss_ok"] for r in reports):
        print("SILENT_LOSS_VIOLATION", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
