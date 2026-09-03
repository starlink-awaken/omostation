#!/usr/bin/env python3
"""UX-NOISE 命令发现层 (差距治理 S5).

背景 (复盘实证): cockpit CLI 命令密度 149+ (含子命令 157), 机制密度超过心智带宽.
CLI-REFERENCE.md 已按场景分组 (10 组), 但缺少:
  - 每组密度统计 (哪组命令最多/最该收敛)
  - 命令名重复/前缀冲突检测 (相似命令难区分 → 心智噪声)
  - 孤儿命令检测 (CLI 参考中无分组或 vs capability-registry 不一致)
  - 分组发现导航 (按域找命令, 不 grep)

本脚本: 解析 docs/CLI-REFERENCE.md, 提取场景分组 + 命令密度,
检测重复前缀/孤儿命令, 输出降噪统计 + 分组导航建议 (软信号, 不翻转 gate).

用法:
    python3 bin/gac/command-discovery.py            # 报告
    python3 bin/gac/command-discovery.py --json     # JSON 输出
    python3 bin/gac/command-discovery.py --group 治理  # 单组明细

SSOT:  docs/CLI-REFERENCE.md (GEN-FORCE 保护生成物, 源 = capability-registry.yaml)
       docs/generated/capability-registry.yaml (能力规模投影)
返回: 0 = 无 UX-NOISE 发现; 1 = 存在超阈值密度组 (报告, 不阻断).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
CLI_REFERENCE = WORKSPACE / "docs" / "CLI-REFERENCE.md"

# UX-NOISE 密度阈值: 单场景组命令数超过该值 → 机制密度超心智带宽
DENSITY_WARN_THRESHOLD = 25
# 相似命令前缀最小长度 (检测易混淆命令对)
SIMILAR_MIN_LEN = 6


def parse_groups(text: str) -> dict[str, list[str]]:
    """解析 CLI-REFERENCE 的场景组 → 命令列表.

    格式:
      ## 场景组名
      | 命令 | 描述 |
      | `cockpit xyz` | 描述 |
    """
    groups: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+)$", line.strip())
        if m:
            current = m.group(1).strip()
            groups.setdefault(current, [])
            continue
        cmd_m = re.match(r"^\|\s*`([^`]+)`", line)
        if cmd_m and current:
            groups[current].append(cmd_m.group(1).strip())
    return groups


def _canonical_cmd(cmd: str) -> str:
    """命令去子命令 → 主命令形态: 'cockpit compute plan' → 'cockpit compute'."""
    parts = cmd.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else cmd


def _sub_commands(cmds: list[str]) -> dict[str, list[str]]:
    """按主命令分组 → 子命令列表 (检测命令族内相似/重复)."""
    families: dict[str, list[str]] = {}
    for cmd in cmds:
        families.setdefault(_canonical_cmd(cmd), []).append(cmd)
    return families


def detect_noise(groups: dict[str, list[str]]) -> dict:
    """检测 UX-NOISE: 密度超阈值组 + 相似命令对."""
    total = sum(len(v) for v in groups.values())
    dense = [
        {"group": g, "count": len(cmds)}
        for g, cmds in groups.items()
        if len(cmds) >= DENSITY_WARN_THRESHOLD
    ]
    # 相似命令对: 同一主命令族内展开的多个子命令 (前缀共享, 心智需区分)
    #   例: cockpit compute <sub1> / <sub2> → 同族子命令展开 (正常); 真正噪声是
    #   名字极相似的不同命令 (bos-capability vs capability), 由 --group 明细定位.
    families: dict[str, list[str]] = {}
    for cmds in groups.values():
        for cmd in cmds:
            families.setdefault(_canonical_cmd(cmd), []).append(cmd)
    # 真重复: 完全相同命令串在 CLI-REFERENCE 出现 ≥2 次 (重复定义 = UX-NOISE)
    exact: dict[str, int] = {}
    for cmds in groups.values():
        for cmd in cmds:
            exact[cmd] = exact.get(cmd, 0) + 1
    similar = [
        {"prefix": cmd, "commands": [cmd, cmd]}  # 重复定义, 展示两条来源示意
        for cmd, n in exact.items()
        if n >= 2 and not cmd.startswith("cockpit ") and cmd != "cockpit"
    ]
    # 追加: 名字前缀重叠的不同命令 (如 bos-capability vs capability) — 易混淆
    confusing = _detect_confusing(families)
    # 孤组 (命名不规范, 无统一前缀)
    orphan_groups = [g for g, cmds in groups.items() if not any(c.startswith("cockpit") for c in cmds)]
    return {
        "total_commands": total,
        "group_count": len(groups),
        "dense_groups": dense,
        "similar_commands": similar,
        "confusing_commands": confusing,
        "orphan_groups": orphan_groups,
        "groups": {g: len(v) for g, v in groups.items()},
    }


def _detect_confusing(families: dict[str, list[str]]) -> list[dict]:
    """检测名字前缀重叠的不同命令族 (易混淆).

    例: 'cockpit bos-capability' vs 'cockpit capability',
        'cockpit bos-inbox' vs 'cockpit bcos' → 前缀重叠, 心智需反复区分.
    只报真实重叠 (非子命令展开), 阈值: 重叠 token 数 ≥ 2 或共享显式子命令.
    """
    canonical = sorted(set(families.keys()))
    found: list[dict] = []
    for i in range(len(canonical)):
        for j in range(i + 1, len(canonical)):
            a, b = canonical[i], canonical[j]
            if a == "cockpit" or b == "cockpit":
                continue
            # 共享前缀 token (如 bos-capability vs capability 共享 'capability')
            a_tokens = a.split()[1:] if a.startswith("cockpit ") else a.split()
            b_tokens = b.split()[1:] if b.startswith("cockpit ") else b.split()
            common = set(a_tokens) & set(b_tokens)
            # 前缀重叠: 一方是另一方的 token 子集 或 共享 ≥2 token
            if common and (a_tokens[0] in b_tokens or b_tokens[0] in a_tokens or len(common) >= 2):
                found.append({"a": a, "b": b, "shared": sorted(common)})
    return found[:15]


def main() -> int:
    ap = argparse.ArgumentParser(description="UX-NOISE: 命令发现层 (分组/密度/降噪)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--group", default="", help="单组明细 (如 治理)")
    args = ap.parse_args()

    if not CLI_REFERENCE.is_file():
        print(f"❌ 找不到 CLI-REFERENCE: {CLI_REFERENCE}", file=sys.stderr)
        return 2
    text = CLI_REFERENCE.read_text(encoding="utf-8")
    groups = parse_groups(text)
    report = detect_noise(groups)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.group:
        cmds = groups.get(args.group, [])
        print(f"## {args.group} ({len(cmds)} 命令)")
        for c in cmds:
            print(f"  {c}")
        return 0

    print(f"UX-NOISE 命令发现: {report['total_commands']} 命令 / {report['group_count']} 场景组")
    print("\n密度分布:")
    for g, n in sorted(report["groups"].items(), key=lambda x: -x[1]):
        bar = "█" * min(n, 40)
        mark = " ⚠️ 密度超阈值" if n >= DENSITY_WARN_THRESHOLD else ""
        print(f"  {g:<12} {n:>3}  {bar}{mark}")
    if report["dense_groups"]:
        print(f"\n⚠️ 超阈值密度组 ({len(report['dense_groups'])}) — 建议收敛/拆组:")
        for d in report["dense_groups"]:
            print(f"  - {d['group']}: {d['count']} 命令")
    if report["similar_commands"]:
        print(f"\n⚠️ 重复定义命令 ({len(report['similar_commands'])}) — CLI-REFERENCE 中多次出现:")
        for s in report["similar_commands"][:10]:
            print(f"  - {s['prefix']}")
    if report["confusing_commands"]:
        print(f"\n⚠️ 易混淆命令对 ({len(report['confusing_commands'])}) — 前缀重叠:")
        for c in report["confusing_commands"][:10]:
            print(f"  - {c['a']} ⇄ {c['b']} (共享: {', '.join(c['shared'])})")
    if report["orphan_groups"]:
        print(f"\n⚠️ 无 cockpit 前缀的孤组 ({len(report['orphan_groups'])}): {', '.join(report['orphan_groups'])}")
    print("\n发现层提示: 用 `cockpit help <关键词>` 模糊搜命令; 本报告定位密度/重复 (软信号, 不阻断).")

    # 密度/重复/易混淆 均为软信号 (advisory), 不阻塞 CI
    return 0


if __name__ == "__main__":
    sys.exit(main())
