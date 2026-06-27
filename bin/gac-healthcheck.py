#!/usr/bin/env python3
"""GaC 治理即代码 — 体系健康检查 (ADR-0106, 元治理递归自检).

端到端验证 GaC 体系落地 + 产生效果 (不只文件存在, 验证机制真工作):

  - 11 核心文件落地检查
  - 机制 2/5/6 (gac-validate 跑通 + 0 error)
  - 机制 4 (gac-drift 跑通 + drift 数)
  - 机制 7 (GacRule M2 可解析)
  - --json 数据源有效 (阶段 4 前置)
  - ADR 引用一致 (无 0104 残留)
  - 注册表规则数 + dimension/layer 覆盖

用法:
  python3 bin/gac-healthcheck.py          # 健康检查, exit 0=全绿, 1=有红
  python3 bin/gac-healthcheck.py --json   # JSON 输出 (cron/仪表盘用)

CI 可移植: Path(__file__).resolve().parents[1]. 对标 gac-validate/gac-drift (bin/+--gate 模式).
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

# 11 核心文件 (相对 WORKSPACE)
CORE_FILES = {
    "north_star": ".omo/_knowledge/gac/NORTH-STAR.md",
    "roadmap": ".omo/_knowledge/gac/roadmap-v1.md",
    "stage34_design": ".omo/_knowledge/gac/stage3-4-design.md",
    "adr": ".omo/_knowledge/decisions/0106-gac-governance-as-code.md",
    "registry": ".omo/_truth/registry/governance-checks.yaml",
    "validate": "bin/gac-validate.py",
    "drift": "bin/gac-drift.py",
    "ci_gate": ".github/workflows/gac-gate.yml",
    "cron": ".omo/cron/gac-crontab",
    "agents_md": "AGENTS.md",
    "m2_type": "projects/ecos/src/ecos/ssot/mof/m2/gac_rule.yaml",
    "stage1_design": ".omo/_knowledge/gac/stage1-hook-design.md",
    "hook": "bin/gac-hook-pre-edit.py",
    "dashboard": "bin/gac-dashboard.py",
    "mof_validate": "bin/gac-mof-validate.py",
    "doc_ssot_lint": "bin/doc-ssot-lint.py",
    "hygiene": "bin/gac-hygiene-check.py",
    "gen_registry": "bin/gen-project-registry.py",
}


def check_files() -> tuple[list[str], list[str]]:
    """11 核心文件落地检查. 返回 (ok_names, missing_paths)."""
    ok, missing = [], []
    for name, rel in CORE_FILES.items():
        if (WORKSPACE / rel).exists():
            ok.append(name)
        else:
            missing.append(rel)
    return ok, missing


def run_tool(script: str, args: list[str]) -> tuple[int, str]:
    """跑 bin/ 脚本, 返回 (exit_code, stdout)."""
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / script), *args],
        capture_output=True,
        text=True,
        cwd=WORKSPACE,
    )
    return result.returncode, result.stdout


def load_rules() -> list[dict]:
    """加载 governance-checks.yaml::gac.rules (多文档 strip frontmatter)."""
    import yaml

    reg = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    docs = [d for d in yaml.safe_load_all(reg.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    return docs[-1].get("gac", {}).get("rules", [])


def check_adr_consistency() -> int:
    """ADR 引用一致 (无 0104 残留). 返回残留数."""
    import subprocess

    result = subprocess.run(
        ["rg", "-c", "ADR-0104"]
        + [
            str(WORKSPACE / p)
            for p in [
                ".omo/_knowledge/gac",
                ".omo/_truth/registry/governance-checks.yaml",
                "AGENTS.md",
            ]
        ]
        + [str(WORKSPACE / "bin/gac-validate.py"), str(WORKSPACE / "bin/gac-drift.py")],
        capture_output=True,
        text=True,
    )
    # rg -c 每文件一行 count; 无匹配 exit 1
    if result.returncode == 1:
        return 0  # 无残留
    return len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0


def check_m2_type() -> dict:
    """机制 7: GacRule M2 可解析. 返回 {ok, fields, states, mechanisms}."""
    import yaml

    m2 = WORKSPACE / "projects/ecos/src/ecos/ssot/mof/m2/gac_rule.yaml"
    if not m2.exists():
        return {"ok": False, "error": "m2/gac_rule.yaml 缺"}
    docs = [d for d in yaml.safe_load_all(m2.read_text(encoding="utf-8")) if d]
    if not docs:
        return {"ok": False, "error": "m2 空文档"}
    g = docs[-1].get("GacRule", {})
    return {
        "ok": True,
        "fields": len(g.get("fields", {})),
        "states": len(g.get("stateMachine", {})),
        "mechanisms": len(g.get("mechanisms", [])),
    }


def healthcheck() -> dict:
    """主健康检查. 返回报告 dict."""
    report: dict = {
        "timestamp": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"])
        .decode()
        .strip()
    }

    # 1. 核心文件
    ok_files, missing = check_files()
    report["files"] = {
        "ok": len(ok_files),
        "total": len(CORE_FILES),
        "missing": missing,
    }

    # 2. gac-validate (机制 2/5/6)
    val_code, val_out = run_tool("bin/gac-validate.py", ["--json"])
    try:
        val_json = json.loads(val_out) if val_out else {}
    except json.JSONDecodeError:
        val_json = {}
    report["validate"] = {
        "ok": val_code == 0,
        "rules": val_json.get("rules", 0),
        "errors": len(val_json.get("errors", [])),
        "warnings": len(val_json.get("warnings", [])),
    }

    # 3. gac-drift (机制 4)
    drift_code, drift_out = run_tool("bin/gac-drift.py", ["--json"])
    try:
        drift_json = json.loads(drift_out) if drift_out else {}
    except json.JSONDecodeError:
        drift_json = {}
    report["drift"] = {
        "ok": drift_code == 0,
        "rules": drift_json.get("rules", 0),
        "drift_count": drift_json.get("drift_count", 0),
    }

    # 4. 注册表 dimension/layer 覆盖
    rules = load_rules()
    dims = Counter(r.get("dimension", "?") for r in rules)
    layers = Counter(r.get("layer", "?") for r in rules)
    report["coverage"] = {
        "rules": len(rules),
        "dimension": dict(dims),
        "dimension_complete": set(dims) >= {"X1", "X2", "X3", "X4"},
        "layer": dict(layers),
    }

    # 5. ADR 引用一致
    report["adr_residue_0104"] = check_adr_consistency()

    # 6. 机制 7 GacRule M2
    report["m2_type"] = check_m2_type()

    # 7. doc-ssot (CR-X4-DOC-SSOT: 文档 SSOT 正交契约)
    ds_code, ds_out = run_tool("bin/doc-ssot-lint.py", ["--json"])
    try:
        ds_json = json.loads(ds_out) if ds_out else {}
    except json.JSONDecodeError:
        ds_json = {}
    report["doc_ssot"] = {
        "ok": ds_code == 0,
        "conflicts": ds_json.get("conflicts", 0),
        "files_scanned": ds_json.get("files_scanned", 0),
    }

    # 8. hygiene (CR-HYG-01/02: 工作区卫生)
    hy_code, hy_out = run_tool("bin/gac-hygiene-check.py", ["--json"])
    try:
        hy_json = json.loads(hy_out) if hy_out else {}
    except json.JSONDecodeError:
        hy_json = {}
    report["hygiene"] = {
        "ok": hy_code == 0,
        "issues": hy_json.get("issues", 0),
        "zero_byte": hy_json.get("zero_byte_count", 0),
        "case_conflicts": hy_json.get("case_conflict_count", 0),
    }

    # 9. registry drift (代码→registry SSOT 链闭环; doc-ssot 第4步)
    gr_code, gr_out = run_tool("bin/gen-project-registry.py", ["--json"])
    try:
        gr_json = json.loads(gr_out) if gr_out else {}
    except json.JSONDecodeError:
        gr_json = {}
    report["registry_drift"] = {
        "ok": gr_code == 0,
        "drift_count": gr_json.get("drift_count", 0),
        "projects_scanned": gr_json.get("projects_scanned", 0),
    }

    # 总体健康 (文件全 + validate/drift/M2 ok + 无 ADR 残留 + dimension 全 + doc-ssot/hygiene/registry-drift ok)
    report["healthy"] = (
        not missing
        and report["validate"]["ok"]
        and report["drift"]["ok"]
        and report["m2_type"].get("ok", False)
        and report["adr_residue_0104"] == 0
        and report["coverage"]["dimension_complete"]
        and report["doc_ssot"]["ok"]
        and report["hygiene"]["ok"]
        and report["registry_drift"]["ok"]
    )
    return report


def print_report(report: dict) -> None:
    """人读报告."""
    print(f"═══ GaC 体系健康检查 ({report['timestamp']}) ═══")
    print()

    # 文件
    f = report["files"]
    status = "✅" if not f["missing"] else "❌"
    print(
        f"▶ 核心文件: {status} {f['ok']}/{f['total']}"
        + (f" (缺: {f['missing']})" if f["missing"] else "")
    )

    # validate
    v = report["validate"]
    status = "✅" if v["ok"] else "❌"
    print(
        f"▶ gac-validate (机制2/5/6): {status} rules={v['rules']} errors={v['errors']} warnings={v['warnings']}"
    )

    # drift
    d = report["drift"]
    status = "✅" if d["drift_count"] == 0 else "⚠️"
    print(
        f"▶ gac-drift (机制4): {status} drift_count={d['drift_count']}"
        + (" (闭环归零)" if d["drift_count"] == 0 else "")
    )

    # 覆盖
    c = report["coverage"]
    dim_status = "✅" if c["dimension_complete"] else "❌"
    print(
        f"▶ 覆盖: {c['rules']} 规则 | dimension {dim_status} {c['dimension']} | layer {c['layer']}"
    )

    # ADR
    adr_status = "✅" if report["adr_residue_0104"] == 0 else "❌"
    print(f"▶ ADR 引用一致: {adr_status} (0104 残留={report['adr_residue_0104']})")

    # M2
    m = report["m2_type"]
    if m.get("ok"):
        print(
            f"▶ GacRule M2 (机制7): ✅ fields={m['fields']} 状态机={m['states']} 机制={m['mechanisms']}"
        )
    else:
        print(f"▶ GacRule M2 (机制7): ❌ {m.get('error')}")

    # doc-ssot (CR-X4-DOC-SSOT)
    ds = report["doc_ssot"]
    ds_status = "✅" if ds["ok"] else "❌"
    print(
        f"▶ doc-ssot (CR-X4-DOC-SSOT): {ds_status} 扫描={ds['files_scanned']} 冲突={ds['conflicts']}"
    )

    # hygiene (CR-HYG-01/02)
    h = report["hygiene"]
    h_status = "✅" if h["ok"] else "❌"
    print(
        f"▶ hygiene (CR-HYG-01/02): {h_status} 0字节={h['zero_byte']} 大小写冲突={h['case_conflicts']}"
    )

    # registry drift (代码→registry SSOT 链)
    gr = report["registry_drift"]
    gr_status = "✅" if gr["ok"] else "❌"
    print(
        f"▶ registry-drift (代码→SSOT): {gr_status} 扫描={gr['projects_scanned']} drift={gr['drift_count']}"
    )

    print()
    overall = "✅ 全绿 (GaC 体系闭环生效)" if report["healthy"] else "❌ 有红 (见上)"
    print(f"═══ 总体: {overall} ═══")


def main() -> int:
    args = sys.argv[1:]
    json_mode = "--json" in args

    report = healthcheck()

    if json_mode:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)

    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
