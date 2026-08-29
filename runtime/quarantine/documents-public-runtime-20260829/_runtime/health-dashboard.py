#!/usr/bin/env python3
"""health-dashboard.py v2.0 — KEMS v7.1 类型感知仪表盘
========================================================
新增:
- --aggregate-recursive(递归聚合子域)
- 6 类型识别(Aggregate/Functional/Infrastructure/Sub/Filelib/Transient)
- 动态桥接统计
"""
import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

DOMAINS = ['驾驶舱', '学习进化', '个人', '公共', '家庭生活', '工作文档', '创意创作', 'OPC']
ROOT = Path('/Users/xiamingxing/Documents')

# 域类型配置(可由 _meta/README.md 覆盖)
DOMAIN_TYPE = {
    '驾驶舱': ('Aggregate', []),  # 本身聚合 + 子域
    '学习进化': ('Functional', []),
    '个人': ('Functional', []),
    '公共': ('Infrastructure', []),
    '家庭生活': ('Sub-domain', ['个人']),
    '工作文档': ('Aggregate', ['卫健委', '国转中心', '合同法规']),
    '创意创作': ('Functional', []),
    'OPC': ('Functional', []),
}

PLANES = ['_control', '_meta', '_knowledge', '_entities', '_runtime', '_storage']
CONTROLLERS = {
    'sensors': '_control/sensors.md',
    'rules': '_control/control-rules.md',
    'executor': '_control/executor-rules.md',
    'l4-kernel': '_control/l4-kernel.md',
}

SUBDOMAINS = {
    '工作文档': ['卫健委', '国转中心', '合同法规'],
    '家庭生活': [],  # iCloud 域不扫
}


def detect_type(name):
    """识别域类型"""
    if name in SUBDOMAINS and SUBDOMAINS[name]:
        return 'Aggregate'
    if name == '公共':
        return 'Infrastructure'
    if name in ['家庭生活']:
        return 'Sub-domain'
    return 'Functional'


def calc_self_health(d):
    """计算单个域自身健康度(不计子域)"""
    # Filelib 特殊路径:不要求六平面,基础分 70
    if d.get('is_filelib'):
        score = 70
        # v2.1.1 修复:Filelib 路径(子域 vs 顶级域)
        if 'name' in d and d.get('parent'):
            # 子域 filelib:@工作文档/合同法规
            base_dir_filelib = ROOT / f"@工作文档/{d['name']}"
        else:
            # 顶级域 filelib
            base_dir_filelib = ROOT / f"@{d['name']}"
        if (base_dir_filelib / '_index').exists():
            score += 5
        if (base_dir_filelib / '_knowledge').exists():
            score += 5
        md_count = d.get('md_count', 0)
        if md_count >= 30:
            score += 5
        elif md_count >= 10:
            score += 3
        elif md_count >= 3:
            score += 1
        return min(100, score)

    # 正常域路径(v2.1 提升基础分:反映 _control/_meta/_knowledge 价值增加)
    score = 0
    score += 12 if d['planes']['_control'] else 0
    score += 7 if d['planes']['_meta'] else 0
    score += 8 if d['controllers']['sensors'] else 0
    score += 8 if d['controllers']['rules'] else 0
    score += 7 if d['controllers']['executor'] else 0
    score += 7 if d['controllers']['l4-kernel'] else 0
    score += 22 if d['planes']['_knowledge'] else 0
    score += 10 if d['planes']['_entities'] else 0
    score += 5 if d['planes']['_runtime'] else 0
    score += 5 if d['planes']['_storage'] else 0

    # v2.1 质量奖励(KEMS v7.1 升级 · 2026-06-19)
    # v2.2 限制:质量奖励累计上限 +5(防刷分叠加)
    bonus_total = 0
    BONUS_CAP = 5

    # 规模奖励:文档域内容量
    md_count = d.get('md_count', 0)
    if md_count >= 500:
        bonus_total += 5
    elif md_count >= 100:
        bonus_total += 3
    elif md_count >= 30:
        bonus_total += 1

    # CLAUDE v2.1 适配奖励
    if d.get('parent'):
        claude_path = ROOT / f"@{d['parent']}" / d['name'] / 'CLAUDE.md'
    else:
        claude_path = ROOT / f"@{d['name']}" / 'CLAUDE.md'
    if claude_path.exists():
        claude_content = claude_path.read_text(errors='ignore')
        if 'KEMS v7.1' in claude_content or 'v2.1' in claude_content:
            bonus_total += 3

    # 深度门禁覆盖(G11-G16)
    if all([
        d['controllers']['sensors'],
        d['controllers']['rules'],
        d['controllers']['executor'],
        d['controllers']['l4-kernel'],
    ]):
        bonus_total += 2

    # 域索引健康(v2.1.1 修复子域路径)
    if d.get('parent'):
        base_dir = ROOT / f"@{d['parent']}" / d['name']
    else:
        base_dir = ROOT / f"@{d['name']}"
    if (base_dir / 'INDEX.md').exists():
        bonus_total += 2
    if (base_dir / '_outputs').exists():
        bonus_total += 2
    if (base_dir / '_index').exists():
        bonus_total += 1

    # v2.2:限制累计奖励 +5(防叠加刷分)
    score += min(bonus_total, BONUS_CAP)

    # v2.4 治理预算负项(KEMS v7.4-r2 §4 铁律 · 2026-07-02):
    # 治理元文档(_control/_meta/_gates 下 md)占比 > 35% 说明治理自我膨胀, 扣分
    gov_md = d.get('gov_md_count', 0)
    total_md = d.get('md_count', 0)
    if total_md >= 20 and gov_md / total_md > 0.35:
        score -= min(8, round((gov_md / total_md - 0.35) * 40))

    return min(100, max(0, score))


