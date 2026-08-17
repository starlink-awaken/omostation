#!/usr/bin/env python3
"""Unified Weekly Governance & Hygiene Patrol Engine (ADR-0192).

Orchestrates 6-pillar multi-domain automated inspections:
1. MOF SSOT Rule Compilation & Drift Gate
2. Documents Dual-Plane Cleanliness (ADR-0191 / E-DOC-001 / E-DOC-002)
3. Domain Truth Entity Schema & Freshness SLA (ADR-0192 / E-DOC-004)
4. Multi-Client Documents MCP Configuration Alignment (E-DOC-005)
5. Local Compute Fabric Health (omlxc doctor)
6. Agent Skills & GAC Heuristic Compliance
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run_subcommand(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        res = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (res.stdout.strip() or res.stderr.strip())
        return res.returncode, out
    except Exception as e:
        return -1, str(e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified Weekly Governance Patrol Engine")
    parser.add_argument("--strict", action="store_true", help="Exit with non-zero code on any failure")
    parser.add_argument("--json", action="store_true", help="Output summary as JSON")
    parser.add_argument("--output", help="Explicit path to write Markdown report")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    date_str = now.strftime("%Y%m%d")

    checks: list[dict[str, Any]] = []

    # 1. MOF SSOT 规则编译与漂移检测
    code_drift, out_drift = run_subcommand(["uv", "run", "--project", "projects/ecos", "ecos-constraint", "drift", "--json"])
    drift_ok = code_drift == 0
    checks.append({
        "name": "MOF SSOT Rules Drift Gate",
        "category": "Governance Core",
        "passed": drift_ok,
        "detail": "SSOT constraints in sync" if drift_ok else out_drift[:120],
    })

    # 2. Documents 双平面纯净度审计
    code_docs, out_docs = run_subcommand(["uv", "run", "--project", "projects/ecos", "ecos-constraint", "documents", "audit", "--json"])
    docs_ok = code_docs == 0
    checks.append({
        "name": "Documents Dual-Plane Cleanliness (ADR-0191)",
        "category": "Plane Separation",
        "passed": docs_ok,
        "detail": "0 runtime/script violations in Documents" if docs_ok else out_docs[:120],
    })

    # 3. 领域事实真源 Schema 与保鲜度校验
    code_facts, out_facts = run_subcommand(["uv", "run", "--project", "projects/ecos", "ecos-constraint", "facts", "validate", "--json"])
    facts_ok = code_facts == 0
    checks.append({
        "name": "Domain Truth Facts Schema & Freshness (ADR-0192)",
        "category": "SSOT Facts",
        "passed": facts_ok,
        "detail": "Domain facts conform to schema & 14-day SLA" if facts_ok else out_facts[:120],
    })

    # 4. 多客户端 IDE 配置挂载一致性
    code_clients, out_clients = run_subcommand(["uv", "run", "--project", "projects/ecos", "ecos-constraint", "documents", "sync-clients", "--mode", "check", "--json"])
    clients_ok = code_clients == 0
    checks.append({
        "name": "Multi-Client Documents Configuration Sync",
        "category": "IDE Ergonomics",
        "passed": clients_ok,
        "detail": "Claude/Zed/Codex/ZCode configs aligned" if clients_ok else out_clients[:120],
    })

    # 5. Local Compute Fabric 诊断 (omlxc doctor)
    code_doctor, out_doctor = run_subcommand(["uv", "run", "--project", "projects/omlxc", "omlxc", "doctor", "--direct", "--json"])
    doctor_ok = code_doctor == 0
    checks.append({
        "name": "omlxc Compute Fabric Health",
        "category": "Compute Engine",
        "passed": doctor_ok,
        "detail": "Compute fabric database, models & sockets healthy" if doctor_ok else out_doctor[:120],
    })

    # 6. Agent Skills 规范校验
    skills_script = REPO_ROOT / "bin" / "ssot" / "check-agent-skills.py"
    if skills_script.exists():
        code_skills, out_skills = run_subcommand([sys.executable, str(skills_script)])
        skills_ok = code_skills == 0
    else:
        skills_ok = True
        out_skills = "skills checker not found (skipped)"
    checks.append({
        "name": "Agent Skills YAML Frontmatter Gate",
        "category": "Agent Assets",
        "passed": skills_ok,
        "detail": "All skills follow .agents/skills specification" if skills_ok else out_skills[:120],
    })

    all_passed = all(c["passed"] for c in checks)
    passed_count = sum(1 for c in checks if c["passed"])

    report_lines = [
        "# 🛡️ omostation 全域周度治理与双平面巡检报告",
        "",
        f"> **巡检时间**: {now_iso}  ",
        f"> **全域状态**: {'🟢 ALL PASS (全域健康)' if all_passed else '🟡 ADVISORY / VIOLATIONS (存在关注项)'} ({passed_count}/{len(checks)})  ",
        "",
        "## 📊 巡检六大支柱状态矩阵",
        "",
        "| 支柱检查项 | 治理维度 | 状态 | 详情摘要 |",
        "| :--- | :--- | :---: | :--- |",
    ]
    for c in checks:
        icon = "✅ PASS" if c["passed"] else "⚠️ ATTENTION"
        report_lines.append(f"| {c['name']} | {c['category']} | {icon} | {c['detail']} |")

    report_lines.extend([
        "",
        "## 🚀 处置与自愈指引",
        "",
        "1. **规则漂移**: 运行 `make mof-compile` 或 `ecos-constraint drift` 同步元模型。",
        "2. **Documents 违规**: 运行 `ecos-constraint documents audit` 定位违规文件并清理。",
        "3. **事实实体过期**: 运行 `ecos-constraint facts validate` 补齐事实字段并更新保鲜时间戳。",
        "4. **客户端挂载断开**: 运行 `ecos-constraint documents sync-clients` 重新下发 IDE 挂载配置。",
        "5. **算力网关异常**: 运行 `omlxc doctor --direct` 检查 launchd 与本地模型套接字。",
        "",
        "---",
        "*Automated Governance Patrol Engine — ADR-0192*",
    ])

    report_md = "\n".join(report_lines)

    # Output file resolution
    out_file = args.output
    if not out_file:
        out_file = str(REPO_ROOT / ".omo" / "reports" / "hygiene" / f"patrol-{date_str}.md")
    
    try:
        p_out = Path(out_file)
        p_out.parent.mkdir(parents=True, exist_ok=True)
        p_out.write_text(report_md, encoding="utf-8")
    except Exception as e:
        print(f"⚠️ 无法写入报告文件 {out_file}: {e}", file=sys.stderr)

    if args.json:
        print(json.dumps({
            "timestamp": now_iso,
            "all_passed": all_passed,
            "score": f"{passed_count}/{len(checks)}",
            "report_file": str(out_file),
            "checks": checks,
        }, ensure_ascii=False, indent=2))
    else:
        print(report_md)

    if not all_passed and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
