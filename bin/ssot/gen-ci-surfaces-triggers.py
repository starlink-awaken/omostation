#!/usr/bin/env python3
"""ci-surfaces workflow_triggers 生成器 (ADR-0381 E-5 补充, ADR-0387).

从 .github/workflows/*.yml 解析实际触发 (on:) 与 paths 过滤,
重建 ci-surfaces.yaml 的 workflow_triggers 段, 使登记 = 实际.

设计约束:
  - 只维护 workflow_triggers 段; surfaces 段 (人工登记的检查工具) 原样保留.
  - 解析正则与 bin/gac/check-ci-surfaces.py 的 check_workflow_trigger_drift
    完全一致 (同一套触发分类: manual/scheduled/per_pr/push/callable),
    保证生成器产出不会被检测器判 drift.
  - 文本级替换 (非 yaml 全量 dump): 保留 surfaces 段注释与格式.

用法:
  python3 bin/ssot/gen-ci-surfaces-triggers.py           # dry-run 报告
  python3 bin/ssot/gen-ci-surfaces-triggers.py --write    # 回写 ci-surfaces.yaml
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
CI_SURFACES = WORKSPACE / ".omo" / "_truth" / "registry" / "ci-surfaces.yaml"
WORKFLOWS_DIR = WORKSPACE / ".github" / "workflows"

# 与 check-ci-surfaces.py 保持一致的触发解析
TRIGGER_RE = {
    "push": re.compile(r"^\s+push:\s*$", re.M),
    "per_pr": re.compile(r"^\s+pull_request:\s*$", re.M),
}
PATHS_RE = re.compile(r"^\s+paths:\s*$((?:\n\s+- [^\n]+)*)", re.M)


def parse_workflow_triggers(text: str) -> tuple[list[str], bool, set[str]]:
    """返回 (triggers, path_filtered, paths). 逻辑与检测器 check_workflow_trigger_drift 相同."""
    triggers: list[str] = []
    if "workflow_call" in text:
        triggers.append("callable")
    if re.search(r"^\s+schedule:\s*$", text, re.M) or "schedule:" in text:
        triggers.append("scheduled")
    if "workflow_dispatch" in text:
        triggers.append("manual")
    if "on: [push, pull_request]" in text or "on: [push,pull_request]" in text:
        triggers += ["push", "per_pr"]
    else:
        if TRIGGER_RE["push"].search(text):
            triggers.append("push")
        if TRIGGER_RE["per_pr"].search(text):
            triggers.append("per_pr")
    path_filtered = bool(re.search(r"^\s+paths:\s*$", text, re.M))
    paths: set[str] = set()
    if path_filtered:
        for m in PATHS_RE.finditer(text):
            for line in m.group(1).split("\n"):
                pm = re.match(r"\s+- (.*)$", line)
                if pm:
                    paths.add(pm.group(1).strip().strip("'\""))
    return sorted(set(triggers)), path_filtered, paths


def render_triggers_entry(workflow: str, triggers: list[str], path_filtered: bool, paths: set[str]) -> list[str]:
    lines = [f"  - workflow: {workflow}"]
    if triggers:
        lines.append(f"    triggers: [{', '.join(triggers)}]")
    if path_filtered:
        lines.append("    path_filtered: true")
        for p in sorted(paths):
            lines.append(f"    paths:")
            break
        for p in sorted(paths):
            lines.append(f"    - {p}")
    else:
        lines.append("    path_filtered: false")
    return lines


def build_workflow_triggers_text() -> str:
    entries: list[str] = []
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="ignore")
        triggers, path_filtered, paths = parse_workflow_triggers(text)
        entries.extend(render_triggers_entry(wf.name, triggers, path_filtered, paths))
    return "\n".join(entries) + "\n"


def rewrite(yaml_path: Path, new_section: str) -> bool:
    """文本级替换 workflow_triggers 段 (保留 surfaces 段原文)."""
    text = yaml_path.read_text(encoding="utf-8")
    marker = "workflow_triggers:"
    idx = text.find(marker)
    if idx == -1:
        print(f"❌ {yaml_path} 缺少 '{marker}' 段", file=sys.stderr)
        return False
    head = text[: idx + len(marker)]
    # 保留原段后续缩进一致性: 统一用生成段替换 marker 之后全部内容
    new_text = head + "\n" + new_section
    yaml_path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    write = "--write" in sys.argv
    new_section = build_workflow_triggers_text()
    text = CI_SURFACES.read_text(encoding="utf-8")
    marker = "workflow_triggers:"
    idx = text.find(marker)
    old_section = text[idx + len(marker) :].lstrip("\n")

    if write:
        if rewrite(CI_SURFACES, new_section):
            print(f"✅ workflow_triggers 已重建 ({CI_SURFACES})")
        return 0

    # dry-run: 对比差异
    print("=== gen-ci-surfaces-triggers dry-run ===")
    print(f"workflows scanned: {len(list(WORKFLOWS_DIR.glob('*.yml')))}")
    print("--- new workflow_triggers ---")
    print(new_section)
    print("--- diff (old → new, 行级) ---")
    old_lines = old_section.strip().splitlines()
    new_lines = new_section.strip().splitlines()
    added = [l for l in new_lines if l not in old_lines]
    removed = [l for l in old_lines if l not in new_lines]
    print(f"added: {len(added)} lines, removed: {len(removed)} lines")
    if added:
        print("  +" + "\n  +".join(added[:20]))
    if removed:
        print("  -" + "\n  -".join(removed[:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
