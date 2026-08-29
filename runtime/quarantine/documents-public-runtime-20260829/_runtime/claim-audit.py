#!/usr/bin/env python3
"""claim-audit.py — KEMS v7.1 宣称审计
=====================================
解决问题: 宣称脱节(KEMS 7/7 跨域 vs 4/8 实际 · M06)
落地: @公共/_runtime/claim-audit.py
触发: 每次深度门禁 / 每月对账
原理: 扫描文档中的"已实现/全部/完成/N/M"等关键词,与实际验证

用法:
    python3 claim-audit.py [path]
    python3 claim-audit.py @学习进化/_knowledge/10-systems/KEMS
    python3 claim-audit.py @公共
"""
import os
import re
import sys
import argparse
from pathlib import Path

# 宣称词模式
CLAIM_PATTERNS = [
    # 百分比宣称
    (r'(\d+)/(\d+)\s*跨?域(?:部署|覆盖)', 'N/M 跨域部署', 'actual_count'),
    (r'(\d+)%\s*覆盖', 'X% 覆盖率', 'percent'),
    (r'覆盖率[达到到]?\s*(\d+)%', '覆盖率 X%', 'percent'),
    # 完成性宣称
    (r'全部[已]?完成', '全部完成', 'completion'),
    (r'全部[已]?实现', '全部实现', 'completion'),
    (r'(\d+)/(\d+)\s*[实现部署]', 'N/M 实现', 'actual_count'),
    # 健康度宣称
    (r'(\d+)\s*个?域[已]?(?:完整|达标)', 'X 域完整', 'count'),
    (r'(\d+)\s*域[已]?(?:完成|兑现)', 'X 域兑现', 'count'),
    # 数量宣称
    (r'已[创建立]?(\d+)\s*个?[\u4e00-\u9fff]+', '已建 X 个', 'count'),
    (r'(\d+)\s*个?域[已]?(?:注册|接入)', 'X 域注册', 'count'),
    # 完整性
    (r'(?:完全|彻底)\s*(?:治理|解决|清完|清理)', '完全治理', 'completion'),
    (r'零[问题债务红黄]', '零问题', 'verify_zero'),
    (r'100%', '100%', 'percent'),
    # 跨工作区
    (r'(?:N|M)[/-](?:N|M)\s*桥接', 'N/M 桥接', 'actual_count'),
]

# 实际验证模式
def verify_claim(claim_type, claim_text, target):
    """根据 claim_type 验证实际"""
    base = Path('/Users/xiamingxing/Documents')

    if claim_type == 'actual_count':
        # 提取 N/M
        m = re.search(r'(\d+)/(\d+)', claim_text)
        if not m:
            return None, None
        claimed_n, total_m = int(m.group(1)), int(m.group(2))

        if '跨域' in claim_text or '跨域' in claim_text:
            # 实际跨域数
            actual = 0
            for d in ['驾驶舱', '学习进化', '个人', '公共', '家庭生活', '工作文档', '创意创作', 'OPC']:
                if (base / f'@{d}' / '_control' / 'l4-kernel.md').exists():
                    actual += 1
            return claimed_n, actual

    elif claim_type == 'completion':
        # 验证"全部完成"
        return 'verify', '需人工确认(无具体数字)'

    elif claim_type == 'count':
        # 数量
        m = re.search(r'(\d+)', claim_text)
        if m:
            return int(m.group(1)), '需人工确认'

    elif claim_type == 'verify_zero':
        # 验证"零问题"
        return 'verify', '跑 check-convergence.py 验证'

    elif claim_type == 'percent':
        m = re.search(r'(\d+)%', claim_text)
        if m:
            return int(m.group(1)), '需人工确认'

    return None, None


def scan_claims(target, exclude_target_files=False):
    """扫描目标路径的所有 md 文件,提取宣称

    exclude_target_files: 豁免目标定义类文件(_gates/README/_metrics/_principles/_outputs/health-report)
    解决误报:KEMS 文档中的"100% 目标"是定义而非实际数据
    """
    base = Path('/Users/xiamingxing/Documents')
    if not os.path.isabs(target):
        target = base / target
    target = Path(target)

    if not target.exists():
        print(f'❌ 目标路径不存在: {target}')
        return []

    # 目标定义文件模式(豁免)— 这些文件是"目标"而非"实际"
    TARGET_FILE_PATTERNS = [
        '/_gates/',         # 门禁定义
        '/_principles/',    # 原则定义
        '/_patterns/',      # 模式定义
        '/cases/',          # 案例(所有 _runtime/cases 等)
        '/_scenarios/',     # 场景(描述)
        '/README.md',       # 顶层 README(描述)
        '/health-report.md',  # 健康报告(状态)
        '/signals.md',      # 信号(状态)
    ]

    results = []
    for md_file in target.rglob('*.md'):
        if any(p in str(md_file) for p in ['_archive', 'node_modules', '.git']):
            continue

        # 目标定义文件豁免
        if exclude_target_files and any(pat in str(md_file) for pat in TARGET_FILE_PATTERNS):
            continue

        try:
            content = md_file.read_text(errors='ignore')
        except:
            continue

        for line_no, line in enumerate(content.split('\n'), 1):
            for pattern, claim_label, claim_type in CLAIM_PATTERNS:
                for m in re.finditer(pattern, line):
                    claim_text = m.group(0)
                    claimed, actual = verify_claim(claim_type, claim_text, target)
                    if claimed is not None or claim_type in ['completion', 'verify_zero']:
                        results.append({
                            'file': str(md_file.relative_to(base)),
                            'line': line_no,
                            'claim': claim_text,
                            'label': claim_label,
                            'claimed': claimed,
                            'actual': actual,
                            'verified': (claimed == actual) if isinstance(claimed, int) and isinstance(actual, int) else 'pending',
                        })
    return results


