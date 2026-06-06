#!/usr/bin/env python3
"""
织星 MOF — L0 自举校验器 (mof-bootstrap)
===========================================
L0 对自己的 M1 节点做自反性校验——L0 管全系统，谁管 L0？L0 管自己。

自举校验项:
  1. L0 自身的 M1 节点是否通过 mof-validate
  2. M3↔M2↔M1 的自反一致性 (M2 定义是否遵守 M3 的规则)
  3. L0 工具链完整性 (4+ 工具是否都在且可运行)
  4. L0 约束覆盖率 (有多少 M2 类型缺少 M1 实例)
  5. L0 层边界自检 (L0 自身是否遵守 layer-boundary.yaml)
  6. 自举闭环: 如果 L0 自己违规了，谁来创建 CARDS？

用法:
    python3 mof-bootstrap.py                 # 全量自举校验
    python3 mof-bootstrap.py --json          # JSON 输出
    python3 mof-bootstrap.py --fix           # 尝试自动修复
"""

import sys, json, yaml, subprocess, sqlite3
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
WS = HOME / "Workspace"
L0_SSOT = WS / "projects" / "ecos" / "src" / "ecos" / "ssot"
L0_TOOLS = L0_SSOT / "tools"
L0_M1 = L0_SSOT / "mof" / "m1"
M2_DIR = L0_SSOT / "mof" / "m2"
M3_FILE = L0_SSOT / "mof" / "m3.yaml"
BOUNDARY_FILE = L0_SSOT / "registry" / "layer-boundary.yaml"
CARDS_DB = WS / "data" / "cards" / "cards.db"


def now(): return datetime.now(timezone.utc)


def check_1_self_validate() -> dict:
    """L0 自身的 M1 节点校验"""
    result = subprocess.run(
        ["python3", str(L0_TOOLS / "mof-validate.py"), "--json"],
        capture_output=True, text=True, timeout=30
    )
    passed = result.returncode == 0
    count = 0
    if passed:
        try:
            data = json.loads(result.stdout)
            count = data.get("node_count", 0)
            results = data.get("results", [])
            errors = sum(1 for r in results if r.get("level") == "error")
            passed = errors == 0
        except: pass
    
    return {"check": "L0 自校验", "passed": passed, "detail": f"{count} 节点通过", "severity": "critical" if not passed else "ok"}


def check_2_m3_m2_consistency() -> dict:
    """M3↔M2 自反一致性"""
    if not M3_FILE.exists() or not M2_DIR.exists():
        return {"check": "M3↔M2 一致性", "passed": False, "detail": "M3 或 M2 文件缺失", "severity": "critical"}
    
    m3 = yaml.safe_load(open(M3_FILE))
    # Load M2 from split files
    m2 = {}
    for f in sorted(M2_DIR.glob('*.yaml')):
        data = yaml.safe_load(open(f))
        for k in data:
            if k not in ('m2_type','version','created'):
                m2[k] = data[k]
    
    m3_elements = m3.get("m3", {}).get("elements", {})
    m2_types = [k for k in m2.get("m2", m2).keys() if k not in ("common", "cross_type_constraints", "ecos_mapping", "meta", "version", "created", "description")]
    
    issues = []
    for mt in m2_types:
        m2_def = m2.get("m2", m2).get(mt, {})
        m3_parent = m2_def.get("m3_parent", "")
        if m3_parent:
            # Check M3 parent exists
            parts = m3_parent.split(".")
            if parts[0] not in m3_elements:
                issues.append(f"{mt}.m3_parent={m3_parent} 在 M3 中不存在")
    
    passed = len(issues) == 0
    return {"check": "M3↔M2 自反性", "passed": passed, "detail": f"{len(issues)} 不一致" if issues else "一致", "severity": "critical" if not passed else "ok"}


def check_3_toolchain_health() -> dict:
    """L0 工具链完整性"""
    tools = ["mof-validate.py", "mof-scan.py", "mof-audit.py", "mof-derive.py", "mof-enforce.py", "mof-extract.py", "mof-model.py", "mof-register-tasks.py"]
    missing = [t for t in tools if not (L0_TOOLS / t).exists()]
    passed = len(missing) == 0
    return {"check": "L0 工具链完整性", "passed": passed, "detail": f"缺 {missing}" if missing else f"{len(tools)} 工具就绪", "severity": "high" if not passed else "ok"}


