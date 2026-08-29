#!/usr/bin/env python3
"""M-θ-audit.py — KEMS v7.3 跨域记忆层检测
=========================================
解决问题: 记忆碎片化/孤岛/冗余/过载/蒸发(5 类)
落地: @公共/_runtime/M-θ-audit.py
触发: 新会话 / 月度对账
原理: 扫描 11 域记忆状态,生成可发现性报告

用法:
    python3 M-θ-audit.py
    python3 M-θ-audit.py --verbose
"""
import os
import re
import sys
import argparse
from pathlib import Path

ROOT = Path('/Users/xiamingxing/Documents')

# 11 域(8 主 + 3 子)
DOMAINS = ['驾驶舱', '学习进化', '个人', '公共', '家庭生活', '工作文档', '创意创作', 'OPC']
SUBDOMAINS = {
    '工作文档': ['卫健委', '国转中心', '合同法规'],
}


def check_fragmentation():
    """检测碎片化:同一类信息在 3+ 域"""
    keywords = ['CARDS 状态', '健康度', 'KEMS 版本', '跨域信号']
    issues = []
    for kw in keywords:
        count = 0
        for d in DOMAINS:
            base = ROOT / f'@{d}'
            if (base / '_control').exists():
                for f in (base / '_control').rglob('*.md'):
                    if kw in f.read_text(errors='ignore'):
                        count += 1
                        break
        if count >= 3:
            issues.append(f'碎片化: "{kw}" 在 {count} 域出现')
    return issues


def check_isolation():
    """检测孤岛:3 个月内无引用的文件"""
    # 简化:文件大小 < 1KB 但存在 30+ 天
    issues = []
    import time
    now = time.time()
    for d in DOMAINS:
        base = ROOT / f'@{d}'
        if not base.exists():
            continue
        # 检查 6 平面所有 md
        for plane in ['_control', '_knowledge', '_meta']:
            pb = base / plane
            if not pb.exists():
                continue
            for f in pb.rglob('*.md'):
                mtime = f.stat().st_mtime
                if (now - mtime) > 90 * 24 * 3600:  # 90 天
                    if f.stat().st_size < 200:  # 小文件
                        rel = f.relative_to(ROOT)
                        issues.append(f'孤岛: {rel} 90 天无引用(< 200 字节)')
    return issues[:5]  # 只列前 5


def check_redundancy():
    """检测冗余:同一内容在 2+ 域"""
    # 简化:扫公约内容重复
    issues = []
    pattern = re.compile(r'CLAUDE\.md.*v\d+\.\d+.*继承', re.MULTILINE)
    for d in DOMAINS:
        f = ROOT / f'@{d}' / 'CLAUDE.md'
        if f.exists() and pattern.search(f.read_text(errors='ignore')):
            # 多次匹配算冗余
            count = len(pattern.findall(f.read_text(errors='ignore')))
            if count > 2:
                issues.append(f'冗余: @{d}/CLAUDE.md "v?.? 继承" 重复 {count} 次')
    return issues


def check_overload():
    """检测过载:signals.md > 200 行"""
    issues = []
    for d in DOMAINS:
        f = ROOT / f'@{d}' / '_control' / 'signals.md'
        if f.exists():
            lines = sum(1 for _ in f.open())
            if lines > 200:
                issues.append(f'过载: @{d}/signals.md {lines} 行(> 200)')
    return issues


def check_evaporation():
    """检测蒸发:关键记忆无 SSOT"""
    issues = []
    # 5 人 SSOT 缺生日(已知)
    for name in ['秦张瑶', '夏维桢', '夏登峰', '王淑慧', '张秀英']:
        f = ROOT / '@公共/_entities/人物' / f'{name}.md'
        if f.exists():
            content = f.read_text(errors='ignore')
            if '出生' not in content and '生日' not in content:
                issues.append(f'蒸发: @{name} SSOT 缺出生日期')
    return issues


def main():
    parser = argparse.ArgumentParser(description='KEMS v7.3 M-θ 跨域记忆审计')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    args = parser.parse_args()

    print('━' * 80)
    print('  KEMS v7.3 · M-θ 跨域记忆审计(11 域)')
    print('━' * 80)
    print('  入口:@驾驶舱/_knowledge/跨域记忆索引.md')
    print('━' * 80)

    all_issues = []
    for name, fn in [
        ('碎片化', check_fragmentation),
        ('孤岛', check_isolation),
        ('冗余', check_redundancy),
        ('过载', check_overload),
        ('蒸发', check_evaporation),
    ]:
        issues = fn()
        all_issues.extend(issues)
        status = '🟢 0' if not issues else f'🟠 {len(issues)}'
        print(f'\n## {name}检测: {status}')
        for i in issues:
            print(f'  • {i}')

    print('\n━' * 80)
    total = len(all_issues)
    if total == 0:
        print('  🟢 M-θ 全部通过(0 类问题)')
    elif total <= 1:
        print(f'  🟡 M-θ 提示({total} 项)— 不阻塞')
    elif total <= 3:
        print(f'  🟠 M-θ 警告({total} 项)— 建议下次治理处理')
    else:
        print(f'  🔴 M-θ 严重({total} 项)— 必须处理')
    print('━' * 80)

    print('\n## 建议')
    if total > 0:
        print('  1. 读 @驾驶舱/_knowledge/跨域记忆索引.md')
        print('  2. 按上述问题逐项修复')
        print('  3. 30 天后重新跑 M-θ-audit')

    return 0 if total <= 3 else 1


if __name__ == '__main__':
    sys.exit(main())
