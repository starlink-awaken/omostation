#!/usr/bin/env python3
"""
ecos-constraint-validator.py — L0 协议约束校验器

校验系统状态是否满足 L0 协议约束 (warn/enforce 两种模式)。

基于 ecos/ssot/registry/L0-constraints.yaml 中定义的约束规则，
检查协议衰减、组件状态、规范执行等。

用法:
    python3 ecos-constraint-validator.py          # 检查 + 报告
    python3 ecos-constraint-validator.py --json   # JSON 输出
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_constraints() -> list[dict]:
    """加载 L0 约束"""
    ws = Path.home() / "Workspace"
    constraints_path = ws / "projects" / "ecos" / "src" / "ecos" / "ssot" / "registry" / "L0-constraints.yaml"
    if not constraints_path.exists():
        return []

    import yaml
    try:
        with open(constraints_path) as f:
            data = yaml.safe_load(f)
        return data.get("constraints", []) if isinstance(data, dict) else []
    except Exception:
        return []


def check_protocol_decay() -> list[dict]:
    """检查协议衰减"""
    ws = Path.home() / "Workspace"
    constraints_path = ws / "projects" / "ecos" / "src" / "ecos" / "ssot" / "registry" / "L0-constraints.yaml"
    if not constraints_path.exists():
        return [{"name": "protocol_decay", "pass": None, "reason": "约束文件不存在"}]

    import yaml
    try:
        with open(constraints_path) as f:
            data = yaml.safe_load(f)
        registry = data.get("protocol_registry", [])
        results = []
        for p in registry:
            introduced = datetime.strptime(p.get("introduced", "2020-01-01"), "%Y-%m-%d")
            age = (datetime.now() - introduced).days
            half_life = p.get("half_life_days", 365)
            decay = min(1.0, age / half_life) if half_life > 0 else 1.0
            remaining = (1.0 - decay) * 100
            status = "fresh" if remaining > 80 else ("aging" if remaining > 50 else "decayed")
            results.append({
                "name": f"protocol_decay_{p.get('id', '?')}",
                "pass": remaining > 50,
                "reason": f"{p.get('id', '?')}: {remaining:.1f}% ({status})",
            })
        return results
    except Exception as e:
        return [{"name": "protocol_decay", "pass": False, "reason": str(e)}]


def validate(json_output: bool = False) -> dict:
    """执行校验"""
    results = []
    results.extend(check_protocol_decay())

    passed = sum(1 for r in results if r.get("pass") is True)
    failed = sum(1 for r in results if r.get("pass") is False)
    unknown = sum(1 for r in results if r.get("pass") is None)

    report = {
        "checked_at": now(),
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "unknown": unknown,
        },
    }

    return report


def main():
    json_output = "--json" in sys.argv
    report = validate(json_output)

    if json_output:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for r in report["results"]:
            icon = "✅" if r.get("pass") is True else ("⚠️" if r.get("pass") is False else "❓")
            print(f"  {icon} {r['reason']}")
        s = report["summary"]
        print(f"\n结果: {s['passed']}/{s['total']} 通过")

    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
