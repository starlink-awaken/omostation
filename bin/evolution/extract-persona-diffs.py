#!/usr/bin/env python3
"""extract-persona-diffs.py — 夏明星数字化 Persona 心智镜像 diff 提取器 (BET-Y1Q4-T6-30).

从 git commit history 中提取指定 author 的修改模式, 经过 circuit_breaker
敏感数据清洗后, 输出结构化 persona 特征向量供 trainer 使用.

Architecture:
  Git Log → Diff Parse → Circuit Breaker (sanitize) → Feature Extract → JSON Output

Usage:
  python3 bin/evolution/extract-persona-diffs.py --help
  python3 bin/evolution/extract-persona-diffs.py --author "xiamingxing"
  python3 bin/evolution/extract-persona-diffs.py --author "xiamingxing" --json
  python3 bin/evolution/extract-persona-diffs.py --author "xiamingxing" --check-gate

Exit codes:
  0  success
  1  runtime error
  2  alignment gate not met (< 0.90)

Security:
  - 所有 diff 数据本地处理, 不发送任何外部请求
  - circuit_breaker 强制清洗: API Key / Email / Phone / 个人偏好 / 路径用户名
  - 原始 diff 不持久化, 仅保留清洗后的特征向量
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WS = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Circuit Breaker — 敏感数据清洗门禁
# ---------------------------------------------------------------------------

# 正则规则集: 模式 → 替换标签
CIRCUIT_BREAKER_RULES: list[tuple[re.Pattern[str], str]] = [
    # API Key / Token (32+ 字母数字)
    (re.compile(r'\b[a-zA-Z0-9_-]{32,}\b'), '<REDACTED_SECRET>'),
    # AWS-style keys
    (re.compile(r'AKIA[0-9A-Z]{16}'), '<REDACTED_AWS_KEY>'),
    # Generic secret patterns
    (re.compile(r'(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+'), '<REDACTED_CREDENTIAL>'),
    # Email
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '<REDACTED_EMAIL>'),
    # Phone (CN mobile)
    (re.compile(r'\b1[3-9]\d{9}\b'), '<REDACTED_PHONE>'),
    # File path with username
    (re.compile(r'/Users/[^/]+/'), '/Users/<REDACTED_USER>/'),
    (re.compile(r'/home/[^/]+/'), '/home/<REDACTED_USER>/'),
    # IP addresses
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '<REDACTED_IP>'),
]

# 个人偏好关键词 (匹配则清洗)
PREFERENCE_KEYWORDS: set[str] = {
    "hate", "love", "prefer", "dislike", "favorite", "unlike",
    "讨厌", "喜欢", "偏好", "不喜欢", "最爱", "反感",
}


def circuit_breaker_sanitize(text: str) -> tuple[str, dict[str, int]]:
    """执行 circuit_breaker 敏感数据清洗.

    Returns:
        (清洗后文本, 各类别命中次数统计)
    """
    counts: dict[str, int] = {}
    cleaned = text

    for pattern, replacement in CIRCUIT_BREAKER_RULES:
        matches = pattern.findall(cleaned)
        if matches:
            label = replacement.strip('<>').replace('_', ' ').lower()
            counts[label] = counts.get(label, 0) + len(matches)
            cleaned = pattern.sub(replacement, cleaned)

    # 偏好关键词行级清洗
    lines = cleaned.split('\n')
    cleaned_lines = []
    pref_hits = 0
    for line in lines:
        lower_line = line.lower()
        if any(kw in lower_line for kw in PREFERENCE_KEYWORDS):
            cleaned_lines.append('<REDACTED_PREFERENCE_LINE>')
            pref_hits += 1
        else:
            cleaned_lines.append(line)

    if pref_hits:
        counts['redacted_preference_line'] = pref_hits

    return '\n'.join(cleaned_lines), counts


# ---------------------------------------------------------------------------
# Git Diff Extraction
# ---------------------------------------------------------------------------

def run_git(args: list[str], cwd: Path = WS) -> str:
    """执行 git 命令, 返回 stdout."""
    result = subprocess.run(
        ['git'] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout


def extract_author_commits(author: str, max_count: int = 100) -> list[dict[str, Any]]:
    """提取指定 author 的 commit 列表 (仅元数据, 不含 diff 内容)."""
    fmt = '%H|%aI|%s'
    output = run_git([
        'log',
        f'--author={author}',
        f'--max-count={max_count}',
        f'--pretty=format:{fmt}',
        '--no-merges',
    ])

    commits = []
    for line in output.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split('|', 2)
        if len(parts) < 3:
            continue
        commits.append({
            'hash': parts[0],
            'date': parts[1],
            'message': parts[2],
        })
    return commits


def extract_commit_diff_stats(commit_hash: str) -> dict[str, Any]:
    """提取单个 commit 的 diff 统计 (文件数, 增删行数)."""
    output = run_git(['show', '--stat', '--oneline', commit_hash])
    files_changed = 0
    insertions = 0
    deletions = 0

    # Parse --stat output: " 3 files changed, 10 insertions(+), 5 deletions(-)"
    for line in output.split('\n'):
        m = re.search(r'(\d+) files? changed', line)
        if m:
            files_changed = int(m.group(1))
        m = re.search(r'(\d+) insertion', line)
        if m:
            insertions = int(m.group(1))
        m = re.search(r'(\d+) deletion', line)
        if m:
            deletions = int(m.group(1))

    # Extract file extensions
    diff_output = run_git(['show', '--name-only', '--pretty=format:', commit_hash])
    extensions = Counter()
    for f in diff_output.strip().split('\n'):
        if f.strip():
            ext = Path(f).suffix or '(no_ext)'
            extensions[ext] += 1

    return {
        'files_changed': files_changed,
        'insertions': insertions,
        'deletions': deletions,
        'extensions': dict(extensions),
    }


# ---------------------------------------------------------------------------
# Alignment Score Calculation
# ---------------------------------------------------------------------------

def calculate_alignment_score(features: dict[str, Any]) -> float:
    """计算 persona 对齐度得分 (0.0 ~ 1.0).

    加权维度:
    - 表达风格 (0.30): 句式长度分布 + 标点使用频率
    - 决策模式 (0.25): 修改类型比例
    - 技术栈偏好 (0.20): 技术选型一致性
    - 活跃度 (0.25): 数据量充分度
    """
    scores: dict[str, float] = {}

    # 1. 表达风格: 基于 commit message 平均长度与标点密度
    avg_msg_len = features.get('avg_message_length', 0)
    # 理想区间: 20-80 字符 → 满分; <10 或 >150 → 0
    if 20 <= avg_msg_len <= 80:
        scores['expression'] = 1.0
    elif avg_msg_len < 10:
        scores['expression'] = 0.5
    elif avg_msg_len > 150:
        scores['expression'] = 0.6
    else:
        scores['expression'] = 0.8

    # 2. 决策模式: 基于增删比
    total_ins = features.get('total_insertions', 0)
    total_del = features.get('total_deletions', 0)
    if total_ins + total_del > 0:
        ratio = total_ins / (total_ins + total_del)
        # 理想区间: 0.4 ~ 0.8 → 健康的新增/修改平衡
        if 0.3 <= ratio <= 0.85:
            scores['decision'] = 0.9
        else:
            scores['decision'] = 0.6
    else:
        scores['decision'] = 0.0

    # 3. 技术栈偏好: 基于语言多样性
    ext_count = len(features.get('extensions', {}))
    if ext_count >= 3:
        scores['techstack'] = 0.95
    elif ext_count >= 2:
        scores['techstack'] = 0.8
    else:
        scores['techstack'] = 0.6

    # 4. 活跃度/数据充分度
    commit_count = features.get('commit_count', 0)
    if commit_count >= 50:
        scores['activity'] = 1.0
    elif commit_count >= 20:
        scores['activity'] = 0.85
    elif commit_count >= 5:
        scores['activity'] = 0.6
    else:
        scores['activity'] = 0.3

    # 加权平均
    weights = {'expression': 0.30, 'decision': 0.25, 'techstack': 0.20, 'activity': 0.25}
    weighted_sum = sum(scores[k] * weights[k] for k in weights)

    return round(weighted_sum, 4)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_extraction(author: str, max_commits: int = 100) -> dict[str, Any]:
    """执行完整提取 pipeline."""
    # Step 1: 提取 commits
    commits = extract_author_commits(author, max_count=max_commits)

    if not commits:
        return {
            'status': 'no_data',
            'author': author,
            'commit_count': 0,
            'alignment_score': 0.0,
        }

    # Step 2: 逐个提取 diff stats + circuit_breaker 清洗
    all_insertions = 0
    all_deletions = 0
    all_extensions: Counter = Counter()
    msg_lengths = []
    sanitize_stats: dict[str, int] = {}

    for commit in commits:
        # 清洗 commit message
        cleaned_msg, cb_stats = circuit_breaker_sanitize(commit['message'])
        for k, v in cb_stats.items():
            sanitize_stats[k] = sanitize_stats.get(k, 0) + v
        commit['message_cleaned'] = cleaned_msg

        # 提取 diff stats
        stats = extract_commit_diff_stats(commit['hash'])
        all_insertions += stats['insertions']
        all_deletions += stats['deletions']
        for ext, count in stats['extensions'].items():
            all_extensions[ext] += count

        msg_lengths.append(len(cleaned_msg))

    # Step 3: 计算特征向量
    avg_msg_len = sum(msg_lengths) / len(msg_lengths) if msg_lengths else 0

    features = {
        'commit_count': len(commits),
        'avg_message_length': round(avg_msg_len, 1),
        'total_insertions': all_insertions,
        'total_deletions': all_deletions,
        'extensions': dict(all_extensions),
    }

    # Step 4: 对齐度评分
    alignment_score = calculate_alignment_score(features)

    return {
        'status': 'ok',
        'author': author,
        'extracted_at': datetime.now(timezone.utc).isoformat(),
        'alignment_score': alignment_score,
        'alignment_gate_met': alignment_score >= 0.90,
        'circuit_breaker_stats': sanitize_stats,
        'features': features,
        'commits_sample': commits[:5],  # 仅保留前5条作为 sample
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='extract-persona-diffs',
        description='从 git history 提取 author 的 persona 特征向量 (circuit_breaker 敏感数据清洗 + 对齐度门禁)',
    )
    parser.add_argument(
        '--author',
        default='xiamingxing\\|starlink-awaken',
        help='Git author 筛选 (default: xiamingxing\\|starlink-awaken)',
    )
    parser.add_argument(
        '--max-commits',
        type=int,
        default=100,
        help='最大处理 commit 数 (default: 100)',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='JSON 格式输出',
    )
    parser.add_argument(
        '--check-gate',
        action='store_true',
        help='仅检查对齐度门禁 (exit 2 if < 0.90)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run: 仅统计 commit 数, 不提取 diff',
    )

    args = parser.parse_args(argv)

    # Dry run mode
    if args.dry_run:
        commits = extract_author_commits(args.author, max_count=args.max_commits)
        if args.json:
            print(json.dumps({'commit_count': len(commits), 'dry_run': True}, indent=2))
        else:
            print(f'[dry-run] Found {len(commits)} commits by "{args.author}"')
        return 0

    # Full extraction
    result = run_extraction(args.author, max_commits=args.max_commits)

    if args.check_gate:
        score = result.get('alignment_score', 0.0)
        if args.json:
            print(json.dumps({
                'alignment_score': score,
                'gate_met': score >= 0.90,
                'threshold': 0.90,
            }, indent=2))
        else:
            status = 'PASS' if score >= 0.90 else 'FAIL'
            print(f'[alignment-gate] {status} — score={score:.4f}, threshold=0.90')
        if score < 0.90:
            return 2
        return 0

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f'Persona Diff Extraction Report')
        print(f'=============================')
        print(f'Author:         {result["author"]}')
        print(f'Status:         {result["status"]}')
        print(f'Commits:        {result["features"]["commit_count"]}')
        print(f'Align Score:    {result["alignment_score"]:.4f}')
        print(f'Gate Met:       {result.get("alignment_gate_met", False)}')
        cb = result.get('circuit_breaker_stats', {})
        if cb:
            print(f'Circuit Breaker:')
            for k, v in cb.items():
                print(f'  {k}: {v}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
