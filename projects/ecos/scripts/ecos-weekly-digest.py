#!/usr/bin/env python3
"""
eCOS v5 Phase 7.6 — 每周健康摘要 (ecos-weekly-digest)
=========================================================
读取 SLA 数据 + 最新健康检查结果，生成每周趋势报告。

用法:
    python3 ecos-weekly-digest.py
    python3 ecos-weekly-digest.py --json
    python3 ecos-weekly-digest.py --output ~/Documents/驾驶舱/CARDS/health-digest.md
"""

import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import subprocess


SCRIPTS = Path.home() / ".ecos" / "scripts"
DOCS = Path.home() / "Documents"


def run_script(name: str, args: list[str] = None) -> str:
    """运行脚本并捕获输出"""
    script = SCRIPTS / name
    if not script.exists():
        return f"⚠️ 脚本缺失: {script}"
    try:
        cmd = ["python3", str(script)]
        if args:
            cmd.extend(args)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"⚠️ 执行失败: {e}"


def format_digest(entries: list[dict]) -> str:
    """生成 Markdown 健康摘要"""
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    lines = []
    lines.append(f"# 健康摘要 — {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> 自动生成 · eCOS v5 Phase 7.6 · 自治运维")
    lines.append("")

    # SLA
    lines.append("## SLA 指标")
    sla = run_script("ecos-sla-tracker.py", ["--json"])
    if sla and not sla.startswith("⚠"):
        try:
            data = json.loads(sla)
            lines.append(f"- Uptime: **{data['uptime']}%**")
            lines.append(f"- 连续通过: **{data['consecutive_passes']}** 次")
            lines.append(f"- 总检查: {data['total']} 次")
            if data.get("last_failure"):
                lf = data["last_failure"]
                lines.append(f"- 😴 最近失败: {lf.get('timestamp','?')[:10]} — {lf.get('detail','?')[:60]}")
            else:
                lines.append(f"- ✅ 最近失败: 无")
        except (json.JSONDecodeError, KeyError):
            lines.append(f"- ⚠️ SLA 数据解析失败")
    else:
        lines.append(f"- ⏳ SLA 数据累积中")
    lines.append("")

    # 覆盖率
    lines.append("## 覆盖率")
    cov = run_script("x3-coverage-report.py", ["--json"])
    if cov:
        # Extract overall ratio
        try:
            data = json.loads(cov)
            # Parse from depth
            depth = data.get("depth", {})
            dims = data.get("coverage", {})
            for dim in ["X1", "X2", "X3"]:
                d = dims.get(dim, {})
                lines.append(f"- {dim}: 二值 **{d.get('ratio', 0)*100:.0f}%**")
        except (json.JSONDecodeError, KeyError):
            pass
    lines.append("")

    # half_life 协议衰减
    lines.append("## 协议价值衰减")
    lines.append("")
    validator = DOCS / "@学习进化" / "_knowledge" / "10-systems" / "基建架构" / "ecos-constraint-validator.py"
    if validator.exists():
        import subprocess
        try:
            r = subprocess.run(["python3", str(validator), "--json"], capture_output=True, text=True, timeout=30)
            constraint = r.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            constraint = ""
    else:
        constraint = ""
    if constraint:
        try:
            data = json.loads(constraint)
            for p in data.get("protocols", []):
                intro = datetime.strptime(p["introduced"], "%Y-%m-%d")
                age = (now - intro).days
                decay = min(1.0, age / p["half_life_days"]) if p["half_life_days"] > 0 else 1.0
                remaining = max(0, (1 - decay) * 100)
                icon = "🟢" if remaining > 50 else ("🟡" if remaining > 10 else "🔴")
                lines.append(f"- {icon} {p['id']}: 剩余价值 {remaining:.0f}% "
                             f"(引入 {age}d / 半衰期 {p['half_life_days']}d)")
        except (json.JSONDecodeError, KeyError):
            pass
    lines.append("")

    # 风险项
    lines.append("## 风险项")
    try:
        constraint_data = json.loads(constraint) if constraint else {}
        for p in constraint_data.get("protocols", []):
            intro = datetime.strptime(p["introduced"], "%Y-%m-%d")
            age = (now - intro).days
            decay = min(1.0, age / p["half_life_days"]) if p["half_life_days"] > 0 else 1.0
            if decay > 1.0:
                lines.append(f"- 🔴 {p['id']} 已超半衰期 ({age}d > {p['half_life_days']}d) — 建议审查")
    except (json.JSONDecodeError, KeyError):
        pass

    if not any("半衰期" in l for l in lines[-5:]):
        lines.append("- ✅ 无重大风险")
    lines.append("")

    lines.append("---")
    lines.append(f"> 生成: {now.isoformat()} · 下次: {(now + timedelta(days=7)).strftime('%Y-%m-%d')}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 每周健康摘要")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=str, default=None,
                        help="输出路径 (默认 stdout)")
    args = parser.parse_args()

    # 读 SLA 数据
    sla_file = Path.home() / ".ecos" / "sla" / "history.jsonl"
    entries = []
    if sla_file.exists():
        with open(sla_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    text = format_digest(entries)

    if args.json:
        print(json.dumps({"generated_at": datetime.now().isoformat(),
                          "digest": text}, ensure_ascii=False, indent=2))
    elif args.output:
        output_path = Path(args.output)
        output_path.write_text(text)
        print(f"  ✅ 健康摘要已生成: {output_path}")
    else:
        print(text)


if __name__ == "__main__":
    main()