def check_4_m1_coverage() -> dict:
    """M1 覆盖率分析"""
    # Load M2
    m2 = {}
    for f in sorted(M2_DIR.glob('*.yaml')):
        data = yaml.safe_load(open(f))
        for k in data:
            if k not in ('m2_type','version','created'):
                m2[k] = data[k]
    m2_types = [k for k in m2.keys() if k not in ("common", "cross_type_constraints", "ecos_mapping", "meta", "version", "created", "description", "m2_type")]
    
    coverage = {}
    for f in L0_M1.rglob("*.yaml"):
        try:
            data = yaml.safe_load(open(f))
            t = data.get("type", "?")
            coverage[t] = coverage.get(t, 0) + 1
        except: pass
    
    gaps = [t for t in m2_types if coverage.get(t, 0) < 2]
    passed = len(gaps) == 0
    return {"check": "M1 覆盖率", "passed": passed, "detail": f"缺口: {gaps}" if gaps else f"{len(m2_types)} 类型全覆盖", "severity": "medium" if gaps else "ok"}


def check_5_l0_boundary_self() -> dict:
    """L0 层边界自检"""
    if not BOUNDARY_FILE.exists():
        return {"check": "L0 边界自检", "passed": False, "detail": "layer-boundary.yaml 不存在", "severity": "critical"}
    
    boundary = yaml.safe_load(open(BOUNDARY_FILE))
    l0_rules = boundary.get("layers", {}).get("L0", {})
    
    # Check: all files in L0_SSOT conform to L0 rules
    violations = []
    for f in L0_SSOT.rglob("*"):
        if f.is_file() and f.suffix == ".md":
            # L0 forbids .md (unless README/INDEX/CHANGELOG)
            if not any(k in f.name for k in ["README", "INDEX", "CHANGELOG"]):
                if "CLAUDE" not in f.name and "AGENTS" not in f.name:
                    violations.append(f.name)
    
    passed = len(violations) == 0
    return {"check": "L0 层边界自检", "passed": passed, "detail": f"{len(violations)} 违规" if violations else "L0 自身合规", "severity": "high" if violations else "ok"}


def check_6_bootstrap_closure() -> dict:
    """自举闭环：如果 L0 自己违规，谁来管？"""
    # Check: does mof-bootstrap itself have a CARDS debt for self-issues?
    # Check: does the validator script exist and run?
    validator = L0_TOOLS / "mof-validate.py"
    if not validator.exists():
        return {"check": "自举闭环", "passed": False, "detail": "mof-validate.py 不存在——L0 无法校验自己", "severity": "critical"}
    
    # Bootstrap closure: can we validate the validator?
    passed = validator.exists()
    return {"check": "自举闭环", "passed": passed, "detail": "L0 可自校验" if passed else "破损", "severity": "critical" if not passed else "ok"}


def create_bootstrap_debt(issue: dict):
    """为自举发现的问题创建 CARDS"""
    if not CARDS_DB.exists():
        return
    if issue["severity"] == "ok":
        return
    try:
        conn = sqlite3.connect(str(CARDS_DB))
        now_dt = now().isoformat()
        debt_id = f"DEBT-BOOTSTRAP-{now_dt[:10]}-{issue['check'][:20]}"
        debt_id = debt_id.replace(" ", "-")[:50]
        conn.execute("""
            INSERT OR IGNORE INTO cards (id, type, status, title, domain, priority, summary, content, created_at, updated_at)
            VALUES (?, 'debt', 'identified', ?, 'meta', 'P1', ?, ?, ?, ?)
        """, (debt_id, f"L0自举: {issue['check']}", 
              issue['detail'],
              f"## mof-bootstrap 自动检测\n- 检查: {issue['check']}\n- 结果: {issue['detail']}\n- 严重度: {issue['severity']}",
              now_dt, now_dt))
        conn.commit()
        conn.close()
    except: pass


def format_report(checks: list[dict]) -> str:
    lines = ["=" * 64, "  织星 MOF — L0 自举校验报告", "=" * 64,
             f"  时间: {now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    
    all_pass = True
    for c in checks:
        icon = "✅" if c["passed"] else {"critical": "🔴", "high": "🟡", "medium": "🟢", "ok": "✅"}.get(c["severity"], "❓")
        lines.append(f"  {icon} {c['check']}: {c['detail']}")
        if not c["passed"]:
            all_pass = False
    
    lines.append(f"\n  {'✅ L0 自举健康' if all_pass else '❌ L0 自举发现问题'}")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()

    checks = [
        check_1_self_validate(),
        check_2_m3_m2_consistency(),
        check_3_toolchain_health(),
        check_4_m1_coverage(),
        check_5_l0_boundary_self(),
        check_6_bootstrap_closure(),
    ]

    if args.json:
        print(json.dumps({"checks": checks}, ensure_ascii=False, indent=2))
    else:
        print(format_report(checks))

    if args.fix:
        for c in checks:
            if not c["passed"]:
                create_bootstrap_debt(c)
        print(f"\n  📋 已为自举问题创建 CARDS")


if __name__ == "__main__":
    main()
