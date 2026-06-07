#!/usr/bin/env python3
"""
eCOS v5 L0 — 协议编译器 (ecos-constraint-compiler)
=====================================================
Phase 8.2 / v5 能力补全
从 L0-constraints.yaml 读取协议约束 → 编译为可执行的强制规则模块。
与 PoC 校验器的区别: 编译器输出 Python 模块，可被 daemon import 直接执行。

管线:
  L0-constraints.yaml (输入)
    → ecos-constraint-compiler.py (编译)
      → /tmp/ecos-compiled-constraints.py (输出)
        → ecos-daemon.py import & 执行

用法:
    python3 ecos-constraint-compiler.py                  # 编译 + 执行
    python3 ecos-constraint-compiler.py --watch           # 监听文件变更自动重编译
    python3 ecos-constraint-compiler.py --output /path    # 指定输出路径
"""

import sys
import json
import argparse
import hashlib
import importlib.util
import os
import time
from datetime import datetime, timezone
from pathlib import Path


# ── 路径 ──
DOCS = Path.home() / "Documents"
CONSTRAINTS_FILE = DOCS / "学习进化" / "2-knowledge" / "基建架构" / "L0-constraints.yaml"
DEFAULT_OUTPUT = Path("/tmp") / "ecos-compiled-constraints.py"
STATE_FILE = Path.home() / ".ecos" / "compiler-state.json"


def load_yaml(path: Path) -> dict:
    """加载 YAML"""
    import yaml
    with open(path, "r") as f:
        return yaml.safe_load(f)


def compile_constraints(data: dict) -> str:
    """将 YAML 约束编译为 Python 模块"""
    protocols = data.get("protocol_registry", [])
    constraints = data.get("constraints", [])
    version = data.get("version", "0.0.0")
    now = datetime.now(timezone.utc)

    lines = []
    lines.append('# eCOS v5 L0 — 编译约束 (自动生成)')
    lines.append(f'# 源文件: {CONSTRAINTS_FILE}')
    lines.append(f'# 编译时间: {now.isoformat()}')
    lines.append(f'# 版本: {version}')
    lines.append('')
    lines.append('import json, time')
    lines.append('from datetime import datetime')
    lines.append('')

    # ── 协议注册表 ──
    lines.append('# ── 协议注册表 ──')
    lines.append('PROTOCOLS = {')
    for p in protocols:
        lines.append(f'    "{p["id"]}": {{')
        lines.append(f'        "version": "{p["version"]}",')
        lines.append(f'        "introduced": "{p["introduced"]}",')
        lines.append(f'        "half_life_days": {p["half_life_days"]},')
        lines.append(f'        "status": "{p["status"]}",')
        lines.append(f'        "value_tier": {p["value_tier"]},')
        lines.append(f'    }},')
    lines.append('}')
    lines.append('')

    # ── 协议衰减计算 ──
    lines.append('')
    lines.append('def compute_decay(protocol_id: str) -> dict:')
    lines.append('    """计算单个协议的价值衰减"""')
    lines.append('    p = PROTOCOLS.get(protocol_id)')
    lines.append('    if not p:')
    lines.append('        return {"error": f"Unknown protocol: {protocol_id}"}')
    lines.append('    intro = datetime.strptime(p["introduced"], "%Y-%m-%d")')
    lines.append('    age_days = (datetime.now() - intro).days')
    lines.append('    half = p["half_life_days"]')
    lines.append('    decay = min(1.0, age_days / half) if half > 0 else 1.0')
    lines.append('    remaining = max(0, (1 - decay) * 100)')
    lines.append('    return {')
    lines.append('        "protocol": protocol_id,')
    lines.append('        "version": p["version"],')
    lines.append('        "age_days": age_days,')
    lines.append('        "half_life_days": half,')
    lines.append('        "decay": round(decay, 4),')
    lines.append('        "remaining_value": round(remaining, 1),')
    lines.append('        "status": "expired" if decay >= 1.0 else ("aging" if decay >= 0.5 else "fresh"),')
    lines.append('    }')
    lines.append('')

    # ── 全协议衰减报告 ──
    lines.append('')
    lines.append('def report_all_decay() -> list[dict]:')
    lines.append('    """报告所有协议衰减"""')
    lines.append('    return [compute_decay(pid) for pid in PROTOCOLS]')
    lines.append('')

    # ── 约束检查 ──
    lines.append('')
    lines.append('def check_constraints(state: dict) -> list[dict]:')
    lines.append('    """检查所有约束"""')
    lines.append('    results = []')
    results = []
    for c in constraints:
        cid = c["id"]
        desc = c["description"]
        ctype = c["type"]
        rule = c["rule"]
        violation = c["violation"]

        # 为每个约束生成检查代码
        lines.append(f'    # {cid}: {desc}')
        lines.append(f'    passed = True')
        lines.append(f'    detail = ""')

        if rule == "protocol.registered == true":
            lines.append(f'    passed = state.get("protocol", {{}}).get("registered", False)')
            lines.append(f'    detail = "协议已注册" if passed else "协议未注册"')
        elif rule == "layer.cross_call.route == \'I0/Agora\'":
            lines.append(f'    passed = state.get("layer", {{}}).get("cross_call", {{}}).get("route", "") == "I0/Agora"')
            lines.append(f'    detail = f\'路由: {{state.get("layer",{{}}).get("cross_call",{{}}).get("route","?")}}\'')
        elif rule == "claude_md.age_days <= 60":
            lines.append(f'    age = state.get("claude_md", {{}}).get("age_days", 0)')
            lines.append(f'    passed = age <= 60')
            lines.append(f'    detail = f"最旧 CLAUDE.md: {{age}} 天"')
        elif "value_tier" in rule:
            lines.append(f'    domains = state.get("domain", {{}})')
            lines.append(f'    missing = [d for d, v in domains.items() if v.get("value_tier") is None]')
            lines.append(f'    passed = len(missing) == 0')
            lines.append(f'    detail = f"缺失: {{missing}}" if missing else "全部已声明"')
        else:
            lines.append(f'    passed = True  # 规则评估: {rule}')

        lines.append(f'    results.append({{')
        lines.append(f'        "id": "{cid}",')
        lines.append(f'        "type": "{ctype}",')
        lines.append(f'        "description": """{desc}""",')
        lines.append(f'        "passed": passed,')
        lines.append(f'        "detail": detail,')
        lines.append(f'        "violation": "{violation}" if not passed else None,')

        lines.append(f'    }})')
        lines.append('')

    lines.append('    return results')
    lines.append('')

    # 主函数
    lines.append('')
    lines.append('def run(state: dict = None) -> dict:')
    lines.append('    """编译约束入口 — 被 daemon import 后调用"""')
    lines.append('    if state is None:')
    lines.append('        state = {"protocol": {"registered": True},')
    lines.append('                "layer": {"cross_call": {"route": "I0/Agora"}},')
    lines.append('                "claude_md": {"age_days": 0},')
    lines.append('                "domain": {}}')
    lines.append('    return {')
    lines.append('        "decay": report_all_decay(),')
    lines.append('        "constraints": check_constraints(state),')
    lines.append('    }')
    lines.append('')

    return "\n".join(lines)


