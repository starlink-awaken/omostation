#!/usr/bin/env python3
"""prefix-clean.py — KEMS v7.1 双前缀检测与修复
=================================================
解决问题: M03 KEMS 21 文件双前缀(本会话复发 · W02 历史警告)
落地: @公共/_runtime/prefix-clean.py
用法:
    python3 prefix-clean.py --check <target>     # 只检查
    python3 prefix-clean.py --fix <target>       # 修复
    python3 prefix-clean.py --auto <target>      # 自动(检查+修复)
"""
import os
import sys
import re
import argparse
from pathlib import Path
from collections import defaultdict

# 已知双前缀模式
DOUBLE_PREFIX_PATTERNS = [
    # 形式1:@xxx/_knowledge/10-systems/KEMS/@xxx/_knowledge/10-systems/KEMS/
    (r'@([^/]+)/_knowledge/10-systems/([^/]+)/@\1/_knowledge/10-systems/\2/', r'@\1/_knowledge/10-systems/\2/'),
    # 形式2:任何路径下出现两次 @xxx/ 串联
    (r'(@[^/]+(?:/[^/]+){2,})/\1/', r'\1/'),
    # 形式3:~/Documents/.../~/Documents/...
    (r'(~/Documents/[^ ]+?)/(\1)', r'\1'),
]

# 关键词 SSOT(用于"目标"识别)
SSOT_KEYWORDS = ['KEMS', 'OMO', 'eCOS']


def detect_double_prefix(content, file_path):
    """检测文件中的双前缀"""
    issues = []
    for pattern, _ in DOUBLE_PREFIX_PATTERNS:
        for m in re.finditer(pattern, content):
            issues.append({
                'file': file_path,
                'match': m.group(0)[:100],
                'pattern': pattern[:50],
            })
    return issues


def fix_double_prefix(content):
    """修复双前缀"""
    fixed = content
    for pattern, replacement in DOUBLE_PREFIX_PATTERNS:
        fixed = re.sub(pattern, replacement, fixed)
    return fixed


def scan_target(target_path, fix=False):
    """扫描目标路径"""
    base = Path('/Users/xiamingxing/Documents')
    if not os.path.isabs(target_path):
        target = base / target_path
    else:
        target = Path(target_path)

    if not target.exists():
        print(f'❌ 目标不存在: {target}')
        return 0, 0

    skip_dirs = {'.git', '__pycache__', '_archive', '_storage', '存档', '_generated', 'node_modules'}

    file_count = 0
    issue_count = 0
    fix_count = 0
    issue_files = []

    for md_file in target.rglob('*.md'):
        if any(s in md_file.parts for s in skip_dirs):
            continue
        try:
            content = md_file.read_text(errors='ignore')
        except Exception:
            continue

        file_count += 1
        issues = detect_double_prefix(content, str(md_file.relative_to(base)))

        if issues:
            issue_count += len(issues)
            issue_files.append(md_file)

            if fix:
                fixed_content = fix_double_prefix(content)
                if fixed_content != content:
                    md_file.write_text(fixed_content)
                    fix_count += len(issues)

    return file_count, issue_count, fix_count, issue_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target', nargs='?', default='.', help='目标路径')
    parser.add_argument('--check', action='store_true', help='只检查')
    parser.add_argument('--fix', action='store_true', help='修复')
    parser.add_argument('--auto', action='store_true', help='自动模式')
    args = parser.parse_args()

    if not any([args.check, args.fix, args.auto]):
        args.check = True  # 默认 check

    print('━' * 70)
    print(f'  KEMS v7.1 · prefix-clean(M-β 脚本 · M03/W02 修复)')
    print('━' * 70)
    print(f'  目标: {args.target}')
    mode = 'auto' if args.auto else ('fix' if args.fix else 'check')
    print(f'  模式: {mode}')
    print('━' * 70)

    fix = args.fix or args.auto
    file_count, issue_count, fix_count, issue_files = scan_target(args.target, fix=fix)

    print(f'\n## 扫描结果')
    print(f'  文件扫描:{file_count} 个 .md')
    print(f'  双前缀发现:{issue_count} 处')

    if issue_files:
        print(f'\n## 🔴 涉及文件({len(issue_files)} 个)')
        for f in issue_files[:20]:
            rel = str(f).replace('/Users/xiamingxing/Documents/', '')
            print(f'    📄 {rel}')

    if fix:
        print(f'\n## 🛠  修复')
        print(f'  已修复:{fix_count} 处')

    print('\n━' * 70)
    if issue_count == 0:
        print(f'  状态:🟢 无双前缀')
    elif fix and fix_count == issue_count:
        print(f'  状态:🟢 已全部修复')
    else:
        print(f'  状态:🔴 发现 {issue_count} 处双前缀(运行 --fix 修复)')
    print('━' * 70)

    sys.exit(0 if issue_count == 0 or (fix and fix_count == issue_count) else 1)


if __name__ == '__main__':
    main()
