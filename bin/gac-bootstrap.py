#!/usr/bin/env python3
"""gac-bootstrap — GaC 自举递归检测 (元治理核心: GaC 治 GaC 自身).

GaC 治理一切, GaC 自己也要被治 (NORTH-STAR 元治理递归). 本工具是 GaC 用自己的
机制检测自身完整性的自举点:

  层1 注册表 drift   → CR-X2-GAC-DRIFT (已有, 本工具不重复)
  层2 schema 自洽    → gac-mof-validate (机制7, M2 type 驱动)
  层3 工具活/死      → 9 个 gac-*.py 工具是否都能跑 (防死工具)
  层4 indexed 完整   → source_ref 文件存在性 (GaC 治 indexed)
  层5 执行有效       → executor 真注册检测 (防声明不执行)

用法:
  python3 bin/gac-bootstrap.py           # 自举检测, 有问题返回 1
  python3 bin/gac-bootstrap.py --json    # JSON 输出 (gac-healthcheck 消费)

退出码: 0 = GaC 自身完整, 1 = 自举发现 gap
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
GAC_TOOLS = sorted((WORKSPACE / "bin").glob("gac-*.py"))


def load_rules() -> list[dict]:
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    return docs[-1].get("gac", {}).get("rules", []) if docs else []


def check_tools_alive() -> dict:
    """层3: GaC 工具存活检测 (语法正确 + __main__ 入口).

    不跑实际工作 (避免 --help 触发 drift/healthcheck 全量执行的 timeout/副作用).
    存活 = Python 语法可解析 + 有 __main__ 入口 (可被 python tool.py 调起).
    """
    import ast

    alive, dead = [], []
    for tool in GAC_TOOLS:
        name = tool.name
        try:
            source = tool.read_text(encoding="utf-8")
            ast.parse(source)  # 语法正确性
            if '__name__' in source and '__main__' in source:
                alive.append(name)
            else:
                dead.append(f"{name} (无 __main__ 入口)")
        except SyntaxError as e:
            dead.append(f"{name} (语法错: {e})")
        except OSError as e:
            dead.append(f"{name} (读失败: {e})")
    return {"alive": len(alive), "dead": dead, "total": len(GAC_TOOLS)}


def check_indexed_integrity() -> dict:
    """层4: indexed source_ref 文件存在性 (GaC 治 indexed 完整)."""
    rules = load_rules()
    missing = []
    for r in rules:
        if r.get("source_type") != "indexed":
            continue
        ref = r.get("source_ref", "").split("::")[0]
        if ref and not os.path.exists(WORKSPACE / ref):
            missing.append({"id": r["id"], "missing_ref": ref})
    return {"ok": len(missing) == 0, "missing_count": len(missing), "missing": missing}


def check_exec_effective() -> dict:
    """层5: executor 执行有效性 (每条规则至少一个真注册 executor).

    检测: executor 非空 + 在 schema.executor_enum 内 (防声明不执行/拼错 executor).
    """
    rules = load_rules()
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    valid_executors = set(
        docs[-1].get("gac", {}).get("schema", {}).get("executor_enum", [])
    )
    issues = []
    for r in rules:
        execs = r.get("executor", [])
        if not execs:
            issues.append({"id": r["id"], "reason": "无 executor"})
            continue
        invalid = [e for e in execs if valid_executors and e not in valid_executors]
        if invalid:
            issues.append({"id": r["id"], "reason": f"非法 executor: {invalid}"})
    return {"ok": len(issues) == 0, "issues_count": len(issues), "issues": issues}


def check_schema_self_consistent() -> dict:
    """层2: schema 自洽 (required 字段 + enum 对齐, 复用 gac-validate 逻辑轻量版)."""
    rules = load_rules()
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    schema = docs[-1].get("gac", {}).get("schema", {})
    required = schema.get("required", [])
    dim_enum = set(schema.get("dimension_enum", []))
    layer_enum = set(schema.get("layer_enum", []))
    issues = []
    for r in rules:
        for f in required:
            if not r.get(f):
                issues.append(f"{r.get('id','?')}: 缺 {f}")
        if r.get("dimension") and dim_enum and r["dimension"] not in dim_enum:
            issues.append(f"{r['id']}: dimension 非法")
        if r.get("layer") and layer_enum and r["layer"] not in layer_enum:
            issues.append(f"{r['id']}: layer 非法")
    return {"ok": len(issues) == 0, "issues_count": len(issues), "rules": len(rules)}


def run_bootstrap(as_json: bool = False) -> int:
    """主自举检测."""
    report: dict[str, Any] = {
        "tools": check_tools_alive(),
        "indexed_integrity": check_indexed_integrity(),
        "exec_effective": check_exec_effective(),
        "schema_self": check_schema_self_consistent(),
    }
    # 总体 ok = 所有层过
    report["ok"] = (
        not report["tools"]["dead"]
        and report["indexed_integrity"]["ok"]
        and report["exec_effective"]["ok"]
        and report["schema_self"]["ok"]
    )

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    print("═══ GaC 自举递归检测 (GaC 治 GaC 自身) ═══")
    t = report["tools"]
    t_status = "✅" if not t["dead"] else "❌"
    print(f"▶ 层3 工具活/死: {t_status} {t['alive']}/{t['total']}")
    for d in t["dead"]:
        print(f"    ❌ {d}")

    ii = report["indexed_integrity"]
    ii_status = "✅" if ii["ok"] else "❌"
    print(f"▶ 层4 indexed 完整: {ii_status} source_ref 缺失={ii['missing_count']}")
    for m in ii["missing"][:3]:
        print(f"    ❌ {m['id']}: {m['missing_ref']}")

    ee = report["exec_effective"]
    ee_status = "✅" if ee["ok"] else "❌"
    print(f"▶ 层5 执行有效: {ee_status} 非法/无 executor={ee['issues_count']}")
    for i in ee["issues"][:3]:
        print(f"    ❌ {i['id']}: {i['reason']}")

    ss = report["schema_self"]
    ss_status = "✅" if ss["ok"] else "❌"
    print(f"▶ 层2 schema 自洽: {ss_status} {ss['rules']} 规则 issues={ss['issues_count']}")

    print()
    overall = "✅ GaC 自身完整 (元治理递归闭环)" if report["ok"] else "❌ GaC 自举发现 gap"
    print(f"═══ 总体: {overall} ═══")
    return 0 if report["ok"] else 1


def main() -> int:
    args = sys.argv[1:]
    return run_bootstrap(as_json="--json" in args)


if __name__ == "__main__":
    sys.exit(main())
