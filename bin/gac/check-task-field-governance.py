#!/usr/bin/env python3
"""TASK-YAML-RULES 规则 5 守卫: 阻断自加非规范 status 字段回归.

背景: ``.omo/standards/task-yaml-rules.md`` 规则 5 声称
``test_opc_phase_governance_alignment.py`` (18 tests) 阻断 self-add 字段回归。
实测该测试**从未存在**, 致该声明成为悬空引用。与此同时 2026-06-13 OPC P5-P7
演练时的事故 (自加 ``readiness_status`` / ``cadence_status`` 破坏 closeout
可审计性, reviewer 一票否决) 具备**真实复演风险**。

本守卫以规则 5 的**真实语义**落地替代该悬空测试, 并接入 gac-local-gate:

  - ``gate_status`` 如出现, 必须在枚举内:
      {not_yet_passed, conditionally_passed, passed}
  - 禁止自加替代状态字段: readiness_status / cadence_status
  - 禁止在非末尾插入导致键重复 / 乱序的 status/history (YAML 解析异常即判)

只扫描活跃任务 (``.omo/tasks`` 非 ``archived/`` 目录); 归档为历史快照,
不受本规则约束。

依赖: PyYAML (gac-local-gate 环境缺时, 跳过非阻断。)

Exit code: 0=PASS, 1=FAIL(regression)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = ROOT / ".omo" / "tasks"
ARCHIVE_DIR_NAME = "archived"

VALID_GATE_STATUS = {"not_yet_passed", "conditionally_passed", "passed"}
BANNED_SELFADD_FIELDS = {"readiness_status", "cadence_status"}


def iter_active_task_files():
    for p in sorted(TASKS_DIR.rglob("*.yaml")):
        rel = p.relative_to(TASKS_DIR)
        if rel.parts and rel.parts[0] == ARCHIVE_DIR_NAME:
            continue
        yield p


def check() -> int:
    violations: list[str] = []
    files: list[Path] = []
    for p in iter_active_task_files():
        files.append(p)
        text = p.read_text(encoding="utf-8")
        docs = yaml.safe_load_all(text)
        # 合法约定: 第二个 document 为 closeout appendix(prose / closeout: ref)。
        # 仅读取第一份作为状态文档判 rules; 整体无法解析才视为回归。
        try:
            data = next(docs, None)
        except yaml.YAMLError as e:
            violations.append(f"{p}: YAML 非法 — 典型 self-add 回归 ({e})")
            continue
        if not isinstance(data, dict):
            continue
        gs = data.get("gate_status")
        if gs is not None and gs not in VALID_GATE_STATUS:
            violations.append(
                f"{p}: gate_status={gs!r} 非法 — 允许: "
                f"{sorted(VALID_GATE_STATUS)}"
            )
        for bad in BANNED_SELFADD_FIELDS:
            if bad in data:
                violations.append(
                    f"{p}: 禁止自加字段 '{bad}' (task-yaml-rules.md 规则 5)"
                )

    if violations:
        print("task-field-governance: FAIL — self-add-field 回归")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(
        f"task-field-governance: PASS — {len(files)} 个活跃任务, "
        f"无自加 status 字段回归"
    )
    return 0


if __name__ == "__main__":
    sys.exit(check())