def render_report(results, target):
    """渲染报告"""
    print('━' * 80)
    print(f'  KEMS v7.1 · 宣称审计(M-γ 机制)')
    print('━' * 80)
    print(f'  目标: {target}')
    print(f'  扫描: {len(results)} 处宣称')
    print('━' * 80)

    # 按验证状态分组
    verified = [r for r in results if r['verified'] == True]
    failed = [r for r in results if r['verified'] == False]
    pending = [r for r in results if r['verified'] == 'pending']

    print(f'\n## 验证结果')
    print(f'  🟢 验证一致:{len(verified)} 处')
    print(f'  🔴 验证失败:{len(failed)} 处')
    print(f'  🟡 待人工确认:{len(pending)} 处')

    if failed:
        print(f'\n## 🔴 验证失败的宣称(M-γ 触发)')
        print()
        for r in failed:
            print(f'  📄 {r["file"]}:L{r["line"]}')
            print(f'     宣称:{r["claim"]}({r["label"]})')
            print(f'     声称:{r["claimed"]}  实际:{r["actual"]}  差距:{r["claimed"] - r["actual"] if isinstance(r["claimed"], int) and isinstance(r["actual"], int) else "—"}')
            print()

    if pending:
        print(f'\n## 🟡 待人工确认的宣称')
        print()
        for r in pending[:20]:
            print(f'  📄 {r["file"]}:L{r["line"]}  {r["claim"]} ({r["label"]})')
        if len(pending) > 20:
            print(f'  ... 还有 {len(pending)-20} 处')
        print()

    if verified:
        print(f'\n## 🟢 验证一致的宣称')
        print()
        for r in verified[:10]:
            print(f'  ✅ {r["file"]}:L{r["line"]}  {r["claim"]}')
        if len(verified) > 10:
            print(f'  ... 还有 {len(verified)-10} 处')
        print()

    print('━' * 80)
    print(f'  KEMS v7.1 原则: 宣称必须 100% 可验证')
    print(f'  修复: 修文档 / 补实现 / 标 [待实现]')
    print('━' * 80)

    return {
        'total': len(results),
        'verified': len(verified),
        'failed': len(failed),
        'pending': len(pending),
    }


def chain_with_prefix_clean(target):
    """联动 prefix-clean(防止 M-γ 修文档时引入双前缀)

    流程:
    1. 跑 claim-audit 找失败
    2. prefix-clean --fix 修双前缀
    3. 重新跑 claim-audit 验证
    """
    import subprocess
    print()
    print('━' * 80)
    print('  🔗 联动修复:claim-audit + prefix-clean(本会话新增)')
    print('━' * 80)

    # 1. prefix-clean --fix
    print('\n## §1 prefix-clean --fix')
    print(f'  目标:{target}')
    r = subprocess.run(
        ['python3', '/Users/xiamingxing/Documents/@公共/_runtime/prefix-clean.py',
         '--fix', f'/Users/xiamingxing/Documents/{target}'],
        capture_output=True, text=True, timeout=30
    )
    # 提取关键信息
    if '已全部修复' in r.stdout or '无双前缀' in r.stdout:
        print('  ✅ 无需修复 / 已全部修复')
    else:
        print('  🛠 prefix-clean 已跑(详见 prefix-clean 输出)')

    # 2. 重新 claim-audit(传 exclude_target_files)
    print('\n## §2 重新 claim-audit 验证')
    import sys as _sys
    exclude = '--exclude-target-files' in _sys.argv
    results2 = scan_claims(target, exclude_target_files=exclude)
    summary2 = render_report(results2, target)

    if summary2['failed'] == 0:
        print('\n  🟢 联动验证:0 失败')
    else:
        print(f'\n  🔴 联动验证:仍有 {summary2["failed"]} 失败')

    return summary2


def main():
    parser = argparse.ArgumentParser(description='KEMS v7.1 宣称审计(M-γ 机制)')
    parser.add_argument('target', nargs='?', default='@学习进化/_knowledge/10-systems/KEMS', help='扫描目标')
    parser.add_argument('--with-prefix-clean', action='store_true', help='联动 prefix-clean(防止修文档时引入双前缀)')
    parser.add_argument('--exclude-target-files', action='store_true',
                        help='豁免目标定义文件(_gates/_principles/README 等)')
    args = parser.parse_args()

    results = scan_claims(args.target, exclude_target_files=args.exclude_target_files)
    summary = render_report(results, args.target)

    # 联动 prefix-clean
    if args.with_prefix_clean or summary['failed'] == 0:
        # 失败时自动联动 + 成功时也联动(预防)
        summary = chain_with_prefix_clean(args.target)

    # 退出码
    sys.exit(1 if summary['failed'] > 0 else 0)


if __name__ == '__main__':
    main()
