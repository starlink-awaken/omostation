#!/usr/bin/env python3
"""fix-frontmatter: 安全地为 Markdown 文档补齐/更新 Frontmatter.

护栏 (2026-08-27 重写, 三连雷教训 #2268):
1. 只处理 .md 文件 — JSON/YAML/TOML 永远不碰 (manifest 被 frontmatter 打崩教训)
2. 已有 frontmatter 时精确解析+更新 last-reviewed, 不是正则替换 (吞 --- 教训)
3. 写前写后校验: frontmatter 完整性 + 原内容不变
4. --dry-run 模式: 只报告不写入
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

TODAY = date.today().isoformat()

# 剥 YAML frontmatter 后的正文必须与写前一致 (护栏 3)
FM_OPEN = "---"
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _split_frontmatter(content: str) -> tuple[str | None, str]:
    """安全分离 frontmatter 与正文。返回 (fm_text 或 None, body)。"""
    if not content.startswith("---\n"):
        return None, content
    # 找闭合 --- (独立行)
    m = FM_RE.match(content)
    if not m:
        return None, content  # 无闭合 --- → 整体当正文, 不动
    return m.group(1), content[m.end():]


def _update_last_reviewed(fm_text: str) -> str:
    """在 frontmatter 文本中更新/插入 last-reviewed 行 (保序)。"""
    lines = fm_text.split("\n")
    out, found = [], False
    for line in lines:
        if line.startswith("last-reviewed:"):
            out.append(f"last-reviewed: {TODAY}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"last-reviewed: {TODAY}")
    return "\n".join(out)


def fix_file(filepath: Path, dry_run: bool = False) -> bool:
    # 护栏 1: 只碰 .md
    if filepath.suffix != ".md":
        print(f"SKIP (非 .md): {filepath}")
        return False
    if not filepath.is_file():
        return False

    content = filepath.read_text(encoding="utf-8")
    fm_text, body = _split_frontmatter(content)

    if fm_text is None:
        # 无 frontmatter → 插入默认 (原有行为, 保留)
        new_fm = f"status: active\nlifecycle: entry\nowner: auto-fix-loop\nlast-reviewed: {TODAY}"
        new_content = f"{FM_OPEN}\n{new_fm}\n{FM_OPEN}\n{body}"
    else:
        # 已有 frontmatter → 只更新 last-reviewed (护栏 2)
        new_fm = _update_last_reviewed(fm_text)
        if new_fm == fm_text:
            return False  # last-reviewed 已是今天
        new_content = f"{FM_OPEN}\n{new_fm}\n{FM_OPEN}\n{body}"

    # 护栏 3: 写前校验 — 正文不变 (strip 头尾空白后比对)
    _, body_after = _split_frontmatter(new_content)
    if body_after.strip() != body.strip():
        print(f"ERROR (正文变化, 拒绝写入): {filepath}")
        return False
    # 护栏 3: 写前校验 — frontmatter 可闭合
    if not new_content.startswith("---\n") or "\n---\n" not in new_content[:2000]:
        print(f"ERROR (frontmatter 无法闭合, 拒绝写入): {filepath}")
        return False

    if dry_run:
        print(f"DRY-RUN would fix: {filepath}")
        return True
    filepath.write_text(new_content, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Files to fix (.md only)")
    parser.add_argument("--dry-run", action="store_true", help="只报告不写入")
    args = parser.parse_args()

    fixed = 0
    for f in args.files:
        if fix_file(Path(f), dry_run=args.dry_run):
            fixed += 1
            if not args.dry_run:
                print(f"Fixed: {f}")

    print(f"{'Would fix' if args.dry_run else 'Fixed'}: {fixed} file(s)")
    return 0 if fixed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
