#!/usr/bin/env python3
r"""doc-claim-lint: 检测导航文档自由文本里的运行时事实声称 (治本 D 类文档漂移, ISC-18).

治本动机 (元根因 1): doc-ssot-lint 只检查 marker 段内的 embedded table, 不检查
导航文档 (INVENTORY/PANORAMA/ssot-7-domain) 自由文本里声称的版本号/健康分/计数/
目录名. 缝隙里 "文档声称 vs SSOT 真值" 无人监督 → INVENTORY 写 mof-version v0.0.12
(实际 v0.0.107, 漂移 95 版本) 不会触发任何 lint (审计 D1-D6 根因).

本检测器扫导航文档自由文本, 匹配 "运行时事实声称" pattern, 命中要求改指针.

pattern (基于审计 D1-D6):
  - PROJECTS\.yaml         → 死链 (D1, 真 SSOT 是 docs/project-registry.yaml)
  - mof.version\s+v\d+\.\d+ → 版本号硬编码 (D2, 应指针 _truth/mof-version.yaml)
  - tasks/active/          → 旧目录名 (D3, 实际 tasks/planned/)
  - \b100\s*A\+            → 健康分声称 (应指针 _truth/ 或 state/)
  - phase\s+\d+(?!.*→)     → phase 硬编码 (易漂移, 应指针 system.yaml::current_phase)

用法:
  python bin/ssot/doc-claim-lint.py                # 扫默认 targets, 命中 exit 1
  python bin/ssot/doc-claim-lint.py --json         # JSON 输出 (CI 友好)
  python bin/ssot/doc-claim-lint.py --target <f>   # 扫指定文件
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# 默认 targets: 导航文档 (审计 D1-D6 实证位置)
DEFAULT_TARGETS = [
    ".omo/_truth/INVENTORY.md",
    ".omo/standards/ssot-7-domain-schema.md",
    "docs/PANORAMA.md",
    "docs/ARCHITECTURE-DETAILED-MAP.md",
    "docs/FUNCTIONAL-CAPABILITY-MAP.md",
]

# pattern → (id, 描述, 建议指针)
PATTERNS = [
    {
        "id": "DEAD-LINK-PROJECTS-YAML",
        "regex": re.compile(r"PROJECTS\.yaml"),
        "desc": "死链: PROJECTS.yaml 不存在 (审计 D1)",
        "fix": "改向 docs/project-registry.yaml",
    },
    {
        "id": "HARDCODED-MOF-VERSION",
        "regex": re.compile(r"mof.?version\s+v?\d+\.\d+(?:\.\d+)?", re.IGNORECASE),
        "desc": "版本号硬编码 (审计 D2: 漂移 95 版本)",
        "fix": "改指针: 见 .omo/_truth/mof-version.yaml",
    },
    {
        "id": "STALE-DIR-TASKS-ACTIVE",
        "regex": re.compile(r"tasks/active/?"),
        "desc": "旧目录名 (审计 D3: 实际是 tasks/planned/)",
        "fix": "改向 tasks/planned/",
    },
    {
        "id": "HARDCODED-HEALTH-SCORE",
        "regex": re.compile(r"\b100\s*A\+"),
        "desc": "健康分硬编码声称 (易漂移)",
        "fix": "改指针: 见 .omo/state/health.yaml",
    },
    {
        "id": "HARDCODED-PHASE",
        "regex": re.compile(r"(?<!\w)phase\s+\d{1,3}\b(?!\s*→|\s*=|\s*:)"),
        "desc": "phase 数字硬编码 (current_phase 易漂移)",
        "fix": "改指针: 见 .omo/state/system.yaml::current_phase",
    },
]

# 白名单: 某些上下文里 phase 数字是合法的 (如 "Phase 1→8" 范围、历史记录)
ALLOW_CONTEXT = re.compile(r"(Phase|phase)\s+\d+\s*→\s*\d+|历史|归档|archive|historical", re.IGNORECASE)


def scan_file(path: Path) -> list[dict]:
    """扫单文件, 返回命中列表 [{file, line, column, pattern_id, matched, context, fix}]."""
    if not path.is_file():
        return []
    findings: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pat in PATTERNS:
            for m in pat["regex"].finditer(line):
                # 白名单: phase 范围/历史上下文跳过
                if pat["id"] == "HARDCODED-PHASE" and ALLOW_CONTEXT.search(line):
                    continue
                findings.append({
                    "file": str(path.relative_to(WORKSPACE)) if path.is_absolute() else str(path),
                    "line": lineno,
                    "column": m.start() + 1,
                    "pattern_id": pat["id"],
                    "matched": m.group(0),
                    "context": line.strip()[:120],
                    "fix": pat["fix"],
                })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="doc-claim-lint: 导航文档运行时事实声称检测 (ISC-18)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--target", action="append", help="指定 target (可多次, 默认 5 个导航文档)")
    args = parser.parse_args()

    targets = args.target or DEFAULT_TARGETS
    all_findings: list[dict] = []
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = WORKSPACE / t
        all_findings.extend(scan_file(p))

    if args.json:
        print(json.dumps({"findings": all_findings, "count": len(all_findings)}, indent=2, ensure_ascii=False))
    else:
        if not all_findings:
            print(f"✅ doc-claim-lint: 0 命中 (扫描 {len(targets)} 个导航文档, 无运行时事实声称漂移)")
            return 0
        print(f"❌ doc-claim-lint: 检测到 {len(all_findings)} 项导航文档运行时事实声称:\n")
        by_pattern: dict[str, list[dict]] = {}
        for f in all_findings:
            by_pattern.setdefault(f["pattern_id"], []).append(f)
        for pid, items in by_pattern.items():
            print(f"  ⚠️  {pid} ({len(items)}): {items[0]['fix']}")
            for it in items[:5]:
                rel = it["file"]
                print(f"     - {rel}:{it['line']} '{it['matched']}' ← {it['context'][:80]}")
            if len(items) > 5:
                print(f"     ... 及其他 {len(items)-5} 处")
        print(f"\n治本: 把硬编码声称改为 SSOT 指针 (见 .omo/standards/doc-ssot-contract.md)")
        return 1

    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())
