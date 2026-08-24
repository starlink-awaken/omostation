#!/usr/bin/env python3
"""compass-radar: 调 c2g.strategy 真实审计 + 写治理健康分 SSOT.

不重写 radar 逻辑,直接 import c2g.strategy 的真审计函数
(strategy_audit/_check_anomalies/_collect_metrics),
捕获 print 输出 + 解析异常数量,算 health_score,落 .omo/state/health.yaml.

health_score (复合, ISC-3 执行面主导 — G-CONV.3 / ADR-0210):
  复合分 = 0.3 * governance_anomaly_score + 0.5 * runtime_health_score + 0.2 * freshness_score

  governance_anomaly_score (原 health_score, ISC-3 语义重命名保留):
    0 异常 → 100, 1 → 85, 2 → 70, 3 → 55, 4 → 40, ≥5 → 25 (熔断)
  runtime_health_score:
    service_online_ratio = online_services / total_services (来自 system.yaml runtime_health_summary)
    依赖 G-CONV.2 去假阳性 (stdio transient 不计入 dead)
  freshness_score:
    health.yaml generated_at 距今 ≤1h → 100, ≤24h → 80, ≤7d → 50, 否则 0

  治本动机: ISC-1 权重偏声明面 (gov 0.5); ISC-2/3 把 runtime 提到 0.5 执行面主导.
  复合化后 service_online_ratio 直接拉低 health_score, 触发 X1 critical 告警 (ISC-4 dispatcher).

用法:
  python bin/compass_radar.py
  python bin/compass_radar.py --output .omo/state/health.yaml
  python bin/compass_radar.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _health_score_from_anomalies(anomaly_count: int) -> int:
    """根据异常数量映射 governance_anomaly_score (0-100, 越高越健康).

    ISC-3 治本: 原 health_score 语义保留为 governance_anomaly_score (名副其实).
    """
    if anomaly_count == 0:
        return 100
    if anomaly_count == 1:
        return 85
    if anomaly_count == 2:
        return 70
    if anomaly_count == 3:
        return 55
    if anomaly_count == 4:
        return 40
    return 25  # 熔断线


def _health_check_is_online(health_check: object) -> bool:
    """Treat healthy / healthy (probe) / idle+healthy as online (G-CONV.2 de-false-positive)."""
    hc = str(health_check or "").strip().lower()
    if not hc:
        return False
    if hc.startswith("healthy"):
        return True
    # idle ≠ down when probe still reports healthy elsewhere
    if hc in {"idle", "ok", "up"}:
        return True
    return False


def collect_runtime_health(ws_root: Path) -> tuple[float | None, dict]:
    """从 system_health.yaml 过滤 daemon 类型服务计算常驻在线率 (WS-2 纠偏).

    返回 (service_online_ratio 0.0-1.0 或 None, summary_dict).

    公共 API (无副作用, 纯读 system_health.yaml 现算): 被 generate-brief.py 复用,
    避免 BRIEF daemon 在线率读 system.yaml 死字段造成快照幻影 (health-daemon-ratio-phantom).

    ISC-3 / G-CONV.3: ratio 仅用 daemon 口径 (非 total services), 与 health.yaml
    service_online_ratio 单源一致; healthy (probe) 计入在线.
    """
    import yaml

    health_yaml = ws_root / ".omo" / "state" / "system_health.yaml"
    if not health_yaml.is_file():
        return (None, {})
    try:
        data = yaml.safe_load(health_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        return (None, {})
    services = data.get("services") or {}
    if not services:
        return (None, {})

    total_daemons = 0
    online_daemons = 0

    for name, s in services.items():
        if not isinstance(s, dict):
            continue
        if s.get("type") != "daemon":
            continue
        total_daemons += 1
        runtime = s.get("runtime") or {}
        status = str(runtime.get("status") or "").lower()
        # running / idle (listening) / healthy* / port listening → online
        if (
            status in {"running", "idle", "active"}
            or _health_check_is_online(s.get("health_check"))
            or s.get("port_listening") is True
        ):
            online_daemons += 1

    if total_daemons <= 0:
        return (None, {})
    ratio = online_daemons / total_daemons
    return (
        ratio,
        {
            # single-source fields: daemon-only (do not mix unmanaged services into ratio)
            "total_services": total_daemons,
            "total_daemons": total_daemons,
            "online_daemons": online_daemons,
            "online_services": online_daemons,
            "ratio": ratio,
            "source": "daemon_de_false_positive",
        },
    )


# G-CONV.3 / ISC-3: execution-surface penalties (points deducted from governance)
_W_ORPHAN_WORKTREE = 4
_W_ADR_RENUMBER = 5
_W_CONCURRENT_CONFLICT = 8


def _count_orphan_worktrees(ws_root: Path) -> int:
    """Count git worktrees whose path is missing or not a directory (orphan)."""
    try:
        res = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=ws_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0
    if res.returncode != 0:
        return 0
    orphans = 0
    for line in res.stdout.splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree ") :].strip())
            if path.resolve() == ws_root.resolve():
                continue
            if not path.is_dir():
                orphans += 1
    return orphans


def _prune_orphan_worktrees(ws_root: Path) -> int:
    """治本 (N1, 2026-07-28): 清 orphan worktree record (目录已不存在), 防 wt_pressure 累积.

    orphan = worktree record 在但目录已删. `git worktree prune` 清 record (安全, 不动实际文件).
    产生机制: 并行作业开 worktree (gac-worktree/手动) 后未 remove, 目录删了 record 残留 →
      _count_concurrent_conflict_signals wt_pressure 累积 → concurrent_conflicts 假高 → health 扣分.
    修法: run_radar 生成 health 前自动 prune, orphan 不累积 (N1 第二次系统性治本).
    返回 git returncode (0=成功).
    """
    try:
        res = subprocess.run(
            ["git", "worktree", "prune"],
            cwd=ws_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        return res.returncode
    except (OSError, subprocess.TimeoutExpired):
        return 1


def _count_adr_renumber_signals(ws_root: Path) -> int:
    """Real ADR number collisions (duplicate ids) — via bin/adr/_lib 单一真相源.

    复用 bin/adr/_lib.py::duplicate_adr_numbers (与 adr-coverage.check_coverage
    同源), 消除两处重复的编号解析 + duplicate 检测 (/simplify finding a DRY).
    """
    adr_lib = Path(__file__).resolve().parent / "adr"
    if str(adr_lib) not in sys.path:
        sys.path.insert(0, str(adr_lib))
    try:
        from _lib import (
            duplicate_adr_numbers,  # type: ignore[reportMissingImports]
        )
    except ImportError:
        return 0
    decisions = ws_root / ".omo" / "_knowledge" / "decisions"
    return len(duplicate_adr_numbers(decisions))


def _count_concurrent_conflict_signals(ws_root: Path) -> int:
    """Concurrent pressure = distinct active runs (status=active) + worktree fan-out.

    读 run 记录的 status (canonical) 而非 lock 文件副作用 (/simplify finding b):
    旧版数 scope-lock 文件, 不看 run status — 已 close 但 lock 未释放的 run
    仍被误算活跃. 现按 run 文件 status=active 计 distinct 活跃 run.
    """
    import yaml

    runs_dir = ws_root / ".omo" / "_delivery" / "agent-workflows" / "runs"
    active_runs: set[str] = set()
    if runs_dir.is_dir():
        for p in runs_dir.glob("*.yaml"):
            if not p.is_file():
                continue
            try:
                payload = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if isinstance(payload, dict) and payload.get("status") == "active":
                rid = payload.get("run_id") or p.stem
                if isinstance(rid, str):
                    active_runs.add(rid)
    run_pressure = max(0, len(active_runs) - 1)
    # worktree fan-out (excluding main) as soft concurrency signal
    try:
        res = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=ws_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        wt = sum(1 for ln in res.stdout.splitlines() if ln.startswith("worktree "))
        wt_pressure = max(0, wt - 2)  # main + 1 active worktree free
    except (OSError, subprocess.TimeoutExpired):
        wt_pressure = 0
    return run_pressure + wt_pressure


def collect_governance_execution_surface(ws_root: Path) -> dict:
    """Live execution-surface inputs for ISC-3 governance sub-score (G-CONV.3).

    Not pure anomaly_count: includes orphan worktrees, ADR renumber events,
    and concurrent lock/worktree pressure so governance can drop under real load.
    """
    orphan = _count_orphan_worktrees(ws_root)
    renumber = _count_adr_renumber_signals(ws_root)
    conflict = _count_concurrent_conflict_signals(ws_root)
    return {
        "orphan_worktrees": orphan,
        "adr_renumber_events": renumber,
        "concurrent_conflicts": conflict,
        "weights": {
            "orphan_worktrees": _W_ORPHAN_WORKTREE,
            "adr_renumber_events": _W_ADR_RENUMBER,
            "concurrent_conflicts": _W_CONCURRENT_CONFLICT,
        },
    }


def governance_score_from_execution(anomaly_score: int, surface: dict) -> tuple[int, dict]:
    """Combine anomaly base with execution-surface deductions (G-CONV.3).

    score = max(0, anomaly_score − Σ count_i × weight_i)
    """
    weights = surface.get("weights") or {
        "orphan_worktrees": _W_ORPHAN_WORKTREE,
        "adr_renumber_events": _W_ADR_RENUMBER,
        "concurrent_conflicts": _W_CONCURRENT_CONFLICT,
    }
    orphan = int(surface.get("orphan_worktrees") or 0)
    renumber = int(surface.get("adr_renumber_events") or 0)
    conflict = int(surface.get("concurrent_conflicts") or 0)
    deduct = (
        orphan * int(weights.get("orphan_worktrees", _W_ORPHAN_WORKTREE))
        + renumber * int(weights.get("adr_renumber_events", _W_ADR_RENUMBER))
        + conflict * int(weights.get("concurrent_conflicts", _W_CONCURRENT_CONFLICT))
    )
    score = max(0, int(anomaly_score) - deduct)
    detail = {
        "base_anomaly_score": int(anomaly_score),
        "execution_deduction": deduct,
        "orphan_worktrees": orphan,
        "adr_renumber_events": renumber,
        "concurrent_conflicts": conflict,
        "weights": weights,
        "score": score,
    }
    return score, detail


def _freshness_score(health_yaml: Path, now_iso: str) -> tuple[int, str]:
    """health.yaml generated_at 新鲜度评分 (ISC-1 复合分输入).

    返回 (score 0-100, age_human_readable).
    """
    if not health_yaml.is_file():
        return (0, "never-generated")
    try:
        import yaml

        data = yaml.safe_load(health_yaml.read_text(encoding="utf-8")) or {}
        gen = data.get("generated_at")
        if not gen:
            return (0, "no-timestamp")
        gen_dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
        now_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        age_s = (now_dt - gen_dt).total_seconds()
    except Exception:
        return (0, "parse-error")

    if age_s < 0:
        return (100, "future")  # 时钟偏移, 宽容
    if age_s <= 3600:
        return (100, f"{age_s / 60:.0f}m")
    if age_s <= 86400:
        return (80, f"{age_s / 3600:.1f}h")
    if age_s <= 7 * 86400:
        return (50, f"{age_s / 86400:.1f}d")
    return (0, f"{age_s / 86400:.1f}d-stale")


def _composite_health_score(
    governance_anomaly_score: int,
    service_online_ratio: float | None,
    freshness_score: int,
    feedback_alive: bool = True,
) -> tuple[int, dict]:
    """复合健康分 (ISC-3 执行面主导) + feedback 回路硬门槛 (理想态 evidence-driven).

    权重 (G-CONV.3): governance 0.3 + runtime 0.5 + freshness 0.2.
    runtime 维度缺失时, 权重重分配到 governance (不因数据缺失惩罚分).
    feedback 回路断 (alive=False) → health 硬封顶 50 (防假绿: 回路断 governance 无活动
    却报满分, 见 evidence-smoke 多源 OR + PR#77).
    """
    weights = {"governance": 0.3, "freshness": 0.2}
    contributions = {
        "governance": governance_anomaly_score * 0.3,
        "freshness": freshness_score * 0.2,
    }
    if service_online_ratio is not None:
        runtime_score = round(service_online_ratio * 100)
        weights["runtime"] = 0.5
        contributions["runtime"] = runtime_score * 0.5
    else:
        # runtime 缺失: 把 0.5 权重还回 governance (0.3 → 0.8)
        weights["governance"] = 0.8
        contributions["governance"] = governance_anomaly_score * 0.8

    total_weight = sum(weights.values())
    raw = sum(contributions.values()) / total_weight if total_weight else 0
    score = round(raw)
    breakdown: dict = {
        "weights": weights,
        "contributions": contributions,
        "raw": round(raw, 2),
    }
    # feedback 回路硬门槛 (理想态 evidence-driven): 断 → 封顶 50 (触发 X1 告警, 防假绿)
    if not feedback_alive:
        # 阈值 50: 半分线 — 高于 governance 熔断 25 (仍触发 X1 告警) 但不熔断 (留恢复窗口). 治 P5 magic number.
        score = min(score, 50)
        breakdown["feedback_capped"] = True
        breakdown["feedback_note"] = "feedback loop dead → capped at 50 (evidence-driven)"
    return (score, breakdown)


def _local_feedback_liveness(ws_root: Path) -> tuple[bool, dict]:
    """轻量 fallback: 直接读 governance-history / omo-events (与 evidence-smoke 同源规则).

    仅在 evidence-smoke 不可用时使用 (ADR-0216), 避免 import/agora 依赖把复合分误封 50.
    """
    import json

    sources = {
        "governance_history": ws_root / ".omo" / "_knowledge" / "governance-history.jsonl",
        "omo_events": ws_root / ".omo" / "_knowledge" / "omo-events.jsonl",
    }
    per_source: dict[str, Any] = {}
    any_alive = False
    best_staleness = None
    best_ts = ""
    for name, path in sources.items():
        entry: dict[str, Any] = {"exists": path.is_file()}
        if not path.is_file():
            per_source[name] = entry
            continue
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            entry["entry_count"] = len(lines)
            if not lines:
                per_source[name] = entry
                continue
            last = json.loads(lines[-1])
            ts = last.get("timestamp") or last.get("ts") or last.get("date") or ""
            entry["last_ts"] = ts
            if ts:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                hours = round((datetime.now(UTC) - dt).total_seconds() / 3600, 1)
                entry["staleness_hours"] = hours
                entry["alive"] = hours < 24
                if hours < 24:
                    any_alive = True
                if best_staleness is None or hours < best_staleness:
                    best_staleness = hours
                    best_ts = str(ts)
        except Exception as exc:
            entry["error"] = str(exc)[:120]
        per_source[name] = entry
    return (
        any_alive,
        {
            "alive": any_alive,
            "source": "compass_local_fallback",
            "last_ts": best_ts,
            "staleness_hours": best_staleness,
            "per_source": per_source,
        },
    )


def _collect_feedback_liveness(ws_root: Path) -> tuple[bool, dict]:
    """反馈回路存活 — 优先 evidence-smoke (DRY); 失败则本地 fallback (ADR-0216).

    evidence-smoke 多源 OR (governance-history | omo-events) 是 feedback 判定 SSOT.
    回路断 = governance 无活动 → compass_radar _composite 硬封顶 health (防假绿).
    """
    import json
    import subprocess

    try:
        res = subprocess.run(
            [
                sys.executable,
                str(ws_root / "bin" / "gac" / "evidence-smoke.py"),
                "--json",
            ],
            cwd=ws_root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        stdout = (res.stdout or "").strip()
        if stdout.startswith("{"):
            data = json.loads(stdout)
            fb = data.get("feedback_loop") or {}
            if fb:
                # partial smoke (agora missing) still carries feedback_loop
                return (bool(fb.get("alive")), {**fb, "via": "evidence-smoke"})
        if res.returncode != 0:
            alive, fb = _local_feedback_liveness(ws_root)
            fb["fallback_reason"] = f"evidence-smoke exit {res.returncode}"
            return (alive, fb)
        alive, fb = _local_feedback_liveness(ws_root)
        fb["fallback_reason"] = "evidence-smoke empty stdout"
        return (alive, fb)
    except Exception as e:
        alive, fb = _local_feedback_liveness(ws_root)
        fb["fallback_reason"] = f"error: {str(e)[:80]}"
        return (alive, fb)


def run_radar(omo_dir: Path) -> dict:
    """调 c2g.strategy 真审计,返回 metrics 字典."""
    # 治本 (N1, 2026-07-28): 清 orphan worktree, 防 wt_pressure 累积 (concurrent_conflicts 系统性副产品)
    _prune_orphan_worktrees(omo_dir.parent if omo_dir.name == ".omo" else omo_dir)
    # 把 c2g src 加进 sys.path (c2g 是 src 布局, 但本脚本不在 c2g venv)
    c2g_src = Path(__file__).resolve().parent.parent / "projects" / "c2g" / "src"
    if c2g_src.is_dir() and str(c2g_src) not in sys.path:
        sys.path.insert(0, str(c2g_src))

    # ADR-0412 收敛后 c2g vendor 进 omo (_vendored/c2g), 旧 submodule 布局移除时走此回退
    c2g_vendored = (
        Path(__file__).resolve().parent.parent / "projects" / "omo" / "src" / "omo" / "_vendored"
    )
    if not c2g_src.is_dir() and c2g_vendored.is_dir() and str(c2g_vendored) not in sys.path:
        sys.path.insert(0, str(c2g_vendored))

    try:
        from c2g.strategy import (  # type: ignore[reportMissingImports]
            _check_anomalies,
            _collect_metrics,
            _list_task_files,
        )
    except ImportError as exc:
        # ADR-0216: worktree 未 init c2g 时仍可算 runtime/freshness 复合分
        print(
            f"⚠️  c2g.strategy unavailable ({exc}); "
            "using empty task audit (anomaly_count=0). "
            "Init with: git submodule update --init projects/c2g",
            file=sys.stderr,
        )
        return {
            "total_tasks": 0,
            "done": 0,
            "planned": 0,
            "anomaly_count": 0,
            "anomalies": [],
            "priority_dist": {},
            "c2g_degraded": True,
            "c2g_error": str(exc)[:160],
        }

    done_files, planned_files = _list_task_files(omo_dir)
    all_files = done_files + planned_files
    total = len(all_files)
    total_done = len(done_files)
    total_planned = len(planned_files)

    metrics = _collect_metrics(all_files)
    pending_metrics = _collect_metrics(planned_files)
    warnings = _check_anomalies(metrics, total, omo_dir=omo_dir, pending_metrics=pending_metrics) if total else []
    # 分布从 metrics 导出 (避免再调 strategy_audit 重复计算)
    distributions = {
        "priority": dict(metrics["priority"]),
        "risk": dict(metrics["risk_level"]),
        "owner": dict(metrics["owner"]),
        "phase": dict(metrics["phase"]),
        "status": dict(metrics["status"]),
    }
    for label, dist in distributions.items():
        print(f"📊 {label.title()} Distribution:")
        for k, v in sorted(dist.items(), key=lambda x: (-x[1], x[0]))[:10]:
            print(f"   {k:<24} {v:>3}")

    return {
        "total_tasks": total,
        "done": total_done,
        "planned": total_planned,
        "anomaly_count": len(warnings),
        "anomalies": warnings,
        "priority_dist": dict(metrics["priority"]),
        "risk_dist": dict(metrics["risk_level"]),
        "owner_dist": dict(metrics["owner"]),
        "phase_dist": dict(metrics["phase"]),
        "status_dist": dict(metrics["status"]),
    }


def render_yaml(report: dict) -> str:
    """手写 YAML 渲染 (避免引入额外依赖)."""
    lines: list[str] = []
    lines.append("# governance health — 治理健康分 SSOT")
    lines.append(f"# generated_at: {report['generated_at']}")
    lines.append("# source: c2g.strategy (real audit, no mock)")
    lines.append("# range: 0-100, higher = healthier")
    lines.append(f"# health_score: composite (ISC-3) = {report['health_composite_breakdown']['weights']}")
    lines.append("")
    lines.append("generated_at: " + _yaml_str(report["generated_at"]))
    lines.append("source: " + _yaml_str(report["source"]))
    lines.append("health_score: " + str(report["health_score"]))
    lines.append("governance_anomaly_score: " + str(report["governance_anomaly_score"]))
    lines.append("anomaly_count: " + str(report["anomaly_count"]))
    lines.append("service_online_ratio: " + _format_ratio(report.get("service_online_ratio")))
    lines.append("freshness_score: " + str(report["freshness_score"]))
    # feedback 回路存活 (理想态 evidence-driven, 防假绿, 见 _composite_health_score 硬门槛)
    fb = report.get("feedback_liveness") or {}
    lines.append("feedback_alive: " + str(fb.get("alive", False)))
    if fb.get("last_ts"):
        lines.append("feedback_last_ts: " + _yaml_str(fb["last_ts"]))
    if fb.get("staleness_hours") is not None:
        lines.append("feedback_staleness_hours: " + str(fb["staleness_hours"]))
    lines.append("total_tasks: " + str(report["total_tasks"]))
    lines.append("done: " + str(report["done"]))
    lines.append("planned: " + str(report["planned"]))
    lines.append("")
    # G-CONV.3: dump execution-surface so governance sub-score is traceable
    ges = report.get("governance_execution_surface") or {}
    if ges:
        lines.append("governance_execution_surface:")
        for k in (
            "base_anomaly_score",
            "execution_deduction",
            "orphan_worktrees",
            "adr_renumber_events",
            "concurrent_conflicts",
            "score",
        ):
            if k in ges:
                lines.append(f"  {k}: {ges[k]}")
        if isinstance(ges.get("weights"), dict):
            lines.append("  weights:")
            for wk, wv in ges["weights"].items():
                lines.append(f"    {wk}: {wv}")
        lines.append("")
    lines.append("health_composite_breakdown:")
    bd = report["health_composite_breakdown"]
    lines.append("  weights:")
    for k, v in bd["weights"].items():
        lines.append(f"    {k}: {v}")
    lines.append("  contributions:")
    for k, v in bd["contributions"].items():
        lines.append(f"    {k}: {v}")
    lines.append(f"  raw: {bd['raw']}")
    lines.append("")
    lines.append("anomalies:")
    if report["anomalies"]:
        for w in report["anomalies"]:
            lines.append("  - " + _yaml_str(w))
    else:
        lines.append("  []")
    lines.append("")
    lines.append("distributions:")
    for dim in (
        "priority_dist",
        "risk_dist",
        "owner_dist",
        "phase_dist",
        "status_dist",
        "governance_dist",
    ):
        lines.append(f"  {dim}:")
        dist = report.get(dim) or {}
        if not dist:
            lines.append("    {}")
            continue
        for k, v in sorted(dist.items()):
            lines.append(f"    {k}: {v}")
    lines.append("")
    return "\n".join(lines)


def _format_ratio(ratio: float | None) -> str:
    if ratio is None:
        return '"unavailable"'
    return f"{ratio:.3f}"


def _yaml_str(s: str) -> str:
    """简化版 YAML 字符串转义 (假设 s 不含特殊控制字符)."""
    # 去掉 emoji (yaml 不喜欢)
    safe = s.replace("⚠️", "[WARN]").replace("✅", "[OK]")
    # 双引号包裹, 转义内部 "
    return '"' + safe.replace('"', '\\"') + '"'


def _normalize_health_yaml(payload: str) -> str:
    lines = []
    for line in payload.splitlines():
        if line.startswith("# generated_at:") or line.startswith("generated_at:"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _normalize_system_yaml(payload: str) -> str:
    import yaml

    data = yaml.safe_load(payload) or {}
    if isinstance(data, dict):
        data = dict(data)
        data.pop("health_score_generated_at", None)
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=True)


def _write_text_if_changed(path: Path, payload: str, *, normalize=None) -> bool:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        comparable_current = normalize(current) if normalize else current
        comparable_payload = normalize(payload) if normalize else payload
        if comparable_current == comparable_payload:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(payload, encoding="utf-8")  # audit-exempt: non-atomic-write
    os.replace(tmp, path)
    return True


def _append_health_history(health_yaml_path: Path, report: dict[str, Any]) -> None:
    """Append a compact snapshot to .omo/state/history/health.jsonl.

    The current health.yaml is regenerated on every radar run, so its
    content is overwritten without history. Operators asking "what was
    the health score last week?" need a JSONL append-only history to
    answer that. Each line is a single JSON record with:
      - ts (UTC ISO8601)
      - health_score (composite)
      - governance_anomaly_score
      - anomaly_count
      - service_online_ratio
      - freshness_score
      - total_tasks
      - source (run_radar source marker)

    Retention is unbounded for now; a downstream cron (e.g.
    omo state prune-history --keep-days=90) can rotate.

    Failures are silent: this is a best-effort observability feature,
    not a core invariant. If the JSONL write fails, radar still
    succeeds.
    """
    import json as _json
    try:
        history_dir = health_yaml_path.parent.parent / "state" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "health.jsonl"
        snapshot = {
            "ts": _utc_now(),
            "health_score": report.get("health_score"),
            "governance_anomaly_score": report.get("governance_anomaly_score"),
            "anomaly_count": report.get("anomaly_count"),
            "service_online_ratio": report.get("service_online_ratio"),
            "freshness_score": report.get("freshness_score"),
            "total_tasks": report.get("total_tasks"),
            "source": report.get("source"),
        }
        # append-only, atomic per-line (write+fsync then continue)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(_json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")
    except Exception as exc:
        print(f"⚠ history append failed (non-fatal): {exc}", file=sys.stderr)


def _observability_event_anomalies(ws_root: Path) -> tuple[int, dict[str, Any]]:
    """统一事件面近 24h 异常统计 (design: docs/observability-unified-architecture.md).

    读 .omo/_delivery/observability/events.jsonl, 统计 severity ∈ {critical, degraded}
    且 ts 在 24h 内的事件数. 缺失/损坏 → (0, {}) 不惩罚.

    去重规则 (P79 治本):
      - 同一 (type, payload.check) 在 1h 窗口内只计 1 次
      - 这样 gac-gate 反复失败同一检查不会因重试把 anomaly_count 拉满
    """
    events_file = ws_root / ".omo" / "_delivery" / "observability" / "events.jsonl"
    if not events_file.exists():
        return (0, {})
    try:
        from datetime import datetime, timedelta

        now = datetime.now(UTC)
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
        dedup_window = timedelta(hours=1)
        count = 0
        by_type: dict[str, int] = {}
        # dedup_key -> (ts, type) 记录最近一次触发
        dedup: dict[tuple[str, str], datetime] = {}

        def _parse(ts_str: str) -> datetime | None:
            try:
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                return datetime.fromisoformat(ts_str)
            except (ValueError, TypeError):
                return None

        with open(events_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    import json

                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("ts", "") < cutoff_24h:
                    continue
                if e.get("severity") not in {"critical", "degraded"}:
                    continue
                t = str(e.get("type", "unknown"))
                check = str(e.get("payload", {}).get("check", ""))
                key = (t, check)
                ev_ts = _parse(e.get("ts", ""))
                if ev_ts is None:
                    # 不能解析时间戳的事件也计入 (避免 silently drop)
                    count += 1
                    by_type[t] = by_type.get(t, 0) + 1
                    continue
                # 去重: 同 key 在 1h 窗口内已记录则 skip
                if key in dedup and (ev_ts - dedup[key]) < dedup_window:
                    continue
                dedup[key] = ev_ts
                count += 1
                by_type[t] = by_type.get(t, 0) + 1
        return (count, {"window_24h": count, "by_type": by_type, "dedup_window_hours": 1})
    except Exception:  # 非阻断
        return (0, {})


def build_health_projection(omo_dir: Path, output: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Build health.yaml content inputs without writing projection files."""
    ws_root = omo_dir.parent
    report = run_radar(omo_dir)
    now_iso = _utc_now()
    report["generated_at"] = now_iso
    report["source"] = "c2g.strategy (real audit, no mock)"

    # 统一事件面 observability 因子 (design: docs/observability-unified-architecture.md):
    # 近 24h critical/degraded 事件并入 anomaly_count, 让运行时异常影响健康分.
    obs_count, obs_detail = _observability_event_anomalies(ws_root)
    if obs_count:
        report["anomaly_count"] = int(report["anomaly_count"]) + obs_count
        report["observability_events"] = obs_detail

    anomaly_base = _health_score_from_anomalies(report["anomaly_count"])
    # G-CONV.3: governance sub-score = anomaly base − execution-surface penalties
    gov_surface = collect_governance_execution_surface(ws_root)
    governance_anomaly_score, gov_detail = governance_score_from_execution(anomaly_base, gov_surface)
    report["governance_anomaly_score"] = governance_anomaly_score
    report["governance_execution_surface"] = gov_detail

    service_online_ratio, runtime_summary = collect_runtime_health(ws_root)
    report["service_online_ratio"] = service_online_ratio
    report["runtime_summary"] = runtime_summary

    prior_fresh_score, prior_age_desc = _freshness_score(output, now_iso)
    # ADR-0216: this run writes generated_at=now → freshness for composite is 100.
    # Still record prior_* for diagnostics (how stale the previous projection was).
    fresh_score, age_desc = 100, "regenerated-now"
    report["freshness_score"] = fresh_score
    report["prior_freshness_score"] = prior_fresh_score
    report["prior_freshness_age"] = prior_age_desc

    feedback_alive, feedback_summary = _collect_feedback_liveness(ws_root)
    report["feedback_liveness"] = feedback_summary

    composite, breakdown = _composite_health_score(
        governance_anomaly_score, service_online_ratio, fresh_score, feedback_alive
    )
    report["health_score"] = composite
    report["health_composite_breakdown"] = breakdown

    # G5/T10-05: 第 6 个可观测轴 — governance 健康分项分布 (composite 三权重贡献).
    # 反映"治理健康可观测性"维度, 数据来自真实 composite 计算 (非 mock).
    gov_dist = {
        "governance": round(breakdown["contributions"].get("governance", 0)),
        "freshness": round(breakdown["contributions"].get("freshness", 0)),
        "runtime": round(breakdown["contributions"].get("runtime", 0)),
    }
    report["governance_dist"] = gov_dist
    print("📊 Governance Distribution:")
    for k, v in sorted(gov_dist.items(), key=lambda x: (-x[1], x[0])):
        print(f"   {k:<24} {v:>3}")
    return report, runtime_summary, age_desc


def build_system_projection_updates(workspace_root: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Build the whitelisted system.yaml projection fields for health sync.

    G-CONV.3 single-source: top-level service_online_ratio and
    runtime_health_summary.ratio both use collect_runtime_health (daemon,
    de-false-positive). Never leave a stale 0.75 summary while top-level is 1.0.
    """
    service_online_ratio = report.get("service_online_ratio")
    runtime_summary = report.get("runtime_summary") or {}
    if not runtime_summary:
        # recompute daemon summary so runtime_health_summary never gets 0/0 with ratio set
        ratio2, runtime_summary = collect_runtime_health(workspace_root)
        if service_online_ratio is None:
            service_online_ratio = ratio2
    ratio_rounded = round(float(service_online_ratio), 4) if service_online_ratio is not None else None
    updates: dict[str, Any] = {
        "health_score": int(report["health_score"]),
        "governance_anomaly_score": int(report["governance_anomaly_score"]),
        "service_online_ratio": ratio_rounded,
        "health_score_source": "compass_radar_composite_isc3",
        "health_score_generated_at": report["generated_at"],
    }
    # Always write runtime_health_summary from the same daemon ratio source
    if ratio_rounded is not None or runtime_summary:
        updates["runtime_health_summary"] = {
            "online_services": int(
                runtime_summary.get("online_daemons") or runtime_summary.get("online_services") or 0
            ),
            "total_services": int(runtime_summary.get("total_daemons") or runtime_summary.get("total_services") or 0),
            "ratio": ratio_rounded if ratio_rounded is not None else runtime_summary.get("ratio"),
            "health_score": int(report["health_score"]),
            "last_scan": report.get("generated_at"),
            "source": "compass_radar_isc3_daemon_ratio",
            "degraded": [],
        }
    # Workflow Mesh health snapshot
    mesh_health = _collect_mesh_health(workspace_root)
    if mesh_health:
        updates["workflow_mesh_health"] = mesh_health
    return updates


def _collect_mesh_health(workspace_root: Path) -> dict[str, Any] | None:
    """Collect Workflow Mesh health snapshot via protocol-based discovery."""
    try:
        omo_src = workspace_root / "projects" / "omo" / "src"
        if str(omo_src) not in sys.path:
            sys.path.insert(0, str(omo_src))
        from omo.workflow_mesh import WorkflowMeshStore

        store = WorkflowMeshStore(workspace_root / ".omo")
        events = store.events()
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        events_last_hour = sum(
            1
            for e in events
            if (
                now - datetime.fromisoformat(e.get("occurred_at", "2000-01-01T00:00:00Z").replace("Z", "+00:00"))
            ).total_seconds()
            < 3600
        )
        producers = {e.get("producer", "") for e in events}
        last_event_age = None
        if events:
            last_ts = events[-1].get("occurred_at", "").replace("Z", "+00:00")
            last_event_age = (now - datetime.fromisoformat(last_ts)).total_seconds()
        return {
            "status": "healthy" if events else "degraded",
            "event_count": len(events),
            "events_last_hour": events_last_hour,
            "last_event_age_seconds": round(last_event_age, 1) if last_event_age else None,
            "bridges_active": sorted(producers),
        }
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="compass-radar: 调 c2g 真审计 + 写 health SSOT")
    parser.add_argument(
        "--omo-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / ".omo",
        help="OMO 目录 (默认 .omo/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出 YAML 路径 (默认 .omo/state/health.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印不写文件",
    )
    args = parser.parse_args()

    omo_dir = args.omo_dir.resolve()
    if not omo_dir.is_dir():
        print(f"❌ OMO 目录不存在: {omo_dir}", file=sys.stderr)
        return 1

    ws_root = omo_dir.parent
    output = args.output or (omo_dir / "state" / "health.yaml")
    output = output.resolve()

    print(f"🧭 compass-radar → {omo_dir}")
    print(f"   output: {output}")

    report, runtime_summary, age_desc = build_health_projection(omo_dir, output)
    governance_anomaly_score = int(report["governance_anomaly_score"])
    service_online_ratio = report.get("service_online_ratio")
    fresh_score = int(report["freshness_score"])

    print()
    print("📊 治理健康分 (ISC-3 复合):")
    print(f"   health_score (composite): {report['health_score']}/100")
    print(f"   governance_anomaly_score: {governance_anomaly_score}/100 (anomalies={report['anomaly_count']})")
    ratio_str = f"{service_online_ratio:.2%}" if service_online_ratio is not None else "unavailable"
    print(
        f"   service_online_ratio:     {ratio_str}  (online={runtime_summary.get('online_services')}/{runtime_summary.get('total_services')})"
    )
    print(f"   freshness_score:          {fresh_score}/100 ({age_desc})")
    print(f"   total:                    {report['total_tasks']} ({report['done']} done + {report['planned']} planned)")
    if report["anomalies"]:
        print("🚨 异常告警:")
        for w in report["anomalies"]:
            print(f"   - {w.replace('⚠️ ', '')}")
    else:
        print("✅ 无 governance 异常")

    if args.dry_run:
        print()
        print("🔍 [dry-run] 不写文件, 仅打印")
        return 0

    changed = _write_text_if_changed(
        output,
        render_yaml(report),
        normalize=_normalize_health_yaml,
    )
    if changed:
        print(f"✅ health.yaml 已刷新: {output}")
    else:
        print(f"ℹ health.yaml 语义未变化, 跳过写入: {output}")

    # 历史快照: append 一个轻量记录到 .omo/state/history/health.jsonl
    # (P79 治本 — 让 trend 文档和未来 dashboard 有真实时间序列)
    _append_health_history(output, report)

    # 同步刷新 system.yaml 的健康分相关字段 (避免 SSOT 偏差告警)
    sync_system_yaml(
        ws_root=ws_root,
        health_score=report["health_score"],
        governance_anomaly_score=governance_anomaly_score,
        service_online_ratio=service_online_ratio,
        generated_at=report["generated_at"],
        runtime_summary=runtime_summary,
    )

    # 自动触发 BRIEF.md 生成 (WS-4 + WS-5)
    try:
        import subprocess

        res = subprocess.run(
            [
                sys.executable,
                str(ws_root / "bin" / "mof" / "generate-brief.py"),
                "--write",
                "--if-changed",
            ],
            cwd=ws_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            print("✅ BRIEF.md 同步刷新成功")
        else:
            print(f"⚠️ BRIEF.md 同步刷新失败: {res.stderr}")
    except Exception as e:
        print(f"⚠️ BRIEF.md 刷新异常: {e}")

    print()
    print(f"✅ 已写入 {output}")
    return 0


def sync_system_yaml(
    ws_root: Path,
    health_score: int,
    governance_anomaly_score: int,
    service_online_ratio: float | None,
    generated_at: str,
    runtime_summary: dict | None = None,
) -> None:
    """把复合 health_score + governance_anomaly_score + service_online_ratio 写回 .omo/state/system.yaml.

    ISC-3: top-level ratio 与 runtime_health_summary.ratio 同口径 (daemon 去假阳性).
    """
    import yaml

    system_yaml = ws_root / ".omo" / "state" / "system.yaml"
    if not system_yaml.is_file():
        print(f"⚠️  system.yaml 不存在: {system_yaml}, 跳过同步")
        return

    try:
        data = yaml.safe_load(system_yaml.read_text(encoding="utf-8"))
        updates = build_system_projection_updates(
            ws_root,
            {
                "health_score": health_score,
                "governance_anomaly_score": governance_anomaly_score,
                "service_online_ratio": service_online_ratio,
                "generated_at": generated_at,
                "runtime_summary": runtime_summary or {},
            },
        )
        data.update(updates)
        payload = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        changed = _write_text_if_changed(
            system_yaml,
            payload,
            normalize=_normalize_system_yaml,
        )
        if changed:
            print(
                f"✅ system.yaml 同步: health_score(composite)={health_score} governance_anomaly={governance_anomaly_score} ratio={service_online_ratio}"
            )
        else:
            print("ℹ system.yaml 语义未变化, 跳过写入")
    except Exception as e:
        print(f"⚠️  system.yaml 同步失败: {e}")


if __name__ == "__main__":
    sys.exit(main())
