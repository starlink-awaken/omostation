#!/usr/bin/env python3
# Status: implemented (P0-5, workorder 2026-07-25)
# 定位 (P0-A 核实 2026-07-28): BLOCKING — exit 1 on any finding (见 main L118). 但 scope 受限:
#   default --project=projects/metaos (P0-5 workorder 只针对 metaos). SGF gate 调用未传 --project,
#   故仅扫 metaos 一处. 实测 6 project 漏过: agora/cockpit/ecos/kairon/omo/runtime 的
#   INTERFACE.yaml 'tests:' 行裸数字 (1112/498/859/1810+/400+/175, 无 as_of 指针).
#   送卡 DEBT-DOC-CLAIMS-SCOPE: 扩 --project all + 6 INTERFACE 补 as_of 指针.
#   时间表: Stage B 首月内 (配合 P0-D as_of 指针化一并做). 前置: 无.
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


def _scan_all_projects() -> dict:
    """扫所有含 INTERFACE/AGENTS/CLAUDE 的 project, 聚合 findings (P0-A scope=all, 2026-07-28).

    治 doc-claims gate 默认只扫 metaos 的 scope 漏洞 (DEBT DOC_CLAIMS_SCOPE):
    6 project INTERFACE tests 裸数字曾从门禁漏过. default=all 让 gate 全覆盖.
    """
    all_findings: list[dict] = []
    projects_scanned = 0
    for proj_dir in sorted((REPO / "projects").iterdir()):
        if not proj_dir.is_dir():
            continue
        has_target = any(
            (proj_dir / f).exists() for f in ("INTERFACE.yaml", "AGENTS.md", "CLAUDE.md")
        )
        if not has_target:
            continue
        projects_scanned += 1
        r = detect_doc_claim_drift(proj_dir)
        for f in r["findings"]:
            f["project"] = r["project"]
            all_findings.append(f)
    return {
        "rule_id": RULE_ID,
        "scope": "all",
        "projects_scanned": projects_scanned,
        "total_findings": len(all_findings),
        "findings": all_findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="文档测试宣称失真防复发门 (P0-5; scope=all P0-A 2026-07-28)"
    )
    parser.add_argument(
        "--project",
        default="all",
        help="项目目录 (相对 repo root) 或 'all' (默认, 扫全 project — 治 DOC_CLAIMS_SCOPE)",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.project == "all":
        result = _scan_all_projects()
        scope_label = f"scope=all ({result['projects_scanned']} projects)"
    else:
        project_dir = (REPO / args.project).resolve()
        result = detect_doc_claim_drift(project_dir)
        scope_label = f"project={args.project}"
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== 文档宣称失真防复发门 ({RULE_ID}, {scope_label}) ===\n")
        if not result["findings"]:
            print("✅ 无裸数字宣称 — 文档已指针化")
        else:
            for f in result["findings"]:
                print(f"🔴 {f['check']}: {f}")
        print(f"\nTotal: {result['total_findings']} findings")
    return 1 if result["total_findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
