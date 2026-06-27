#!/usr/bin/env python3
"""gen-project-registry — registry vs 实际代码 drift 检测 (doc-ssot 第4步).

检测 docs/project-registry.yaml 的 version/python 是否与 projects/*/pyproject.toml 漂移.

SSOT 链闭环:
  实际代码 (pyproject.toml)  →  本工具检测  →  registry.yaml  →  doc-ssot-lint 检测  →  markdown
  (事实源)                       (registry drift)  (SSOT)            (硬编码冲突)          (引用层)

doc-ssot-lint 只覆盖 registry → markdown; 本工具覆盖 代码 → registry (补齐 SSOT 链).

用法:
  python3 bin/gen-project-registry.py           # 检测 drift, 有漂移返回 1
  python3 bin/gen-project-registry.py --write    # 修复 registry version/python
  python3 bin/gen-project-registry.py --json     # 机器可读 JSON (gac-healthcheck 消费)

退出码:
  0 = 无 drift
  1 = 有 drift (registry 与 pyproject.toml 不一致)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib  # Python 3.11+ 内置
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY = WORKSPACE / "docs" / "project-registry.yaml"
PROJECTS_DIR = WORKSPACE / "projects"


def load_registry_projects() -> dict:
    """加载 registry projects 段 (多文档 strip frontmatter)."""
    import yaml

    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    if not docs:
        return {}
    return docs[-1].get("projects", {})


def scan_pyprojects() -> dict:
    """扫描 projects/*/pyproject.toml, 返回 {proj_name: {version, python}}."""
    result: dict[str, dict] = {}
    for proj_dir in sorted(PROJECTS_DIR.iterdir()):
        if not proj_dir.is_dir():
            continue
        pyproj = proj_dir / "pyproject.toml"
        if not pyproj.exists():
            continue  # TS/Docker 项目无 pyproject.toml, 跳过
        try:
            with open(pyproj, "rb") as f:
                data = tomllib.load(f)
            proj_meta = data.get("project", {})
            version = proj_meta.get("version")
            python = proj_meta.get("requires-python")
            if version or python:
                result[proj_dir.name] = {"version": version, "python": python}
        except (tomllib.TOMLDecodeError, OSError):
            continue
    return result


def detect_drift(registry_projects: dict, actual: dict) -> list[dict]:
    """检测 drift. 返回 [{project, field, registry, actual}]."""
    drifts: list[dict] = []
    for name, actual_info in actual.items():
        reg = registry_projects.get(name, {})
        for field in ("version", "python"):
            reg_val = reg.get(field)
            act_val = actual_info.get(field)
            if act_val is None:
                continue
            if reg_val and reg_val != act_val:
                drifts.append(
                    {
                        "project": name,
                        "field": field,
                        "registry": reg_val,
                        "actual": act_val,
                    }
                )
    return drifts


def run_check(as_json: bool = False) -> int:
    registry_projects = load_registry_projects()
    actual = scan_pyprojects()
    drifts = detect_drift(registry_projects, actual)

    if as_json:
        payload = {
            "ok": len(drifts) == 0,
            "drift_count": len(drifts),
            "projects_scanned": len(actual),
            "drifts": drifts,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1

    if drifts:
        print(f"❌ 检测到 {len(drifts)} 项 registry drift (vs pyproject.toml):\n")
        for d in drifts:
            print(
                f"  {d['project']}.{d['field']}: registry={d['registry']} → 实际={d['actual']}"
            )
        print()
        print("修复: python3 bin/gen-project-registry.py --write")
        return 1

    print(f"✅ registry version/python 无 drift (扫描 {len(actual)} 项目 vs pyproject.toml)")
    return 0


def write_fixes(drifts: list[dict]) -> int:
    """修复 registry drift (--write). 按项目块精确定位 (防多项目同 version 改错)."""
    if not drifts:
        print("无 drift 需修复")
        return 0

    content = REGISTRY.read_text(encoding="utf-8")
    fixed = 0

    for d in drifts:
        proj = d["project"]
        field = d["field"]
        old_val = d["registry"]
        new_val = d["actual"]

        # 按项目块定位 (从 "  proj:" 到下一个 2 空格缩进段或顶层段)
        proj_pat = re.compile(rf"^  {re.escape(proj)}:\s*$", re.MULTILINE)
        match = proj_pat.search(content)
        if not match:
            print(f"  ⚠️  {proj}: 未找到项目块, 跳过")
            continue

        block_start = match.end()
        remainder = content[block_start:]
        next_block = re.search(r"\n  [a-z][\w-]*:\s*$|\n[a-z#]", remainder)
        block_end = block_start + (next_block.start() if next_block else len(remainder))
        block = content[block_start:block_end]

        old_line = f'    {field}: "{old_val}"'
        new_line = f'    {field}: "{new_val}"'
        if old_line in block:
            new_block = block.replace(old_line, new_line, 1)
            content = content[:block_start] + new_block + content[block_end:]
            fixed += 1
            print(f"  ✅ {proj}.{field}: {old_val} → {new_val}")
        else:
            print(f"  ⚠️  {proj}.{field}: 块内未找到 '{old_line}', 跳过")

    if fixed > 0:
        REGISTRY.write_text(content, encoding="utf-8")
    print(f"\n修复 {fixed}/{len(drifts)} 项")
    return fixed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="registry vs 实际代码 drift 检测 (doc-ssot 第4步)"
    )
    parser.add_argument("--write", action="store_true", help="修复 registry drift")
    parser.add_argument("--json", action="store_true", help="机器可读 JSON")
    args = parser.parse_args()

    if args.write:
        registry_projects = load_registry_projects()
        actual = scan_pyprojects()
        drifts = detect_drift(registry_projects, actual)
        write_fixes(drifts)
        return 0

    return run_check(as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
