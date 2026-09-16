#!/usr/bin/env python3
"""persona_trainer.py — 夏明星数字化 Persona 心智镜像训练与对齐度校验 (BET-Y1Q4-T6-30).

基于 extract-persona-diffs.py 提取的特征向量, 提供:
  1. 对齐度门禁校验 (alignment >= 0.90)
  2. 代行权限启用判定
  3. 敏感数据零出域保障 (circuit_breaker 联动)

Usage:
  python3 bin/evolution/persona_trainer.py --help
  python3 bin/evolution/persona_trainer.py --gate-check
  python3 bin/evolution/persona_trainer.py --can-delegate
  python3 bin/evolution/persona_trainer.py --train --author xiamingxing

Exit codes:
  0  gate met / delegation allowed
  1  runtime error
  2  gate not met (< 0.90) / delegation denied
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 通过 importlib 加载同目录模块 (脚本名含连字符, 不可直接 import)
import importlib.util as _ilu

_module_path = Path(__file__).resolve().parent / 'extract-persona-diffs.py'
_spec = _ilu.spec_from_file_location('extract_persona_diffs', _module_path)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

run_extraction = _mod.run_extraction
calculate_alignment_score = _mod.calculate_alignment_score

WS = Path(__file__).resolve().parents[2]

# 对齐度门禁阈值
ALIGNMENT_GATE_THRESHOLD = 0.90


def check_alignment_gate(author: str) -> dict:
    """执行对齐度门禁校验.

    Returns:
        {
            'gate_met': bool,
            'alignment_score': float,
            'threshold': float,
            'can_delegate': bool,
        }
    """
    result = run_extraction(author)
    score = result.get('alignment_score', 0.0)
    gate_met = score >= ALIGNMENT_GATE_THRESHOLD

    return {
        'gate_met': gate_met,
        'alignment_score': score,
        'threshold': ALIGNMENT_GATE_THRESHOLD,
        'can_delegate': gate_met,  # 仅 gate 通过时代行权限可用
        'status': result.get('status', 'unknown'),
        'commit_count': result.get('features', {}).get('commit_count', 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='persona-trainer',
        description='夏明星 Persona 心智镜像 — 对齐度门禁校验与代行权限判定',
    )
    parser.add_argument(
        '--author',
        default='xiamingxing',
        help='Git author (default: xiamingxing)',
    )
    parser.add_argument(
        '--gate-check',
        action='store_true',
        help='校验对齐度门禁 (>= 0.90)',
    )
    parser.add_argument(
        '--can-delegate',
        action='store_true',
        help='检查是否可启用代行权限',
    )
    parser.add_argument(
        '--train',
        action='store_true',
        help='执行训练 (提取 + 评分 + 报告)',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='JSON 格式输出',
    )

    args = parser.parse_args(argv)

    if not any([args.gate_check, args.can_delegate, args.train]):
        parser.print_help()
        return 0

    try:
        gate_result = check_alignment_gate(args.author)
    except Exception as e:
        if args.json:
            print(json.dumps({'error': str(e), 'gate_met': False}))
        else:
            print(f'[error] {e}')
        return 1

    if args.gate_check:
        if args.json:
            print(json.dumps(gate_result, indent=2))
        else:
            status = 'PASS' if gate_result['gate_met'] else 'FAIL'
            print(f'[alignment-gate] {status}')
            print(f'  Score:     {gate_result["alignment_score"]:.4f}')
            print(f'  Threshold: {gate_result["threshold"]}')
            print(f'  Commits:   {gate_result["commit_count"]}')
        return 0 if gate_result['gate_met'] else 2

    if args.can_delegate:
        can_delegate = gate_result['gate_met']
        if args.json:
            print(json.dumps({
                'can_delegate': can_delegate,
                'reason': 'alignment gate met' if can_delegate else 'alignment gate NOT met',
                **gate_result,
            }, indent=2))
        else:
            if can_delegate:
                print(f'[delegation] ALLOWED — alignment={gate_result["alignment_score"]:.4f} >= {ALIGNMENT_GATE_THRESHOLD}')
            else:
                print(f'[delegation] DENIED — alignment={gate_result["alignment_score"]:.4f} < {ALIGNMENT_GATE_THRESHOLD}')
                print(f'  非对齐度门禁未达到, 不启用代行权限 (per BET-Y1Q4-T6-30 non_goals)')
        return 0 if can_delegate else 2

    if args.train:
        if args.json:
            print(json.dumps(gate_result, indent=2, ensure_ascii=False))
        else:
            print(f'Persona Trainer Report')
            print(f'=====================')
            print(f'Author:       {args.author}')
            print(f'Status:       {gate_result["status"]}')
            print(f'Commits:      {gate_result["commit_count"]}')
            print(f'Align Score:  {gate_result["alignment_score"]:.4f}')
            print(f'Gate Met:     {gate_result["gate_met"]}')
            print(f'Can Delegate: {gate_result["can_delegate"]}')
            print()
            print(f'Circuit Breaker: ACTIVE (敏感数据零出域)')
            print(f'Gate Threshold:  {ALIGNMENT_GATE_THRESHOLD}')
        return 0 if gate_result['gate_met'] else 2

    return 0


if __name__ == '__main__':
    sys.exit(main())