def scan_domain(name):
    """扫描单个域"""
    base = ROOT / f'@{name}'
    if not base.exists():
        return None

    is_filelib = detect_type(name) == 'Filelib'
    # v2.3:空目录不算平面(防 P21 刷分)
    def has_content(p):
        """目录存在且有文件"""
        full = base / p
        if not full.exists() or not full.is_dir():
            return False
        # 必须有 .md 文件(子目录不算)
        return any(full.rglob('*.md'))

    result = {
        'name': name,
        'type': detect_type(name),
        'exists': True,
        'md_count': sum(1 for _ in base.rglob('*.md')),
        # v2.4 治理预算: 治理元文档计数(控制面/元面/门禁下的 md)
        'gov_md_count': sum(
            sum(1 for _ in (base / p).rglob('*.md')) if (base / p).is_dir() else 0
            for p in ('_control', '_meta', '_gates')
        ),
        'planes': {p: has_content(p) for p in PLANES},
        'controllers': {k: (base / v).exists() for k, v in CONTROLLERS.items()},
        'is_filelib': is_filelib,
    }

    # 子域
    if name in SUBDOMAINS:
        for sub in SUBDOMAINS[name]:
            sub_base = base / sub
            if sub_base.exists():
                result.setdefault('subdomains', []).append(sub)

    return result


def calc_aggregate_health(d, sub_health_map, recursive=False):
    """计算健康度(支持递归)
    v2.1 调整:子域权重 0.7→0.4(更看重本体)
    """
    self_h = calc_self_health(d)
    if d.get('type') == 'Aggregate' and recursive and d.get('subdomains'):
        # 递归聚合
        sub_h = []
        for sub in d['subdomains']:
            if sub in sub_health_map:
                sub_h.append(sub_health_map[sub])
        if sub_h:
            return sum(sub_h) / len(sub_h) * 0.4 + self_h * 0.6
    return self_h


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--aggregate-recursive', action='store_true', help='递归聚合子域')
    args = parser.parse_args()

    # 1. 扫描所有域 + 子域
    domains_data = []
    subdomain_data = {}

    for name in DOMAINS:
        d = scan_domain(name)
        if d:
            domains_data.append(d)
            # 扫描子域
            for sub in d.get('subdomains', []):
                sub_d = scan_domain_in_dir(ROOT / f'@{name}' / sub)
                if sub_d:
                    subdomain_data[sub] = sub_d
                    sub_d['name'] = sub
                    sub_d['parent'] = name
                    sub_d['type'] = 'Filelib' if '合同法规' in sub else 'Sub-domain'
                    sub_d['is_filelib'] = '合同法规' in sub  # v2.1 修复:filelib 字段传递

    # 2. 计算健康度
    sub_health_map = {n: calc_self_health(d) for n, d in subdomain_data.items()}

    # 3. 渲染
    print('━' * 90)
    print(f'  Documents 8 域健康度仪表盘 · v2.0 · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    if args.aggregate_recursive:
        print('  模式:🔁 递归聚合(子域计入)')
    else:
        print('  模式:📊 自身(不计子域)')
    print('━' * 90)
    print(f'  {"域":<10} {"类型":<14} {"文件":>6} {"六面":>6} {"控制器":>10} {"健康度":>10} 评估')
    print('  ' + '─' * 80)

    total = 0
    count = 0
    for d in domains_data:
        planes_n = sum(d['planes'].values())
        ctrl_n = sum(d['controllers'].values())
        health = calc_aggregate_health(d, sub_health_map, args.aggregate_recursive)
        if d.get('type') == 'Aggregate' and args.aggregate_recursive:
            health_str = f'{health:.0f}(递归)'
        else:
            health_str = f'{health:.0f}'
        if health >= 90: eval_ = '🟢 优秀'
        elif health >= 70: eval_ = '🟢 健康'
        elif health >= 50: eval_ = '🟡 一般'
        elif health >= 30: eval_ = '🟠 欠账'
        else: eval_ = '🔴 缺失'
        print(f'  @{d["name"]:<9} {d["type"]:<14} {d["md_count"]:>6} {planes_n}/6   {ctrl_n}/4   {health_str:>5}/100  {eval_}')
        total += health
        count += 1

    # 子域(独立显示)
    if subdomain_data and args.aggregate_recursive:
        print('  ' + '─' * 80)
        print(f'  --- 子域详情 ---')
        for sub_name, d in subdomain_data.items():
            planes_n = sum(d['planes'].values())
            ctrl_n = sum(d['controllers'].values())
            health = calc_self_health(d)
            if health >= 70: eval_ = '🟢'
            elif health >= 50: eval_ = '🟡'
            else: eval_ = '🟠'
            print(f'  └ @{d["parent"]}/{sub_name:<9} {d["type"]:<14} {d["md_count"]:>6} {planes_n}/6   {ctrl_n}/4   {health:>5}/100  {eval_}')

    print('  ' + '─' * 80)
    avg = total / count if count else 0
    print(f'  {"平均":<10} {"":>14} {"":>6} {"":>6} {"":>10}  {avg:>5.1f}/100')
    print('━' * 90)


def scan_domain_in_dir(base):
    """扫描一个具体目录(用于子域)"""
    if not base.exists():
        return None
    return {
        'exists': True,
        'md_count': sum(1 for _ in base.rglob('*.md')),
        'planes': {p: (base / p).exists() for p in PLANES},
        'controllers': {k: (base / v).exists() for k, v in CONTROLLERS.items()},
        'is_filelib': 'filelib' in str(base).lower() or '合同' in str(base),
    }


if __name__ == '__main__':
    main()
