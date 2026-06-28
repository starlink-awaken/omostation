#!/usr/bin/env python3
"""check-health-ssot: 校验 health_score SSOT 引用一致性 + 保鲜.

不生成 health.yaml (那是 compass_radar.py 的活), 只校验:
  1. system.yaml 的 health_score_ref 指向的文件存在
  2. health.yaml 的 generated_at 在 24h 内 (保鲜)
  3. health.yaml 的 health_score 与 system.yaml 的 health_score 数值一致

用法:
  python3 scripts/check_health_ssot.py
  pre-commit:  走 .pre-commit-config.yaml 的 local hook
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _parse_ts(s: object) -> datetime | None:
    """容忍 ISO 字符串 / datetime 对象."""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s
    if isinstance(s, str):
        s2 = s.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s2)
        except ValueError:
            return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="check-health-ssot: 校验 health_score SSOT 引用")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Workspace 根 (默认自动探测)",
    )
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=24,
        help="health.yaml 保鲜阈值 (小时, 默认 24)",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="只警告, 不阻断 (用于本地调试)",
    )
    args = parser.parse_args()

    ws = args.workspace.resolve()
    system_yaml = ws / ".omo" / "state" / "system.yaml"
    if not system_yaml.is_file():
        print(f"⚠️  system.yaml 不存在: {system_yaml}", file=sys.stderr)
        return 1

    import yaml  # noqa: PLC0415

    sys_data = yaml.safe_load(system_yaml.read_text(encoding="utf-8"))
    ref = sys_data.get("health_score_ref")
    sys_score = sys_data.get("health_score")
    sys_gen = sys_data.get("health_score_generated_at")

    errors: list[str] = []
    warnings: list[str] = []

    # 1. 引用字段存在?
    if not ref:
        errors.append("system.yaml 缺 health_score_ref 字段")
        return _report(errors, warnings, args.warn_only)

    # 2. 引用文件存在?
    ref_path = (ws / ref).resolve()
    if not ref_path.is_file():
        errors.append(f"health_score_ref 指向的文件不存在: {ref_path}")
        return _report(errors, warnings, args.warn_only)

    # 3. health.yaml 可解析?
    try:
        health = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        errors.append(f"health.yaml 解析失败: {e}")
        return _report(errors, warnings, args.warn_only)

    h_score = health.get("health_score")
    h_gen = health.get("generated_at")

    # 4. 数值一致?
    if sys_score is None or h_score is None:
        errors.append("system.yaml 或 health.yaml 缺 health_score 数值")
    elif sys_score != h_score:
        errors.append(
            f"health_score 不一致: system.yaml={sys_score} vs health.yaml={h_score}"
        )

    # 5. 保鲜检查 (健康分必须 24h 内)
    h_gen_dt = _parse_ts(h_gen)
    if h_gen_dt is None:
        warnings.append(f"health.yaml generated_at 无法解析: {h_gen!r}")
    else:
        age = datetime.now(UTC) - h_gen_dt
        if age > timedelta(hours=args.max_age_hours):
            errors.append(
                f"health.yaml 已过期 {age.total_seconds() / 3600:.1f}h "
                f"(阈值 {args.max_age_hours}h). 跑 python3 bin/compass_radar.py 刷新"
            )
        else:
            print(f"✅ health.yaml 保鲜: {age.total_seconds() / 3600:.1f}h 前生成 (阈值 {args.max_age_hours}h)")

    # 6. sys_gen 与 h_gen 一致 (允许 1 分钟时钟漂移)
    sys_gen_dt = _parse_ts(sys_gen)
    if sys_gen_dt and h_gen_dt:
        drift = abs((sys_gen_dt - h_gen_dt).total_seconds())
        if drift > 60:
            warnings.append(
                f"system.yaml.health_score_generated_at 与 health.yaml.generated_at "
                f"偏差 {drift:.0f}s, 建议重新跑 compass_radar.py"
            )

    # 7. 全文档 SSOT 扫描 (CR-ENG-SSOT-POINTER-01)
    # 扫 README/CLAUDE/CHANGELOG 的 health 数字硬编码, 比对 system.yaml.
    # 防失序 (复盘案例: health 曾在 system/CLAUDE/Kim 报告 3 处不同值 77.5/22/67).
    import re  # noqa: PLC0415

    doc_files = ["README.md", "CLAUDE.md", "CHANGELOG.md"]
    health_patterns = [
        r"health-(\d+(?:\.\d+)?)%2F\d+",      # badge: health-NN%2F100
        r"health_score[:\s]+(\d+(?:\.\d+)?)",  # health_score: NN
        r"健康分[:\s]*(\d+(?:\.\d+)?)/100",   # 健康分 NN/100
        r"Health[:\s]+(\d+(?:\.\d+)?)/100",   # Health NN/100
    ]
    for doc_name in doc_files:
        doc_path = ws / doc_name
        if not doc_path.is_file():
            continue
        content = doc_path.read_text(encoding="utf-8")
        for pattern in health_patterns:
            for m in re.finditer(pattern, content):
                doc_score = float(m.group(1))
                if sys_score is not None and doc_score != float(sys_score):
                    warnings.append(
                        f"{doc_name}: health={doc_score} != system.yaml={sys_score} "
                        f"(硬编码过期? 改 SSOT 指针或更新, CR-ENG-SSOT-POINTER-01)"
                    )

    return _report(errors, warnings, args.warn_only)


def _report(errors: list[str], warnings: list[str], warn_only: bool) -> int:
    print(f"📊 health_score: {errors == [] and warnings == []}")
    if errors:
        print(f"❌ {len(errors)} 个错误:")
        for e in errors:
            print(f"   - {e}")
    if warnings:
        print(f"⚠️  {len(warnings)} 个警告:")
        for w in warnings:
            print(f"   - {w}")
    if errors and not warn_only:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
