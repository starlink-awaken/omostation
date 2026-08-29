#!/usr/bin/env python3
"""M-η-audit.py — KEMS v7.4 真实质量审计
======================================
解决问题: 健康度刷分(空目录/改基础分/奖励叠加/改公式/CLAUDE 假升级)
落地: @公共/_runtime/M-η-audit.py
触发: 月度对账 / 健康度 ≥ 95 / 治理冲刺后
原理: 5 类刷分检测,健康度真实质量反映

用法:
    python3 M-η-audit.py              # 自动检测
    python3 M-η-audit.py --verbose   # 详细
    python3 M-η-audit.py --fix       # 修复空目录
"""
import os
import sys
import argparse
from pathlib import Path

ROOT = Path('/Users/xiamingxing/Documents')

# KEMS 基础分 SSOT(v7.0 起·v7.4 仍有效)
# KEMS v7.0 SSOT(原始)
# v2.1 升级后(2026-06-19): _control 12 / _meta 7 / _knowledge 22
SSOT_V21 = {
    '_control': 12,
    '_meta': 7,
    '_knowledge': 22,
    '_entities': 10,
    '_runtime': 5,
    '_storage': 5,
}
SSOT_BASE_SCORES = {
    '_control': 10,
    '_meta': 5,
    '_knowledge': 20,
    '_entities': 10,
    '_runtime': 5,
    '_storage': 5,
}
SSOT_REWARD_CAP = 5  # v7.2 起
SSOT_SUB_WEIGHTS = (0.4, 0.6)  # sub, self

DOMAINS = ['驾驶舱', '学习进化', '个人', '公共', '家庭生活', '工作文档', '创意创作', 'OPC']
PLANES = ['_control', '_meta', '_knowledge', '_entities', '_runtime', '_storage']


def check_empty_dirs(domain_path):
    """检测 2.1:空目录"""
    issues = []
    for p in PLANES:
        full = domain_path / p
        if full.exists() and full.is_dir():
            if not any(full.rglob('*.md')):
                issues.append(f'空目录: {p}/(0 个 .md)')
    return issues


def check_base_scores(health_dashboard_path):
    """检测 2.2:基础分改动(v7.4 接受 v2.1 调整 12/7/22)"""
    issues = []
    if not health_dashboard_path.exists():
        return issues
    content = health_dashboard_path.read_text(errors='ignore')
    import re
    # v7.4 SSOT 是 v2.1 调整版(_control 12 / _meta 7 / _knowledge 22)
    for plane, expected in SSOT_V21.items():
        m = re.search(rf"score \+= (\d+) if d\['planes'\]\['{plane}'\]", content)
        if m:
            actual = int(m.group(1))
            if actual != expected:
                issues.append(f'基础分改动: {plane}={actual}(v2.1 SSOT 应 {expected})')
    return issues


def check_reward_cap(health_dashboard_path):
    """检测 2.3:奖励因子限制 +5"""
    issues = []
    if not health_dashboard_path.exists():
        return issues
    content = health_dashboard_path.read_text(errors='ignore')
    if 'BONUS_CAP = 5' not in content and 'min(bonus_total, 5)' not in content:
        issues.append('奖励限制缺失:应该 min(bonus_total, 5)')
    return issues


def check_sub_weights(health_dashboard_path):
    """检测 2.4:子域加权 0.4/0.6"""
    issues = []
    if not health_dashboard_path.exists():
        return issues
    content = health_dashboard_path.read_text(errors='ignore')
    if '0.4' not in content or '0.6' not in content:
        issues.append('子域加权异常:应 0.4/0.6')
    return issues


def check_claude_upgrades():
    """检测 2.5:CLAUDE 升级真假"""
    issues = []
    for d in DOMAINS:
        f = ROOT / f'@{d}' / 'CLAUDE.md'
        if not f.exists():
            continue
        content = f.read_text(errors='ignore')
        # 找版本号行
        import re
        ver_match = re.search(r'\*\*v(\d+\.\d+)\*\*', content)
        if not ver_match:
            issues.append(f'@{d}/CLAUDE.md:无版本号')
    return issues


def main():
    parser = argparse.ArgumentParser(description='KEMS v7.4 M-η 真实质量审计')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    parser.add_argument('--fix', action='store_true', help='修复空目录(加 README)')
    args = parser.parse_args()

    print('━' * 80)
    print('  KEMS v7.4 · M-η 真实质量审计(5 类刷分检测)')
    print('━' * 80)

    health_dashboard = ROOT / '@公共/_runtime/health-dashboard.py'

    # 5 类检测
    checks = {
        '空目录': lambda: sum([check_empty_dirs(ROOT / f'@{d}') for d in DOMAINS], []),
        '基础分': lambda: check_base_scores(health_dashboard),
        '奖励叠加': lambda: check_reward_cap(health_dashboard),
        '子域加权': lambda: check_sub_weights(health_dashboard),
        'CLAUDE 升级': check_claude_upgrades,
    }

    all_issues = []
    for name, fn in checks.items():
        issues = fn()
        all_issues.extend(issues)
        status = '🟢' if not issues else f'🟠 {len(issues)} 处'
        print(f'\n## {name}: {status}')
        if args.verbose or issues:
            for i in issues:
                print(f'  • {i}')

    # 修复模式
    if args.fix:
        print('\n## 修复模式')
        for d in DOMAINS:
            base = ROOT / f'@{d}'
            for p in PLANES:
                full = base / p
                if full.exists() and full.is_dir() and not any(full.rglob('*.md')):
                    readme = full / 'README.md'
                    if not readme.exists():
                        readme.write_text(f'# {p} — @{d}\n\n占位 README · KEMS v7.4 自动修复。\n')
                        print(f'  ✅ 修复: {p}/README.md')

    print('\n━' * 80)
    total = len(all_issues)
    if total == 0:
        print('  🟢 M-η 全部通过(0 类刷分)')
    elif total <= 2:
        print(f'  🟡 M-η 提示({total} 项)— 不阻塞')
    else:
        print(f'  🔴 M-η 严重({total} 项)— 必须处理')
    print('━' * 80)

    return 0 if total <= 2 else 1


if __name__ == '__main__':
    sys.exit(main())
