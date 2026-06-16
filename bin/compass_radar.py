#!/usr/bin/env python3
"""compass-radar: 调 c2g.strategy 真实审计 + 写治理健康分 SSOT.

不重写 radar 逻辑,直接 import c2g.strategy 的真审计函数
(strategy_audit/_check_anomalies/_collect_metrics),
捕获 print 输出 + 解析异常数量,算 health_score,落 .omo/state/health.yaml.

health_score 映射:
  0 异常 → 100
  1 异常 → 85
  2 异常 → 70
  3 异常 → 55
  4 异常 → 40
  ≥5 异常 → 25 (熔断: 治理停滞, 需人工介入)

用法:
  python scripts/compass_radar.py
  python scripts/compass_radar.py --output .omo/state/health.yaml
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _health_score_from_anomalies(anomaly_count: int) -> int:
    """根据异常数量映射 health_score (0-100, 越高越健康)."""
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
    warnings = _check_anomalies(metrics, total) if total else []
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
    lines.append(f"# source: c2g.strategy (real audit, no mock)")
    lines.append(f"# range: 0-100, higher = healthier")
    lines.append("")
    lines.append("generated_at: " + _yaml_str(report["generated_at"]))
    lines.append("source: " + _yaml_str(report["source"]))
    lines.append("health_score: " + str(report["health_score"]))
    lines.append("anomaly_count: " + str(report["anomaly_count"]))
    lines.append("total_tasks: " + str(report["total_tasks"]))
    lines.append("done: " + str(report["done"]))
    lines.append("planned: " + str(report["planned"]))
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


def _yaml_str(s: str) -> str:
    """简化版 YAML 字符串转义 (假设 s 不含特殊控制字符)."""
    # 去掉 emoji (yaml 不喜欢)
    safe = s.replace("⚠️", "[WARN]").replace("✅", "[OK]")
    # 双引号包裹, 转义内部 "
    return '"' + safe.replace('"', '\\"') + '"'


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

    output = args.output or (omo_dir / "state" / "health.yaml")
    output = output.resolve()

    print(f"🧭 compass-radar → {omo_dir}")
    print(f"   output: {output}")

    report = run_radar(omo_dir)
    report["generated_at"] = _utc_now()
    report["source"] = "c2g.strategy (real audit, no mock)"
    report["health_score"] = _health_score_from_anomalies(report["anomaly_count"])

    print()
    print("📊 治理健康分:")
    print(f"   health_score: {report['health_score']}/100")
    print(f"   anomalies:    {report['anomaly_count']}")
    print(f"   total:        {report['total_tasks']} ({report['done']} done + {report['planned']} planned)")
    if report["anomalies"]:
        print("🚨 异常告警:")
        for w in report["anomalies"]:
            print(f"   - {w.replace('⚠️ ', '')}")
    else:
        print("✅ 无异常")

    if args.dry_run:
        print()
        print("🔍 [dry-run] 不写文件, 仅打印")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_yaml(report), encoding="utf-8")

    # 同步刷新 system.yaml 的健康分相关字段 (避免 SSOT 偏差告警)
    sync_system_yaml(ws_root=omo_dir.parent, health_score=report["health_score"], generated_at=report["generated_at"])

    print()
    print(f"✅ 已写入 {output}")
    return 0


def sync_system_yaml(ws_root: Path, health_score: int, generated_at: str) -> None:
    """把 health_score + generated_at 同步写回 .omo/state/system.yaml.

    用 ruamel.yaml 失败时回退到 pyyaml (不保留注释但语义正确).
    """
    import yaml  # noqa: PLC0415

    system_yaml = ws_root / ".omo" / "state" / "system.yaml"
    if not system_yaml.is_file():
        print(f"⚠️  system.yaml 不存在: {system_yaml}, 跳过同步")
        return

    try:
        data = yaml.safe_load(system_yaml.read_text(encoding="utf-8"))
        data["health_score"] = int(health_score)
        data["health_score_generated_at"] = generated_at
        # 原子写
        tmp = system_yaml.with_suffix(".yaml.tmp")
        tmp.write_text(
            yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        tmp.replace(system_yaml)
        print(f"✅ system.yaml 同步: health_score={health_score} @ {generated_at}")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  system.yaml 同步失败: {e}")


if __name__ == "__main__":
    sys.exit(main())