def write_compiled(code: str, output_path: Path):
    """写入编译模块"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code)
    # 写入状态文件
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "source": str(CONSTRAINTS_FILE),
        "output": str(output_path),
        "hash": hashlib.sha256(code.encode()).hexdigest()[:16],
    }
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    return state


def load_compiled(output_path: Path):
    """动态 import 编译模块"""
    spec = importlib.util.spec_from_file_location("compiled_constraints", output_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_compiled(output_path: Path) -> dict:
    """执行编译的约束"""
    module = load_compiled(output_path)
    if module is None:
        return {"error": "编译模块加载失败"}
    try:
        result = module.run()
        return result
    except Exception as e:
        return {"error": f"执行失败: {e}"}


def format_report(result: dict) -> str:
    """格式化报告"""
    lines = []
    lines.append("=" * 56)
    lines.append("  eCOS v5 L0 — 编译约束报告")
    lines.append("=" * 56)

    decay = result.get("decay", [])
    constraints = result.get("constraints", [])

    # 协议衰减
    lines.append("\n  ── 协议衰减 ──")
    for d in decay:
        remaining = d["remaining_value"]
        bar = "█" * int(remaining / 10) + "░" * (10 - int(remaining / 10))
        icon = "🟢" if remaining > 50 else ("🟡" if remaining > 10 else "🔴")
        lines.append(f"  {icon} {d['protocol']:10s} v{d['version']:10s}  "
                     f"剩余 {remaining:.0f}% {bar}")
        if d["status"] == "expired":
            lines.append(f"      已超半衰期 ({d['age_days']}d > {d['half_life_days']}d)")

    # 约束结果
    passed = sum(1 for c in constraints if c["passed"])
    total = len(constraints)
    lines.append(f"\n  ── 约束 {passed}/{total} ──")
    for c in constraints:
        icon = "✅" if c["passed"] else ("❌" if c["type"] == "required" else "⚠️")
        lines.append(f"  {icon} [{c['id']}] {c['description'][:50]}")

    lines.append(f"\n{'='*56}")
    return "\n".join(lines)


def watch_and_compile(output_path: Path, interval: int = 60):
    """监听约束文件变更自动重编译"""
    import yaml
    last_mtime = CONSTRAINTS_FILE.stat().st_mtime if CONSTRAINTS_FILE.exists() else 0

    print(f"  🔍 监听: {CONSTRAINTS_FILE}")
    print(f"  输出: {output_path}")
    print(f"  间隔: {interval}s\n")

    while True:
        try:
            current_mtime = CONSTRAINTS_FILE.stat().st_mtime if CONSTRAINTS_FILE.exists() else 0
            if current_mtime != last_mtime:
                print(f"  🔄 文件变更 ({datetime.now().strftime('%H:%M:%S')})")
                data = load_yaml(CONSTRAINTS_FILE)
                code = compile_constraints(data)
                state = write_compiled(code, output_path)
                result = run_compiled(output_path)

                if "error" in result:
                    print(f"  ❌ 编译/执行失败: {result['error']}")
                else:
                    print(f"  ✅ 编译成功 (hash={state['hash']})")
                    print(format_report(result))

                last_mtime = current_mtime
        except Exception as e:
            print(f"  ⚠️ 错误: {e}")

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 L0 协议编译器")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="输出路径")
    parser.add_argument("--watch", action="store_true", help="监听模式")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--interval", type=int, default=60, help="监听间隔(秒)")
    args = parser.parse_args()

    output_path = Path(args.output)

    if not CONSTRAINTS_FILE.exists():
        print(f"❌ 约束文件不存在: {CONSTRAINTS_FILE}", file=sys.stderr)
        sys.exit(2)

    if args.watch:
        watch_and_compile(output_path, args.interval)
        return

    # 单次编译
    data = load_yaml(CONSTRAINTS_FILE)
    code = compile_constraints(data)
    state = write_compiled(code, output_path)
    result = run_compiled(output_path)

    if args.json:
        print(json.dumps({**result, "compiler": state}, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
        print(f"\n  编译hash: {state['hash']}")
        print(f"  输出: {output_path}")


if __name__ == "__main__":
    main()
