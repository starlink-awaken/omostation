#!/usr/bin/env python3
"""compass-radar: 调 c2g.strategy 真实审计 + 写治理健康分 SSOT.

不重写 radar 逻辑,直接 import c2g.strategy 的真审计函数
(strategy_audit/_check_anomalies/_collect_metrics),
捕获 print 输出 + 解析异常数量,算 health_score,落 .omo/state/health.yaml.

health_score (复合, ISC-1 治本):
  复合分 = 0.5 * governance_anomaly_score + 0.3 * runtime_health_score + 0.2 * freshness_score

  governance_anomaly_score (原 health_score, ISC-3 语义重命名保留):
    0 异常 → 100, 1 → 85, 2 → 70, 3 → 55, 4 → 40, ≥5 → 25 (熔断)
  runtime_health_score:
    service_online_ratio = online_services / total_services (来自 system.yaml runtime_health_summary)
  freshness_score:
    health.yaml generated_at 距今 ≤1h → 100, ≤24h → 80, ≤7d → 50, 否则 0

  治本动机: 原 health_score 只由 anomaly_count 决定, 服务全死也报 100 (指标名不副实).
  复合化后 service_online_ratio 直接拉低 health_score, 触发 X1 critical 告警 (ISC-4 dispatcher).

用法:
  python bin/compass_radar.py
  python bin/compass_radar.py --output .omo/state/health.yaml
  python bin/compass_radar.py --dry-run
"""
from __future__ import annotations

import argparse
import os
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


