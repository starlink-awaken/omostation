#!/usr/bin/env python3
"""
check-critical-path.py — 关键路径巡检（新建项目 8 月冲刺）
读取 key-milestones.yaml → 计算距今天数 → 核对缺口(gaps.yaml)与文件(申报材料目录) → 输出缺项清单

用法:
  python3 _runtime/check-critical-path.py          # 全量输出（含 ✅ 就绪项）
  python3 _runtime/check-critical-path.py --alert  # 只输出 🔴/🟡 缺项（供 controller 调用）
  python3 _runtime/check-critical-path.py --json   # JSON 输出（供 gen-dashboard 读取）

版本: v1.0 | 2026-08-01 | 机制迭代（里程碑 SSOT 化）
"""

import os, re, sys, json
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(os.environ.get('WEIJIAN_HOME', Path(__file__).parent.parent))
ROOT = str(BASE_DIR)
TODAY = date.today()

MILESTONE_FP = os.path.join(ROOT, '_control', 'key-milestones.yaml')
GAPS_FP = os.path.join(ROOT, '_entities', 'ontology', 'gaps.yaml')
REQ_DIR = os.environ.get('CP_REQ_DIR') or os.path.join(ROOT, '_knowledge', '业务资料', '信息化项目', '项目管理', '诊疗数据归集平台', '1-申报材料')


def load_yaml_list(fp, key=None):
    """读取 YAML（优先 PyYAML，回退轻量解析）；key 指定取 dict 下的哪个列表字段"""
    try:
        import yaml
        with open(fp) as f:
            doc = yaml.safe_load(f)
        if isinstance(doc, list):
            return doc
        if isinstance(doc, dict):
            if key:
                return doc.get(key, [])
            # 找第一个列表字段
            for v in doc.values():
                if isinstance(v, list):
                    return v
            return []
    except ImportError:
        pass
    items = []
    with open(fp) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('- {') or line.startswith('-{'):
                body = line.lstrip('- ').strip()
                if body.startswith('{') and body.endswith('}'):
                    kv = {}
                    for pair in body[1:-1].split(','):
                        if ':' not in pair:
                            continue
                        k, v = pair.split(':', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        kv[k] = v
                    items.append(kv)
    return items


def gap_status(gaps, gid):
    for g in gaps:
        if g.get('id') == gid:
            return g.get('status', 'open'), g.get('note', '')
    return 'unknown', ''


def main():
    # 1. 读取里程碑 SSOT
    if not os.path.exists(MILESTONE_FP):
        print(f'❌ 里程碑 SSOT 缺失: {MILESTONE_FP}')
        return 1
    milestones = load_yaml_list(MILESTONE_FP, key='milestones')

    # 2. 读取缺口 SSOT
    gaps = load_yaml_list(GAPS_FP, key='gaps') if os.path.exists(GAPS_FP) else []

    # 3. 申报材料目录文件清单
    files_exist = set()
    if os.path.isdir(REQ_DIR):
        files_exist = set(os.listdir(REQ_DIR))

    report = []
    json_rows = []
    critical_open = []

    for m in sorted(milestones, key=lambda x: x.get('date', '')):
        mid = m.get('id', '?')
        title = m.get('title', '?')
        sev = m.get('severity', '🟡')
        date_s = m.get('date', '')
        note = m.get('note', '')
        try:
            md, dd = int(date_s[:2]), int(date_s[3:])
            target = date(TODAY.year, md, dd)
            delta = (target - TODAY).days
        except Exception:
            delta = 0

        # 4. 前置检查：缺口
        gap_items = []
        for gid in m.get('gap_ids', []):
            st, gnote = gap_status(gaps, gid)
            if st != 'resolved':
                gap_items.append(f'缺口 {gid} 未闭环({st})')

        # 5. 前置检查：文件
        file_items = []
        for rf in m.get('req_files', []):
            if rf not in files_exist:
                file_items.append(f'文件缺失: {rf}')

        missing = gap_items + file_items

        if delta < 0:
            status = '✅ 已过'
            state = 'past'
        elif missing:
            status = f'⏳ 剩{delta}天 · 缺 {len(missing)} 项'
            state = 'warn' if sev == '🟡' else 'alert'
            if sev == '🔴':
                critical_open.append((mid, title, delta, missing))
        else:
            status = f'✅ 就绪 · 剩{delta}天'
            state = 'ok'

        json_rows.append({
            'id': mid, 'title': title, 'date': date_s, 'severity': sev,
            'delta': delta, 'state': state, 'missing': missing, 'note': note
        })
        line = f"{sev} **{date_s}** {title}（{status}）"
        if missing:
            line += '\n      ' + '\n      '.join(f'→ {x}' for x in missing)
        if note:
            line += f'\n      注: {note}'
        report.append(line)

    head = f"🔀 关键路径巡检 — {TODAY}"
    body = '\n'.join(report)

    if '--json' in sys.argv:
        print(json.dumps({'today': TODAY.isoformat(), 'milestones': json_rows}, ensure_ascii=False, indent=2))
        return 0

    if '--alert' in sys.argv:
        # 只输出待办缺项
        alerts = [r for r in json_rows if r['state'] in ('alert', 'warn')]
        if not alerts:
            print(f"{head}: ✅ 无缺项")
            return 0
        print(f"{head}: {len(alerts)} 项待办")
        for r in alerts:
            sev = r['severity']
            print(f"{sev} [{r['id']}] {r['title']} 剩{r['delta']}天 · 缺: {'; '.join(r['missing']) if r['missing'] else '人工核实'}")
        return 0

    print(head)
    print('-' * 60)
    print(body)
    print('-' * 60)
    if critical_open:
        print(f"🚨 {len(critical_open)} 个 🔴 关键节点有缺项，需优先处理:")
        for mid, title, delta, missing in critical_open:
            print(f"  · {mid} {title}（剩{delta}天）: {len(missing)} 项")
    else:
        print("✅ 全部 🔴 关键节点就绪或已过")
    return 0


if __name__ == '__main__':
    sys.exit(main())
