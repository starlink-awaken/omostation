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
    import yaml  # noqa: PLC0415

    health_yaml = ws_root / ".omo" / "state" / "system_health.yaml"
    if not health_yaml.is_file():
        return (None, {})
    try:
        data = yaml.safe_load(health_yaml.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
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


def _count_adr_renumber_signals(ws_root: Path) -> int:
    """Count ADR renumber / collision signals in recent decision docs (ADR-0202 D4)."""
    decisions = ws_root / ".omo" / "_knowledge" / "decisions"
    if not decisions.is_dir():
        return 0
    markers = ("renumber", "抢号", "撞号", "ADR-0202 D4", "renumbered", "撞 ADR")
    n = 0
    try:
        files = sorted(decisions.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[
            :40
        ]
    except OSError:
        return 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        low = text.lower()
        if any(m.lower() in low or m in text for m in markers):
            n += 1
    return n


def _count_concurrent_conflict_signals(ws_root: Path) -> int:
    """Active agent-workflow locks beyond 1 + multi-worktree pressure as concurrency signal."""
    locks_dir = ws_root / ".omo" / "_delivery" / "agent-workflows" / "locks"
    active_locks = 0
    if locks_dir.is_dir():
        active_locks = sum(1 for p in locks_dir.glob("*.yaml") if p.is_file())
    # extra locks beyond self imply concurrent agents contending
    lock_pressure = max(0, active_locks - 1)
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
    return lock_pressure + wt_pressure


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


def governance_score_from_execution(
    anomaly_score: int, surface: dict
) -> tuple[int, dict]:
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
        import yaml  # noqa: PLC0415

        data = yaml.safe_load(health_yaml.read_text(encoding="utf-8")) or {}
        gen = data.get("generated_at")
        if not gen:
            return (0, "no-timestamp")
        gen_dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
        now_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        age_s = (now_dt - gen_dt).total_seconds()
    except Exception:  # noqa: BLE001
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
        breakdown["feedback_note"] = (
            "feedback loop dead → capped at 50 (evidence-driven)"
        )
    return (score, breakdown)


def _local_feedback_liveness(ws_root: Path) -> tuple[bool, dict]:
    """轻量 fallback: 直接读 governance-history / omo-events (与 evidence-smoke 同源规则).

    仅在 evidence-smoke 不可用时使用 (ADR-0216), 避免 import/agora 依赖把复合分误封 50.
    """
    import json  # noqa: PLC0415

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
            lines = [
                line
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
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
        except Exception as exc:  # noqa: BLE001
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
    import json  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

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
    except Exception as e:  # noqa: BLE001
        alive, fb = _local_feedback_liveness(ws_root)
        fb["fallback_reason"] = f"error: {str(e)[:80]}"
        return (alive, fb)


def run_radar(omo_dir: Path) -> dict:
    """调 c2g.strategy 真审计,返回 metrics 字典."""
    # 把 c2g src 加进 sys.path (c2g 是 src 布局, 但本脚本不在 c2g venv)
    c2g_src = Path(__file__).resolve().parent.parent / "projects" / "c2g" / "src"
    if c2g_src.is_dir() and str(c2g_src) not in sys.path:
        sys.path.insert(0, str(c2g_src))

    try:
        from c2g.strategy import (  # type: ignore[reportMissingImports]  # noqa: PLC0415, E402
            _collect_metrics,
            _check_anomalies,
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
    warnings = (
        _check_anomalies(
            metrics, total, omo_dir=omo_dir, pending_metrics=pending_metrics
        )
        if total
        else []
    )
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
    lines.append(
        f"# health_score: composite (ISC-3) = {report['health_composite_breakdown']['weights']}"
    )
    lines.append("")
    lines.append("generated_at: " + _yaml_str(report["generated_at"]))
    lines.append("source: " + _yaml_str(report["source"]))
    lines.append("health_score: " + str(report["health_score"]))
    lines.append("governance_anomaly_score: " + str(report["governance_anomaly_score"]))
    lines.append("anomaly_count: " + str(report["anomaly_count"]))
    lines.append(
        "service_online_ratio: " + _format_ratio(report.get("service_online_ratio"))
    )
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
    import yaml  # noqa: PLC0415

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


def build_health_projection(
    omo_dir: Path, output: Path
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Build health.yaml content inputs without writing projection files."""
    ws_root = omo_dir.parent
    report = run_radar(omo_dir)
    now_iso = _utc_now()
    report["generated_at"] = now_iso
    report["source"] = "c2g.strategy (real audit, no mock)"

    anomaly_base = _health_score_from_anomalies(report["anomaly_count"])
    # G-CONV.3: governance sub-score = anomaly base − execution-surface penalties
    gov_surface = collect_governance_execution_surface(ws_root)
    governance_anomaly_score, gov_detail = governance_score_from_execution(
        anomaly_base, gov_surface
    )
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
    return report, runtime_summary, age_desc


def build_system_projection_updates(
    workspace_root: Path, report: dict[str, Any]
) -> dict[str, Any]:
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
    ratio_rounded = (
        round(float(service_online_ratio), 4)
        if service_online_ratio is not None
        else None
    )
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
                runtime_summary.get("online_daemons")
                or runtime_summary.get("online_services")
                or 0
            ),
            "total_services": int(
                runtime_summary.get("total_daemons")
                or runtime_summary.get("total_services")
                or 0
            ),
            "ratio": ratio_rounded
            if ratio_rounded is not None
            else runtime_summary.get("ratio"),
            "health_score": int(report["health_score"]),
            "last_scan": report.get("generated_at"),
            "source": "compass_radar_isc3_daemon_ratio",
            "degraded": [],
        }
    return updates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="compass-radar: 调 c2g 真审计 + 写 health SSOT"
    )
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
    print(
        f"   governance_anomaly_score: {governance_anomaly_score}/100 (anomalies={report['anomaly_count']})"
    )
    ratio_str = (
        f"{service_online_ratio:.2%}"
        if service_online_ratio is not None
        else "unavailable"
    )
    print(
        f"   service_online_ratio:     {ratio_str}  (online={runtime_summary.get('online_services')}/{runtime_summary.get('total_services')})"
    )
    print(f"   freshness_score:          {fresh_score}/100 ({age_desc})")
    print(
        f"   total:                    {report['total_tasks']} ({report['done']} done + {report['planned']} planned)"
    )
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
        import subprocess  # noqa: PLC0415

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
    import yaml  # noqa: PLC0415

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
        payload = yaml.dump(
            data, allow_unicode=True, sort_keys=False, default_flow_style=False
        )
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
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  system.yaml 同步失败: {e}")


if __name__ == "__main__":
    sys.exit(main())