def _collect_runtime_health(ws_root: Path) -> tuple[float | None, dict]:
    """从 system_health.yaml 过滤 daemon 类型服务计算常驻在线率 (WS-2 纠偏).

    返回 (service_online_ratio 0.0-1.0 或 None, summary_dict).
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
        if s.get("type") == "daemon":
            total_daemons += 1
            runtime = s.get("runtime") or {}
            # 状态为 running, 或者健康检查 healthy, 或者端口在监听, 均视为在线
            if (
                runtime.get("status") == "running"
                or s.get("health_check") == "healthy"
                or s.get("port_listening") is True
            ):
                online_daemons += 1

    if total_daemons <= 0:
        return (None, {})
    return (
        online_daemons / total_daemons,
        {
            "total_services": len(services),
            "total_daemons": total_daemons,
            "online_daemons": online_daemons,
            "online_services": online_daemons,  # 兼容原有字段命名
        },
    )


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
        return (100, f"{age_s/60:.0f}m")
    if age_s <= 86400:
        return (80, f"{age_s/3600:.1f}h")
    if age_s <= 7 * 86400:
        return (50, f"{age_s/86400:.1f}d")
    return (0, f"{age_s/86400:.1f}d-stale")


def _composite_health_score(
    governance_anomaly_score: int,
    service_online_ratio: float | None,
    freshness_score: int,
    feedback_alive: bool = True,
) -> tuple[int, dict]:
    """复合健康分 (ISC-1 治本) + feedback 回路硬门槛 (理想态 evidence-driven).

    权重: governance 0.5 + runtime 0.3 + freshness 0.2.
    runtime 维度缺失时, 权重重分配到 governance (不因数据缺失惩罚分).
    feedback 回路断 (alive=False) → health 硬封顶 50 (防假绿: 回路断 governance 无活动
    却报满分, 见 evidence-smoke 多源 OR + PR#77).
    """
    weights = {"governance": 0.5, "freshness": 0.2}
    contributions = {
        "governance": governance_anomaly_score * 0.5,
        "freshness": freshness_score * 0.2,
    }
    if service_online_ratio is not None:
        runtime_score = round(service_online_ratio * 100)
        weights["runtime"] = 0.3
        contributions["runtime"] = runtime_score * 0.3
    else:
        # runtime 缺失: 把 0.3 权重还回 governance (0.5 → 0.8)
        weights["governance"] = 0.8
        contributions["governance"] = governance_anomaly_score * 0.8

    total_weight = sum(weights.values())
    raw = sum(contributions.values()) / total_weight if total_weight else 0
    score = round(raw)
    breakdown: dict = {"weights": weights, "contributions": contributions, "raw": round(raw, 2)}
    # feedback 回路硬门槛 (理想态 evidence-driven): 断 → 封顶 50 (触发 X1 告警, 防假绿)
    if not feedback_alive:
        score = min(score, 50)
        breakdown["feedback_capped"] = True
        breakdown["feedback_note"] = "feedback loop dead → capped at 50 (evidence-driven)"
    return (score, breakdown)


def _collect_feedback_liveness(ws_root: Path) -> tuple[bool, dict]:
    """反馈回路存活 (理想态 evidence-driven): omo-events.jsonl 24h 内有记录 = alive.

    跟 evidence-smoke 多源 OR 同源 (omo-events 轻事件流, state-stale-emit 写).
    回路断 = governance 无活动 → compass_radar _composite 硬封顶 health (防假绿)."""
    import json  # noqa: PLC0415
    from datetime import datetime, timezone  # noqa: PLC0415

    events_log = ws_root / ".omo" / "_knowledge" / "omo-events.jsonl"
    if not events_log.is_file():
        return (False, {"reason": "no omo-events log"})
    try:
        lines = [l for l in events_log.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return (False, {"reason": "empty log"})
        last = json.loads(lines[-1])
        ts = last.get("timestamp") or last.get("ts") or last.get("date") or ""
        if not ts:
            return (False, {"reason": "no timestamp", "last_ts": ts})
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        hours = round((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 1)
        return (hours < 24, {"last_ts": ts, "staleness_hours": hours, "alive": hours < 24})
    except Exception as e:  # noqa: BLE001
        return (False, {"reason": f"error: {str(e)[:80]}"})


def run_radar(omo_dir: Path) -> dict:
    """调 c2g.strategy 真审计,返回 metrics 字典."""
    # 把 c2g src 加进 sys.path (c2g 是 src 布局, 但本脚本不在 c2g venv)
    c2g_src = Path(__file__).resolve().parent.parent / "projects" / "c2g" / "src"
    if c2g_src.is_dir() and str(c2g_src) not in sys.path:
        sys.path.insert(0, str(c2g_src))

    from c2g.strategy import _collect_metrics, _check_anomalies, _list_task_files  # type: ignore[reportMissingImports]  # noqa: PLC0415, E402

    done_files, planned_files = _list_task_files(omo_dir)
    all_files = done_files + planned_files
    total = len(all_files)
    total_done = len(done_files)
    total_planned = len(planned_files)

    metrics = _collect_metrics(all_files)
    pending_metrics = _collect_metrics(planned_files)
    warnings = (
        _check_anomalies(metrics, total, omo_dir=omo_dir, pending_metrics=pending_metrics)
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
    lines.append(f"# health_score: composite (ISC-1) = {report['health_composite_breakdown']['weights']}")
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
    for dim in ("priority_dist", "risk_dist", "owner_dist", "phase_dist", "status_dist"):
        lines.append(f"  {dim}:")
        for k, v in sorted(report[dim].items()):
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


def build_health_projection(omo_dir: Path, output: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Build health.yaml content inputs without writing projection files."""
    ws_root = omo_dir.parent
    report = run_radar(omo_dir)
    now_iso = _utc_now()
    report["generated_at"] = now_iso
    report["source"] = "c2g.strategy (real audit, no mock)"

    governance_anomaly_score = _health_score_from_anomalies(report["anomaly_count"])
    report["governance_anomaly_score"] = governance_anomaly_score

    service_online_ratio, runtime_summary = _collect_runtime_health(ws_root)
    report["service_online_ratio"] = service_online_ratio

    fresh_score, age_desc = _freshness_score(output, now_iso)
    report["freshness_score"] = fresh_score

    feedback_alive, feedback_summary = _collect_feedback_liveness(ws_root)
    report["feedback_liveness"] = feedback_summary

    composite, breakdown = _composite_health_score(
        governance_anomaly_score, service_online_ratio, fresh_score, feedback_alive
    )
    report["health_score"] = composite
    report["health_composite_breakdown"] = breakdown
    return report, runtime_summary, age_desc


def build_system_projection_updates(workspace_root: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Build the whitelisted system.yaml projection fields for health sync."""
    import yaml  # noqa: PLC0415

    service_online_ratio = report.get("service_online_ratio")
    updates: dict[str, Any] = {
        "health_score": int(report["health_score"]),
        "governance_anomaly_score": int(report["governance_anomaly_score"]),
        "service_online_ratio": (
            round(float(service_online_ratio), 4)
            if service_online_ratio is not None
            else None
        ),
        "health_score_source": "compass_radar_composite",
        "health_score_generated_at": report["generated_at"],
    }
    health_yaml = workspace_root / ".omo" / "state" / "system_health.yaml"
    if health_yaml.is_file():
        try:
            omo_src = workspace_root / "projects" / "omo" / "src"
            if str(omo_src) not in sys.path:
                sys.path.insert(0, str(omo_src))
            from omo.omo_state_schema import summarize_system_health_snapshot  # noqa: PLC0415

            health_data = yaml.safe_load(health_yaml.read_text(encoding="utf-8")) or {}
            updates["runtime_health_summary"] = summarize_system_health_snapshot(health_data)
        except Exception as inner:  # noqa: BLE001
            print(f"⚠️  兜底同步 runtime_health_summary 失败: {inner}")
    return updates


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
    print("📊 治理健康分 (ISC-1 复合):")
    print(f"   health_score (composite): {report['health_score']}/100")
    print(f"   governance_anomaly_score: {governance_anomaly_score}/100 (anomalies={report['anomaly_count']})")
    ratio_str = f"{service_online_ratio:.2%}" if service_online_ratio is not None else "unavailable"
    print(f"   service_online_ratio:     {ratio_str}  (online={runtime_summary.get('online_services')}/{runtime_summary.get('total_services')})")
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

    # 同步刷新 system.yaml 的健康分相关字段 (避免 SSOT 偏差告警)
    sync_system_yaml(
        ws_root=ws_root,
        health_score=report["health_score"],
        governance_anomaly_score=governance_anomaly_score,
        service_online_ratio=service_online_ratio,
        generated_at=report["generated_at"],
    )

    # 自动触发 BRIEF.md 生成 (WS-4 + WS-5)
    try:
        import subprocess  # noqa: PLC0415
        res = subprocess.run(
            [sys.executable, str(ws_root / "bin" / "generate-brief.py"), "--write", "--if-changed"],
            cwd=ws_root, capture_output=True, text=True, check=False
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
) -> None:
    """把复合 health_score + governance_anomaly_score + service_online_ratio 写回 .omo/state/system.yaml.

    ISC-2 治本: system.yaml 新增 governance_anomaly_score + service_online_ratio 字段.
    用 ruamel.yaml 失败时回退到 pyyaml (不保留注释但语义正确).
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
            print(f"✅ system.yaml 同步: health_score(composite)={health_score} governance_anomaly={governance_anomaly_score} ratio={service_online_ratio}")
        else:
            print("ℹ system.yaml 语义未变化, 跳过写入")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  system.yaml 同步失败: {e}")


if __name__ == "__main__":
    sys.exit(main())
