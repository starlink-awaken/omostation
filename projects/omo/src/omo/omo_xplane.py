#!/usr/bin/env python3
"""OMO X-Plane — X 轴治理控制面探活聚合器。

读 protocols/x-axis-registry.yaml,对每个机制执行 probe,输出 X1-X4 真实存活状态,
并把结果折算成 xplane_factor 供 health_score 接入(档位②)。

核心理念:probe 回答的是"机制真的在运行吗"(alive),不是"代码是否存在"。
  - status=DEAD  专治声明/现实分裂:注册表/文档说有,探针探不到活动证据。
  - 两个正交指标(Law of Prudence / Anti-Optimism,不混为一谈):
      存活率 survival = green / probed   —— 只评判"探到的"机制,接入 health。
      覆盖率 coverage = probed / total   —— X 轴可观测性,PENDING 多则低,单独按债务追踪。
    不拿 PENDING(未实现探针)当"死亡"去砸 health 分。

对应设计: .omo/_knowledge/management/x-plane-architecture-design-v1.md §4-§7
注册表:   protocols/x-axis-registry.yaml
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# ── status 常量 ──
GREEN = "GREEN"      # 活且新鲜
YELLOW = "YELLOW"    # 活但接近 SLA 边界
RED = "RED"          # 探活失败/报错(机制坏了)
DEAD = "DEAD"        # 声明存在但无活动证据(声明/现实分裂)
PENDING = "PENDING"  # runner 待实现,未探活(不计入存活率分母)

_ICON = {GREEN: "✅", YELLOW: "🟡", RED: "❌", DEAD: "💀", PENDING: "⏳"}
_ANSI = {GREEN: "32", YELLOW: "33", RED: "31", DEAD: "31", PENDING: "90"}

# X 轴对 health_score 的过渡权重。xplane_factor = 1 - W*(1 - xplane_score/100)。
# 初期 0.3(X 轴尚薄,留缓冲不卡 Phase gate),随探活覆盖率提升可调高至 0.5。
W_XPLANE = 0.3


@dataclass
class ProbeResult:
    mechanism_id: str
    axis: str
    name: str
    status: str
    detail: str = ""


def _color(text: str, status: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{_ANSI.get(status, '0')}m{text}\033[0m"


def _find_registry() -> Path | None:
    """向上爬找 protocols/x-axis-registry.yaml,兼容任意 cwd。"""
    env = os.environ.get("WORKSPACE_ROOT")
    if env:
        p = Path(env) / "protocols" / "x-axis-registry.yaml"
        if p.exists():
            return p
    for parent in Path(__file__).resolve().parents:
        cand = parent / "protocols" / "x-axis-registry.yaml"
        if cand.exists():
            return cand
    cand = Path.cwd() / "protocols" / "x-axis-registry.yaml"
    return cand if cand.exists() else None


def _last_nonempty_line(path: Path, blocksize: int = 8192) -> str:
    """从文件尾部高效读最后一条非空行(不整读大文件,39M 也秒回)。"""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        if size == 0:
            return ""
        f.seek(max(0, size - blocksize))
        data = f.read().decode("utf-8", "replace")
    lines = [ln for ln in data.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _parse_ts(line: str) -> datetime | None:
    """从一条 JSONL 记录里抠时间戳(兼容 ts / timestamp / time,处理 Z 后缀)。"""
    try:
        rec = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    raw = rec.get("ts") or rec.get("timestamp") or rec.get("time")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _probe_jsonl_freshness(m: dict) -> ProbeResult:
    """jsonl_freshness 探针:读文件尾行时间戳判新鲜度。"""
    probe, sla = m["probe"], m.get("sla", {})
    base = dict(mechanism_id=m["id"], axis=m["axis"], name=m["name"])
    path = Path(os.path.expanduser(probe["path"]))
    if not path.exists():
        return ProbeResult(**base, status=DEAD, detail=f"文件不存在: {path}")
    line = _last_nonempty_line(path)
    if not line:
        return ProbeResult(**base, status=DEAD, detail="文件空,无记录")
    ts = _parse_ts(line)
    if ts is None:
        return ProbeResult(**base, status=DEAD, detail="尾行无可解析时间戳")
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    max_h = float(sla.get("max_silence_h", 24))
    detail = f"age={age_h:.1f}h / sla={max_h:.0f}h · last={ts.isoformat(timespec='seconds')}"
    if age_h < max_h * 0.8:
        return ProbeResult(**base, status=GREEN, detail=detail)
    if age_h < max_h:
        return ProbeResult(**base, status=YELLOW, detail=detail + " (接近边界)")
    return ProbeResult(**base, status=DEAD, detail=detail + " → 陈旧")


def _probe_command(m: dict, root: Path) -> ProbeResult:
    """command 探针:跑命令按 expect_exit 判定。runner!=ready 直接 PENDING。"""
    probe = m["probe"]
    base = dict(mechanism_id=m["id"], axis=m["axis"], name=m["name"])
    if m.get("runner") != "ready":
        return ProbeResult(**base, status=PENDING, detail="runner 待实现 (档位②)")
    try:
        r = subprocess.run(
            probe.get("run", ""), shell=True, capture_output=True, text=True,
            timeout=float(probe.get("timeout_s", 30)), cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(**base, status=RED, detail="探活超时")
    except Exception as e:  # noqa: BLE001
        return ProbeResult(**base, status=RED, detail=f"探活异常: {e}")
    if r.returncode == probe.get("expect_exit", 0):
        return ProbeResult(**base, status=GREEN, detail=f"exit={r.returncode}")
    err = (r.stderr or r.stdout or "").strip().splitlines()
    return ProbeResult(**base, status=RED, detail=f"exit={r.returncode} · {err[-1][:80] if err else ''}")


def _probe_one(m: dict, root: Path, quick: bool) -> ProbeResult:
    kind = m.get("probe", {}).get("kind", "")
    base = dict(mechanism_id=m["id"], axis=m["axis"], name=m["name"])
    if kind == "jsonl_freshness":
        return _probe_jsonl_freshness(m)
    if kind == "command":
        if quick:
            return ProbeResult(**base, status=PENDING, detail="--quick 跳过 command 型")
        return _probe_command(m, root)
    return ProbeResult(**base, status=PENDING, detail=f"{kind} runner 待实现 (档位②)")


def _aggregate(results: list[ProbeResult]) -> dict:
    """聚合为存活率 + 覆盖率两个正交指标。

    存活率 survival[axis] = green / probed(PENDING 不计分母;无探活记 None,不参与短板)。
    覆盖率 coverage[axis] = probed / total。
    xplane_score = min(有探活各轴的存活率) —— 木桶短板;无任何探活时 0.0。
    xplane_factor = 1 - W_XPLANE*(1 - xplane_score/100) —— 乘法折扣,供 health 接入。
    """
    axes: dict[str, list[ProbeResult]] = {}
    for r in results:
        axes.setdefault(r.axis, []).append(r)
    survival: dict[str, float | None] = {}
    coverage: dict[str, float] = {}
    for axis, items in axes.items():
        probed = [r for r in items if r.status != PENDING]
        if probed:
            pts = sum(1.0 if r.status == GREEN else 0.5 if r.status == YELLOW else 0.0 for r in probed)
            survival[axis] = round(pts / len(probed) * 100, 1)
        else:
            survival[axis] = None
        coverage[axis] = round(len(probed) / len(items) * 100, 1)
    survived = [v for v in survival.values() if v is not None]
    xplane_score = round(min(survived), 1) if survived else 0.0
    total_probed = sum(1 for r in results if r.status != PENDING)
    overall_coverage = round(total_probed / len(results) * 100, 1) if results else 0.0
    xplane_factor = round(1 - W_XPLANE * (1 - xplane_score / 100), 4)
    return {
        "survival": survival,
        "coverage": coverage,
        "xplane_score": xplane_score,
        "overall_coverage": overall_coverage,
        "xplane_factor": xplane_factor,
    }


def compute_xplane_score(quick: bool = True) -> dict:
    """编程入口:供 sync_omo_state / omo_state 接入 health_score。

    返回聚合结果(含 xplane_score / xplane_factor / survival / coverage / results)。
    任何前置缺失(无 yaml / 无注册表 / 无机制)返回 xplane_score=0.0 + error 字段,
    不抛异常 —— 让调用方决定是否降级(健康同步不能因 X-Plane 故障而崩)。
    """
    if yaml is None:
        return {"xplane_score": 0.0, "xplane_factor": 1.0, "error": "pyyaml missing"}
    reg = _find_registry()
    if reg is None:
        return {"xplane_score": 0.0, "xplane_factor": 1.0, "error": "registry not found"}
    data = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
    mechanisms = data.get("mechanisms", [])
    if not mechanisms:
        return {"xplane_score": 0.0, "xplane_factor": 1.0, "error": "no mechanisms"}
    results = [_probe_one(m, reg.parent.parent, quick) for m in mechanisms]
    agg = _aggregate(results)
    agg["results"] = results
    agg["probed_at"] = datetime.now(timezone.utc).isoformat()
    return agg


def _render(results: list[ProbeResult], agg: dict) -> str:
    out = ["═" * 66, f"  X-Plane 探活报告  ·  {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "═" * 66]
    for axis in sorted({r.axis for r in results}):
        items = [r for r in results if r.axis == axis]
        surv = agg["survival"].get(axis)
        cov = agg["coverage"].get(axis, 0.0)
        surv_str = f"{surv:.0f}%" if surv is not None else "未探"
        out.append(f"\n{axis}  存活率 {surv_str} · 覆盖 {cov:.0f}%   ({len(items)} 项)")
        for r in items:
            label = f"  {_ICON.get(r.status, '?')} {r.mechanism_id:<7} {r.name:<14} "
            out.append(_color(label, r.status) + r.detail)
    pend = sum(1 for r in results if r.status == PENDING)
    xp = agg["xplane_score"]
    factor = agg["xplane_factor"]
    out += [
        "\n" + "─" * 66,
        f"  xplane_score(存活率短板) = {xp:.0f}   ·   探活覆盖率 = {agg['overall_coverage']:.0f}%  ({len(results) - pend}/{len(results)})",
        f"  health 接入: xplane_factor = {factor}  →  raw=100 时 health 100 → {round(100 * factor)} 分(W={W_XPLANE})",
        f"  注: 存活率只评判已探机制(PENDING={pend} 不冤算死亡);覆盖率低 → X 轴可观测性按债务追踪",
        "─" * 66,
    ]
    return "\n".join(out)


def cmd_check(args: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="omo x-axis check")
    ap.add_argument("--quick", action="store_true", help="只跑 jsonl_freshness (只读,秒级)")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ns = ap.parse_args(args)

    agg = compute_xplane_score(quick=ns.quick)
    if "error" in agg:
        print(f"ERROR: {agg['error']}", file=sys.stderr)
        return 1
    results = agg["results"]
    if ns.json:
        payload = {k: v for k, v in agg.items() if k != "results"}
        payload["results"] = [r.__dict__ for r in results]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_render(results, agg))
    return 0


def main(args: list[str] | None = None) -> int:
    argv = list(args if args is not None else sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help"):
        print("Usage: omo x-axis <check> [--quick] [--json]")
        return 0 if argv else 1
    if argv[0] == "check":
        return cmd_check(argv[1:])
    print(f"Unknown subcommand: {argv[0]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
