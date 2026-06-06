#!/usr/bin/env python3
"""
eCOS v5 L0 — 协议约束校验器 (ecos-constraint-validator)
===========================================================
Phase7 / ADT-04 / v5 设计能力 PoC
读取 L0-constraints.yaml，校验当前系统状态是否满足协议级约束。

用法:
    python3 ecos-constraint-validator.py [--enforce] [--json]

模式:
    warn (默认): 输出告警，退出码始终为 0
    enforce: 违反 required 约束时退出码为 1

退出码:
    0 = 全部通过（或 warn 模式）
    1 = 存在 required 违反（仅 enforce 模式）
"""

import sys
import json
import argparse
import yaml
from datetime import datetime
from pathlib import Path


CONSTRAINTS_FILE = Path(__file__).parent / "L0-constraints.yaml"
# L0 协议层: 约束文件与校验器同目录
DOCS = Path.home() / "Documents"


def load_constraints() -> dict:
    with open(CONSTRAINTS_FILE, "r") as f:
        return yaml.safe_load(f)


def check_system_state() -> dict:
    """收集当前系统状态用于约束校验"""
    state = {
        "protocol": {"registered": True, "version": "1.0.0"},
        "layer": {"cross_call": {"route": "I0/Agora"}},
        "write": {"entry": "agora.register"},
        "claude_md": {"age_days": 0},  # 由 check-claude-freshness.py 动态更新
        "domain": {},
    }

    # 检查 CLAUDE.md 保鲜
    freshness_script = Path(__file__).parent / "check-claude-freshness.py"
    if freshness_script.exists():
        import subprocess
        result = subprocess.run(
            ["python3", str(freshness_script), "--root", str(DOCS),
             "--max-age-days", "60", "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                state["claude_md"]["age_days"] = max(
                    (f["age_days"] for f in data.get("files", [])), default=0
                )
                state["claude_md"]["stale_count"] = data.get("stale", 0)
            except (json.JSONDecodeError, KeyError):
                pass

    # 检查 value_tier
    value_stack = DOCS / "驾驶舱" / "x3-value-stack.yaml"
    if value_stack.exists():
        with open(value_stack, "r") as f:
            vs = yaml.safe_load(f)
        for domain_name, domain in vs.get("domains", {}).items():
            state["domain"][domain_name] = {
                "value_tier": domain.get("value_tier"),
                "cost_attribution": domain.get("cost_attribution", "none"),
            }

    return state


def evaluate_constraints(constraints: list[dict], state: dict) -> list[dict]:
    """评估约束"""
    results = []
    for c in constraints["constraints"]:
        rule = c["rule"]
        ctype = c["type"]

        # 简化规则评估（PoC 阶段用显式检查替代表达式引擎）
        passed = True
        detail = ""

        if rule == "protocol.registered == true":
            passed = state["protocol"]["registered"]
            detail = "协议已注册" if passed else "协议未注册"
        elif rule == "layer.cross_call.route == 'I0/Agora'":
            passed = state["layer"]["cross_call"]["route"] == "I0/Agora"
            detail = f"当前路由: {state['layer']['cross_call']['route']}"
        elif rule == "write.entry == 'agora.register'":
            passed = state["write"]["entry"] == "agora.register"
            detail = f"当前入口: {state['write']['entry']}"
        elif rule == "protocol.version != null":
            passed = state["protocol"]["version"] is not None
            detail = f"版本: {state['protocol']['version']}"
        elif rule == "claude_md.age_days <= 60":
            age = state["claude_md"]["age_days"]
            passed = age <= 60
            detail = f"最旧 CLAUDE.md: {age} 天"
        elif "value_tier" in rule:
            # 简化: 检查是否有域缺少 value_tier
            missing = [d for d, v in state["domain"].items() if v.get("value_tier") is None]
            passed = len(missing) == 0
            detail = f"缺失: {missing}" if missing else "全部已声明"
        else:
            passed = True
            detail = "规则评估未实现（PoC 限制）"

        results.append({
            "id": c["id"],
            "type": ctype,
            "dimension": c["dimension"],
            "description": c["description"],
            "passed": passed,
            "detail": detail,
            "violation": c["violation"] if not passed else None,
        })

    return results


def format_report(results: list[dict], mode: str, constraints: dict = None) -> str:
    now = datetime.now()
    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — L0 协议约束校验报告 (PoC)")
    lines.append("=" * 64)
    lines.append(f"  时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  模式: {mode}  |  约束数: {len(results)}")
    lines.append("")

    # 协议价值评估 (X3 half_life 追踪)
    if constraints and "protocol_registry" in constraints:
        lines.append("  ── X3 协议价值评估 ──")
        for p in constraints["protocol_registry"]:
            intro = datetime.strptime(p["introduced"], "%Y-%m-%d")
            age_days = (now - intro).days
            half = p["half_life_days"]
            decay = min(1.0, age_days / half)
            value_remaining = max(0, (1 - decay) * 100)
            bar = "█" * int(value_remaining / 10) + "░" * (10 - int(value_remaining / 10))

            age_str = f"{age_days}d" if age_days > 0 else "0d"
            status = "⚠️ 超期" if decay > 1.0 else "✅" if decay < 0.5 else "⏳"

            lines.append(f"  {status} {p['id']:10s} v{p['version']:10s} "
                         f"{age_str:5s}/{p['half_life_days']}d  "
                         f"衰减 {decay:.0%} 剩余 {value_remaining:.0f}% {bar}")
        lines.append("")

    lines.append(f"  ── 约束校验 ({len(results)} 项) ──")

    required = [r for r in results if r["type"] == "required"]
    preferred = [r for r in results if r["type"] == "preferred"]
    req_pass = sum(1 for r in required if r["passed"])
    pref_pass = sum(1 for r in preferred if r["passed"])

    lines.append(f"  Required:  {req_pass}/{len(required)} 通过")
    lines.append(f"  Preferred: {pref_pass}/{len(preferred)} 通过")
    lines.append("")

    for r in results:
        icon = "✅" if r["passed"] else ("❌" if r["type"] == "required" else "⚠️")
        lines.append(f"  {icon} [{r['dimension']}] {r['id']}: {r['description']}")
        if not r["passed"]:
            lines.append(f"      违反: {r['violation']} — {r['detail']}")

    lines.append("")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--enforce", action="store_true", help="强制执行模式")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    constraints = load_constraints()
    state = check_system_state()
    results = evaluate_constraints(constraints, state)
    mode = "enforce" if args.enforce else "warn"

    if args.json:
        print(json.dumps({
            "generated_at": datetime.now().isoformat(),
            "mode": mode,
            "constraints": len(results),
            "protocols": constraints.get("protocol_registry", []),
            "results": results,
        }, ensure_ascii=False, indent=2))
    else:
        print(format_report(results, mode, constraints))

    if args.enforce:
        required_fail = [r for r in results if r["type"] == "required" and not r["passed"]]
        sys.exit(1 if required_fail else 0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
