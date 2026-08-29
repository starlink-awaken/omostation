#!/usr/bin/env python3
"""principle-reality.py — KEMS v7.1 原则 vs 实际审计
=====================================================
解决问题: M05 CLAUDE.md §0a "不维护 STATE" vs 实际
落地: @公共/_runtime/principle-reality.py
"""
import os
import re
import sys
from pathlib import Path

# 原则模式
PRINCIPLE_PATTERNS = [
    # "不维护 X" 类
    (r'不维护\s*(自己的\s*)?([\u4e00-\u9fff]+\.md)', 'maintain'),
    (r'不创建\s*([\u4e00-\u9fff]+)', 'create'),
    (r'不用\s*([\u4e00-\u9fff/]+)', 'use'),
    (r'不实施\s*([\u4e00-\u9fff]+)', 'implement'),
    # "不写 X" 类
    (r'不写\s*([\u4e00-\u9fff/]+)', 'write'),
    (r'不读\s*([\u4e00-\u9fff/]+)', 'read'),
]

# 验证函数
def verify_principle(action, target, file_path):
    """验证原则 vs 实际"""
    base = Path('/Users/xiamingxing/Documents')

    if action == 'maintain':
        # 提取 .md 文件名
        m = re.search(r'([\u4e00-\u9fff]+\.md)', target)
        if not m:
            return None
        file_name = m.group(1)
        # 检查目录范围(文件路径的目录)
        domain_dir = base / file_path.parent
        target_file = domain_dir / file_name
        exists = target_file.exists()
        return {
            'action': action,
            'claim_target': target,
            'actual_file': str(target_file.relative_to(base)) if exists else None,
            'exists': exists,
            'violation': exists,  # 存在 = 违反
        }

    return None


def scan_principles(path):
    """扫描原则"""
    base = Path('/Users/xiamingxing/Documents')
    if not os.path.isabs(path):
        path = base / path
    path = Path(path)

    if not path.exists():
        print(f'❌ 目标路径不存在: {path}')
        return []

    results = []
    for md_file in path.rglob('*.md'):
        if any(p in str(md_file) for p in ['_archive', 'node_modules', '.git']):
            continue
        try:
            content = md_file.read_text(errors='ignore')
        except:
            continue

        for line_no, line in enumerate(content.split('\n'), 1):
            for pattern, action in PRINCIPLE_PATTERNS:
                for m in re.finditer(pattern, line):
                    target = m.group(1) if m.lastindex >= 1 else ''
                    verification = verify_principle(action, target, md_file.relative_to(base))
                    if verification and verification.get('violation'):
                        results.append({
                            'file': str(md_file.relative_to(base)),
                            'line': line_no,
                            'principle': m.group(0),
                            'action': action,
                            'target': target,
                            'actual': verification.get('actual_file'),
                            'violation': True,
                        })
    return results


def render_report(results):
    print('━' * 80)
    print(f'  KEMS v7.1 · 原则 vs 实际审计(M-δ 机制)')
    print('━' * 80)
    print(f'  扫描违反:{len(results)} 处')
    print('━' * 80)
    print()

    if not results:
        print('  🟢 无违反')
    else:
        print('## 🔴 原则违反(原则说"X"但实际"X")')
        print()
        for r in results:
            print(f'  📄 {r["file"]}:L{r["line"]}')
            print(f'     原则:{r["principle"]}')
            print(f'     实际:{r["actual"]} 存在')
            print()

    print('━' * 80)
    print(f'  修复: 改原则(加例外/适用范围) 或 删文件')
    print('━' * 80)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else '@工作文档'
    results = scan_principles(target)
    render_report(results)
    sys.exit(1 if results else 0)


if __name__ == '__main__':
    main()
