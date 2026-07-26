#!/usr/bin/env python3
# Status: implemented (P0-5, workorder 2026-07-25)
"""check-doc-claims — 文档测试宣称失真防复发门 (P0-5).

治 "文档宣称 vs 实际漂移" (P0-3 指针化后, 本门退化为禁止裸数字宣称的 lint,
更省事). 防 AGENTS/CLAUDE/INTERFACE 退回裸 "100% 通过" / "NNN tests" 宣称.

rule_id: CR-X4-DOC-CLAIMS

用法:
    python3 bin/mof/check-doc-claims.py --project projects/metaos
    python3 bin/mof/check-doc-claims.py --project projects/metaos --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RULE_ID = "CR-X4-DOC-CLAIMS"

# 裸通过率宣称模式 (100% 通过 / 100% pass)
_BARE_PASS_RE = re.compile(r"100\s*%\s*(通过|pass)", re.IGNORECASE)


def check_interface_tests_has_pointer(interface_text: str) -> list[dict]:
    """INTERFACE.yaml 'tests:' 行必须有 # 指针注释 (as_of/见 pytest).

    裸 'tests: 260' (无注释) = 失真源. P0-3 后须带 as_of/指针.
    """
    findings: list[dict] = []
    for i, line in enumerate(interface_text.splitlines(), 1):
        stripped = line.strip()
        if (
            stripped.startswith("tests:")
            and stripped[6:].strip()
            and "#" not in stripped
        ):
            findings.append(
                {
                    "check": "interface_tests_bare_number",
                    "line": i,
                    "content": stripped,
                    "reason": "tests: 裸数字无 as_of/指针注释 (P0-3)",
                }
            )
    return findings


def check_no_bare_pass_claim(md_text: str, filename: str = "") -> list[dict]:
    """AGENTS/CLAUDE 禁止裸 '100% 通过' 宣称 (须指针化: 见 pytest 实跑)."""
    findings: list[dict] = []
    for i, line in enumerate(md_text.splitlines(), 1):
        if _BARE_PASS_RE.search(line):
            findings.append(
                {
                    "check": "bare_pass_claim",
                    "file": filename,
                    "line": i,
                    "content": line.strip(),
                    "reason": "裸 100% 通过宣称 (P0-3 指针化, 见 pytest 实跑)",
                }
            )
    return findings


def detect_doc_claim_drift(project_dir: Path) -> dict:
    """聚合 project 文档宣称检查 (INTERFACE tests 指针 + AGENTS/CLAUDE 裸通过率)."""
    findings: list[dict] = []
    interface = project_dir / "INTERFACE.yaml"
    if interface.exists():
        findings += check_interface_tests_has_pointer(
            interface.read_text(encoding="utf-8")
        )
    for md_name in ("AGENTS.md", "CLAUDE.md"):
        md = project_dir / md_name
        if md.exists():
            findings += check_no_bare_pass_claim(
                md.read_text(encoding="utf-8"), md_name
            )
    try:
        proj_rel = str(project_dir.resolve().relative_to(REPO))
    except ValueError:
        proj_rel = str(project_dir)
    return {
        "rule_id": RULE_ID,
        "project": proj_rel,
        "total_findings": len(findings),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="文档测试宣称失真防复发门 (P0-5, workorder 2026-07-25)"
    )
    parser.add_argument(
        "--project", default="projects/metaos", help="项目目录 (相对 repo root)"
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    project_dir = (REPO / args.project).resolve()
    result = detect_doc_claim_drift(project_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== 文档宣称失真防复发门 ({RULE_ID}, project={args.project}) ===\n")
        if not result["findings"]:
            print("✅ 无裸数字宣称 — 文档已指针化")
        else:
            for f in result["findings"]:
                print(f"🔴 {f['check']}: {f}")
        print(f"\nTotal: {result['total_findings']} findings")
    return 1 if result["total_findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
