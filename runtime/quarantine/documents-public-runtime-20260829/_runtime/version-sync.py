#!/usr/bin/env python3
"""version-sync.py — KEMS v7.1 SSOT 版本号同步
================================================
解决问题: M04 KEMS 版本号碎片化(7 个不同版本)
落地: @公共/_runtime/version-sync.py
用法:
    python3 version-sync.py --ssot VERSION.yaml --targets INDEX,README,CLAUDE,SKILL
"""
import os
import re
import sys
import argparse
from pathlib import Path

def extract_version(ssot_path):
    """从 VERSION.yaml 提取版本"""
    if not Path(ssot_path).exists():
        return None
    content = Path(ssot_path).read_text()
    m = re.search(r'^version:\s*["\']?([0-9.]+)["\']?', content, re.MULTILINE)
    return m.group(1) if m else None


def update_file(file_path, version, target='all'):
    """更新一个文件中的版本声明"""
    if not Path(file_path).exists():
        return False, f'文件不存在: {file_path}'

    content = Path(file_path).read_text()
    original = content

    # 模式 1: frontmatter
    if file_path.endswith('.md'):
        # YAML frontmatter
        content = re.sub(
            r'(version:\s*["\']?)v?[0-9]+\.[0-9]+(\.[0-9]+)?(["\']?)',
            f'\\1v{version}\\3',
            content,
            count=5
        )
        # 标题中 "vX.X"
        content = re.sub(
            r'(>\s*\*\*v)v[0-9]+\.[0-9]+(\.[0-9]+)?\*\*',
            f'\\1{version}**',
            content
        )
        # 文件名中的 vX.X (跳过)
    elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
        content = re.sub(
            r'^version:\s*["\']?v?[0-9]+\.[0-9]+(\.[0-9]+)?',
            f'version: v{version}',
            content,
            flags=re.MULTILINE,
            count=3
        )

    if content != original:
        Path(file_path).write_text(content)
        return True, '已更新'
    return False, '无需更新'


def main():
    parser = argparse.ArgumentParser(description='KEMS v7.1 版本号 SSOT 同步')
    parser.add_argument('--ssot', required=True, help='SSOT VERSION.yaml 路径')
    parser.add_argument('--targets', required=True, help='逗号分隔的目标文件/目录')
    parser.add_argument('--auto-replace', action='store_true', help='自动替换')
    parser.add_argument('--check', action='store_true', help='只检查不修改')
    args = parser.parse_args()

    base = Path('/Users/xiamingxing/Documents')

    # 解析 SSOT
    ssot_path = args.ssot if os.path.isabs(args.ssot) else base / args.ssot
    version = extract_version(ssot_path)
    if not version:
        print(f'❌ 无法从 {ssot_path} 提取版本号')
        sys.exit(1)

    print(f'📌 SSOT 版本: v{version}  来源: {ssot_path}')
    print()

    # 解析 targets
    targets = [t.strip() for t in args.targets.split(',')]

    for target in targets:
        if '*' in target:
            # glob 模式
            files = list(base.glob(target))
        elif os.path.isdir(target) or (base / target).is_dir():
            target_dir = Path(target) if os.path.isabs(target) else base / target
            files = list(target_dir.rglob('*.md'))
        else:
            target_path = Path(target) if os.path.isabs(target) else base / target
            files = [target_path]

        print(f'## {target} ({len(files)} 文件)')
        updated = 0
        for f in files:
            ok, msg = update_file(str(f), version)
            if ok:
                updated += 1
                print(f'  ✅ {f.relative_to(base)}: {msg}')
        print(f'  共 {updated}/{len(files)} 更新')
        print()


if __name__ == '__main__':
    main()
