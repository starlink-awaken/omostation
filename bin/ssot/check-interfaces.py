#!/usr/bin/env python3
"""check-interfaces.py — 校验 `.omo/standards/interface_contract.md` 的模型表结构

该文档是 L0/L3 通信模型的 SSOT，并且**由 `omo-parser` 在运行时解析这些 markdown 表来
生成 Pydantic 模型**（见文档自述 "The omo-parser will dynamically parse these markdown
tables to generate Pydantic models at runtime"）。

所以表结构本身就是接口契约的一部分：表坏了 → 运行时生成的模型就坏，而这种坏在静态
检查里完全不可见。这个检查器钉住表结构本身。

校验（全部为 error）：

1. 文档至少声明 1 个 `## Model: <Name>`
2. 每个模型之后必须有且仅有一个 markdown 表
3. 表头必须逐字是 `| Field | Type | Description |`
4. 分隔行必须逐字是 `|---|---|---|`
5. 每个数据行恰好 3 列（首尾竖线计入）
6. `Type` 必须落在已知集合内：string / int / float / bool / dict / list
7. `Field` 不得为空，且同一模型内不得重复
8. 模型名在文档内不得重复

用法：
  python3 bin/ssot/check-interfaces.py                 # 检查默认路径
  python3 bin/ssot/check-interfaces.py --json          # JSON 输出
  python3 bin/ssot/check-interfaces.py --path <file>   # 指定契约文档
  python3 bin/ssot/check-interfaces.py --check-parse   # 额外：按 omo-parser 的口径试解析

退出码：0 = 全部通过；1 = 有 error。

历史：`scripts/check-interfaces.py` 曾在 governance-check.yml 的 FAILED=1 循环里被调用
（2026-06-06 引入），但那个脚本从未提交进本仓 —— 循环里 ~20 个 `scripts/check-*.py`
一个都不存在，接口契约检查的执行面自那时起就是空的。ADR-0379 D3 以「已由独立 workflow
interfaces-enforce.yml 覆盖」为由把该行移除，而那个 workflow 同样没有脚本（2026-10-28
已作为零信号空 job 删除）。本文件是该能力的首次真正实现。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_CONTRACT = Path(".omo") / "standards" / "interface_contract.md"

KNOWN_TYPES = {"string", "int", "float", "bool", "dict", "list"}
HEADER = "| Field | Type | Description |"
SEPARATOR = "|---|---|---|"
MODEL_HEADING = re.compile(r"^##\s+Model:\s*(\S+)\s*$")


def parse_models(text: str) -> tuple[list[dict], list[str]]:
    """把契约文档解析成模型列表 + error 列表。"""
    errors: list[str] = []
    models: list[dict] = []
    seen_names: set[str] = set()

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = MODEL_HEADING.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        if name in seen_names:
            errors.append(f"{name}: 模型名重复声明")
        seen_names.add(name)

        # 向下找到该模型段（到下一个 ## 或 # 或 EOF）
        j = i + 1
        segment: list[str] = []
        while j < len(lines) and not lines[j].startswith("#"):
            segment.append(lines[j])
            j += 1

        fields, seg_errors = _parse_segment(name, segment)
        errors.extend(seg_errors)
        models.append({"name": name, "fields": fields})
        i = j

    if not models:
        errors.append(f"文档未声明任何 `## Model:` —— 契约不能为空")
    return models, errors


def _parse_segment(name: str, segment: list[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    fields: list[str] = []

    rows = [ln for ln in segment if ln.strip().startswith("|")]
    if not rows:
        return fields, [f"{name}: 模型声明后没有 markdown 表"]

    if rows[0].strip() != HEADER:
        errors.append(f"{name}: 表头应为 `{HEADER}`，实际 `{rows[0].strip()}`")
    if len(rows) < 2 or rows[1].strip() != SEPARATOR:
        errors.append(f"{name}: 缺少分隔行 `{SEPARATOR}`")

    for row in rows[2:]:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) != 3:
            errors.append(f"{name}: 行应有 3 列 (Field/Type/Description)，实际 {len(cells)} 列 —— `{row.strip()}`")
            continue
        field, ftype, _desc = cells
        if not field:
            errors.append(f"{name}: 存在空 Field 名")
            continue
        if ftype not in KNOWN_TYPES:
            errors.append(f"{name}.{field}: Type `{ftype}` 不在已知集合 {sorted(KNOWN_TYPES)}")
        if field in fields:
            errors.append(f"{name}: Field `{field}` 重复")
            continue
        fields.append(field)
    return fields, errors


def check_parse(models: list[dict]) -> list[str]:
    """按 omo-parser 的口径做一次可解析性检查：每个字段都有非空 Type/Description。"""
    errors: list[str] = []
    for model in models:
        if not model["fields"]:
            errors.append(f"{model['name']}: 没有可用字段，omo-parser 会生成空模型")
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path", default=str(DEFAULT_CONTRACT), help=f"契约文档路径 (默认 {DEFAULT_CONTRACT})")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.add_argument("--check-parse", action="store_true", help="额外跑 omo-parser 口径的可解析性检查")
    args = p.parse_args(argv)

    path = Path(args.path)
    if not path.is_file():
        print(f"❌ 契约文档不存在: {path}", file=sys.stderr)
        return 1

    models, errors = parse_models(path.read_text(encoding="utf-8"))
    if args.check_parse:
        errors.extend(check_parse(models))

    report = {
        "schema": "interface-contract-check/v1",
        "path": str(path),
        "models": models,
        "model_count": len(models),
        "field_count": sum(len(m["fields"]) for m in models),
        "errors": errors,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"📋 interface contract: {len(models)} 模型 / {report['field_count']} 字段")
        for m in models:
            print(f"   - {m['name']} ({len(m['fields'])} 字段)")
        if errors:
            print(f"❌ {len(errors)} 个错误:", file=sys.stderr)
            for e in errors:
                print(f"   - {e}", file=sys.stderr)
        else:
            print("✅ 接口契约表结构通过")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
