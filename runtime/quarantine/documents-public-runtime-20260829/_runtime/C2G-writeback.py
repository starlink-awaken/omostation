#!/usr/bin/env python3
"""C2G-writeback.py — KEMS v1.2 自动写回
=====================================
解决问题: 治理变更后无自动 git 记录
落地: @公共/_runtime/C2G-writeback.py
触发: git add + commit 治理变更(每日 1 次 / 健康度变化)
原理: 扫描 @公共 / @驾驶舱 / KEMS 域变更,自动 git add + commit

用法:
    python3 C2G-writeback.py           # 自动检测 + commit
    python3 C2G-writeback.py --dry-run # 只显示不 commit
    python3 C2G-writeback.py --force  # 强制 commit 即使无变更
"""
import os
import sys
import argparse
import subprocess
from pathlib import Path

ROOT = Path('/Users/xiamingxing/Documents')


def git_status():
    """git status --short"""
    r = subprocess.run(
        ['git', '-C', str(ROOT), 'status', '--short'],
        capture_output=True, text=True, timeout=10
    )
    return r.stdout.strip()


def git_diff_shortstat():
    """git diff --shortstat"""
    r = subprocess.run(
        ['git', '-C', str(ROOT), 'diff', '--shortstat', 'HEAD'],
        capture_output=True, text=True, timeout=10
    )
    return r.stdout.strip()


def git_add_all():
    """git add -A"""
    r = subprocess.run(
        ['git', '-C', str(ROOT), 'add', '-A'],
        capture_output=True, text=True, timeout=30
    )
    return r.returncode == 0


def git_commit(message):
    """git commit -m"""
    r = subprocess.run(
        ['git', '-C', str(ROOT), 'commit', '-m', message],
        capture_output=True, text=True, timeout=10
    )
    return r.returncode == 0, r.stdout + r.stderr


def has_changes():
    """是否有变更"""
    status = git_status()
    return bool(status)


def main():
    parser = argparse.ArgumentParser(description='C2G 自动写回 v1.2')
    parser.add_argument('--dry-run', action='store_true', help='只显示不 commit')
    parser.add_argument('--force', action='store_true', help='强制 commit 即使无变更')
    args = parser.parse_args()

    print('━' * 80)
    print('  C2G 自动写回 v1.2 · KEMS v7.3')
    print('━' * 80)

    # 1. 检测变更
    shortstat = git_diff_shortstat()
    print(f'  当前变更:{shortstat or "(无)"}')

    if not has_changes() and not args.force:
        print('\n  🟢 无变更,跳过 commit')
        return 0

    # 2. 准备 commit 信息
    status = git_status()
    files_count = len(status.split('\n')) if status else 0
    print(f'  待 commit 文件:{files_count} 个')

    # 自动 commit 信息(KEMS v7.3 风格)
    commit_msg = f"""chore: 自动写回 · KEMS v7.3 · {files_count} 文件

变更摘要:
{shortstat or '(无差异)'}

M-θ 跨域记忆层 · G16 跨域记忆门禁 · P23 记忆碎片化反模式
"""
    print(f'\n  Commit 信息:')
    for line in commit_msg.split('\n'):
        print(f'    {line}')

    if args.dry_run:
        print('\n  🟡 Dry-run 模式,未 commit')
        return 0

    # 3. git add + commit
    if not git_add_all():
        print('  ❌ git add 失败')
        return 1

    ok, log = git_commit(commit_msg)
    if ok:
        print(f'\n  🟢 Commit 成功')
        # 显示 commit hash
        r = subprocess.run(
            ['git', '-C', str(ROOT), 'log', '-1', '--format=%h %s'],
            capture_output=True, text=True, timeout=5
        )
        print(f'  {r.stdout.strip()}')
    else:
        print(f'  ❌ Commit 失败:{log[:200]}')
        return 1

    print('━' * 80)
    return 0


if __name__ == '__main__':
    sys.exit(main())
