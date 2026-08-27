#!/usr/bin/env python3
"""fix-frontmatter: 安全地为 Markdown 文档补齐/更新 Frontmatter.

护栏 (2026-08-27 重写, 三连雷教训 #2268):
1. 只处理 .md 文件 — JSON/YAML/TOML 永远不碰 (manifest 被 frontmatter 打崩教训)
2. 已有 frontmatter 时精确解析+更新 last-reviewed, 不是正则替换 (吞 --- 教训)
3. 写前写后校验: frontmatter 完整性 + 原内容不变
4. --dry-run 模式: 只报告不写入

Modes:
  - 默认 (positional files): 补默认 frontmatter + 更新 last-reviewed
  - --batch <root>: 全仓扫描 .omo/_knowledge, 修正 status/lifecycle
    不在 allowed set 的文件 + 清除残留 git 冲突标记 + 修复缺 closing --- 的
    前置 frontmatter (P77 doc-ssot debt 收敛)
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

# Batch mode: status / lifecycle allowed-set mapping (来自 doc-governance-check.py)
STATUS_MAP = {
    "accepted": "archived",
    "blocked": "stale",
    "candidate": "planned",
    "ready_for_human": "active",
    "in_progress": "active",
    "completed": "archived",
    "in-review": "planned",
}
ALLOWED_STATUS = {
    "active",
    "archived",
    "deprecated",
    "draft",
    "experimental",
    "planned",
    "retired",
    "stale",
    "superseded",
}
ALLOWED_LIFECYCLE = {
    "contract",
    "entry",
    "experimental",
    "generated",
    "history",
    "pattern",
    "plan",
    "proposal",
    "report",
    "retired",
    "spec",
    "ssot",
    "stable",
}


def _nearest_allowed_status(value: str) -> str:
    """Pick the closest allowed status for an unknown one."""
    v = value.lower()
    if "active" in v or "open" in v or "live" in v or "candidate-delivery" in v:
        return "active"
    if "archive" in v or "done" in v or "accept" in v or "complet" in v:
        return "archived"
    if "block" in v or "stale" in v or "fail" in v:
        return "stale"
    if "plan" in v or "ready" in v or "pending" in v or "candidate" in v:
        return "planned"
    if "draft" in v or "wip" in v:
        return "draft"
    if "experiment" in v or "pilot" in v:
        return "experimental"
    if "deprecat" in v or "obsolete" in v:
        return "deprecated"
    if "supersed" in v:
        return "superseded"
    if "retire" in v:
        return "retired"
    return "archived"
LIFECYCLE_BY_PATH = {
    "plans": "plan",
    "retros": "history",
    "audits": "history",
    "summaries": "history",
    "decisions": "spec",
    "patterns": "pattern",
    "specs": "spec",
    "contracts": "contract",
    "ssot": "ssot",
}


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


# ----- batch mode (P77 doc-ssot debt) -----


def _strip_baselines(lines: list[str]) -> list[str]:
    """清除残留 <<<<<<< / ||||||| 冲突标记 (recursive rebase 残留)。"""
    out, skip = [], False
    for line in lines:
        if line.startswith("||||||| "):
            skip = True
            continue
        if skip:
            if line.startswith("<<<<<<< "):
                skip, out = False, [*out, line]
            continue
        out.append(line)
    return out


def _ensure_closing_frontmatter_text(text: str) -> str:
    """文件以 --- 开头但缺闭合 --- 时补一个。"""
    if text.startswith("---") and text.count("---") == 1:
        return text + "\n---\n"
    return text


def _resolve_conflicts(path: Path) -> bool:
    """剥除 git 冲突标记 (取 HEAD 侧), 修复缺 closing --- (.md) / 删冲突行 (.jsonl)."""
    is_jsonl = path.suffix == ".jsonl"
    text = path.read_text(encoding="utf-8")
    if "<<<<<<< " not in text and "||||||| " not in text:
        if is_jsonl:
            return False
        new_text = _ensure_closing_frontmatter_text(text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            return True
        return False
    if is_jsonl:
        # JSONL: drop lines from <<<<<<< until next >>>>>>>, preserve structure
        out_lines, skip = [], False
        for line in text.split("\n"):
            if line.startswith("<<<<<<< "):
                skip = True
                continue
            if skip:
                if line.startswith(">>>>>>> "):
                    skip = False
                continue
            out_lines.append(line)
        path.write_text("\n".join(out_lines), encoding="utf-8")
        return True
    # 1. 清 orphan |||||||
    lines = text.split("\n")
    text = "\n".join(_strip_baselines(lines))
    if "<<<<<<< " not in text:
        text = _ensure_closing_frontmatter_text(text)
        path.write_text(text, encoding="utf-8")
        return True
    # 2. 迭代剥嵌套 <<<<<<< ======= >>>>>>> (取 HEAD 侧)
    for _ in range(10):
        lines = text.split("\n")
        out, i, resolved_any = [], 0, False
        while i < len(lines):
            line = lines[i]
            if line.startswith("<<<<<<< "):
                sep_idx, theirs_idx = None, None
                for j in range(i + 1, len(lines)):
                    if lines[j] == "=======":
                        sep_idx = j
                        break
                if sep_idx is None:
                    out.append(line)
                    i += 1
                    continue
                for j in range(sep_idx + 1, len(lines)):
                    if lines[j].startswith(">>>>>>> "):
                        theirs_idx = j
                        break
                if theirs_idx is None:
                    out.append(line)
                    i += 1
                    continue
                ours_block = _strip_baselines(lines[i + 1 : sep_idx])
                out.extend(ours_block)
                resolved_any = True
                i = theirs_idx + 1
            else:
                out.append(line)
                i += 1
        text = "\n".join(out)
        if not resolved_any or "<<<<<<< " not in text:
            break
    text = _ensure_closing_frontmatter_text(text)
    path.write_text(text, encoding="utf-8")
    return True


def _fix_frontmatter_fields(path: Path) -> bool:
    """映射 status 到 allowed set, 按父目录名设 lifecycle, 补 owner (unassigned).

    也补缺失的 status / lifecycle / owner 字段.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        # 无 frontmatter — 插入默认
        default_lifecycle = LIFECYCLE_BY_PATH.get(path.parent.name, "history")
        new_fm = (
            f"status: archived\n"
            f"lifecycle: {default_lifecycle}\n"
            f"owner: unassigned\n"
            f"last-reviewed: 2026-08-27"
        )
        new_content = f"{FM_OPEN}\n{new_fm}\n{FM_OPEN}\n{text}"
        path.write_text(new_content, encoding="utf-8")
        return True
    m = FM_RE.match(text)
    if not m:
        new_text = _ensure_closing_frontmatter_text(text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            return True
        return False
    frontmatter, body = m.group(1), text[m.end():]
    lines, new_lines = frontmatter.split("\n"), []
    has_status = has_lifecycle = has_owner = False
    modified = False
    for line in lines:
        # docs/ 下的文件 surface 异构, 不主动 remap 已知在 allowed set 的 status
        # (docs/superpowers/specs 用不同 enum, 改了反而触发新错). 但未在
        # allowed set 的 (如 proposed) 仍要 nearest 映射到合法值.
        in_docs = "docs" in path.parts
        if re.match(r"^status:\s*", line):
            has_status = True
            m2 = re.match(r"^status:\s*(\S+)", line)
            if m2:
                cur = m2.group(1)
                if cur in STATUS_MAP and not in_docs:
                    new_v = STATUS_MAP[cur]
                    if new_v != cur:
                        line = f"status: {new_v}"
                        modified = True
                elif cur not in ALLOWED_STATUS:
                    new_v = _nearest_allowed_status(cur)
                    if new_v != cur:
                        line = f"status: {new_v}"
                        modified = True
        elif re.match(r"^lifecycle:\s*", line):
            has_lifecycle = True
            m3 = re.match(r"^lifecycle:\s*(\S+)", line)
            if m3:
                target = LIFECYCLE_BY_PATH.get(path.parent.name, "history")
                if m3.group(1) != target:
                    line = f"lifecycle: {target}"
                    modified = True
        elif re.match(r"^owner:\s*", line):
            has_owner = True
        new_lines.append(line)
    if not has_lifecycle:
        new_lines.append(f"lifecycle: {LIFECYCLE_BY_PATH.get(path.parent.name, 'history')}")
        modified = True
    if not has_owner:
        new_lines.append("owner: unassigned")
        modified = True
    if not any(l.startswith("last-reviewed:") for l in new_lines):
        new_lines.append("last-reviewed: 2026-08-27")
        modified = True
    if not has_status:
        new_lines.append("status: archived")
        modified = True
    if not modified:
        return False
    new_text = "---\n" + "\n".join(new_lines) + "\n---\n" + body
    path.write_text(new_text, encoding="utf-8")
    return True


def _batch_fix(root: Path) -> tuple[int, int]:
    """对 .omo/_knowledge 全仓: 修冲突标记 + 修 frontmatter 字段.

    Returns (conflict_fixes, field_fixes).
    """
    md_targets = [
        root / ".omo" / "_knowledge" / "plans",
        root / ".omo" / "_knowledge" / "retros",
        root / ".omo" / "_knowledge" / "audits",
        root / ".omo" / "_knowledge" / "summaries",
        root / ".omo" / "_knowledge" / "decisions",
        root / "docs",  # 全 docs/ 都扫
    ]
    jsonl_targets = [
        root / ".omo" / "_knowledge",
    ]
    conflict_fixed = field_fixed = 0
    for target in md_targets:
        if not target.exists():
            continue
        for p in target.rglob("*.md"):
            if _resolve_conflicts(p):
                conflict_fixed += 1
            if _fix_frontmatter_fields(p):
                field_fixed += 1
    # JSONL: 仅修冲突标记, 不动字段 (no frontmatter 概念)
    for target in jsonl_targets:
        if not target.exists():
            continue
        for p in target.rglob("*.jsonl"):
            if _resolve_conflicts(p):
                conflict_fixed += 1
    return conflict_fixed, field_fixed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="Files to fix (.md only)")
    parser.add_argument("--dry-run", action="store_true", help="只报告不写入")
    parser.add_argument(
        "--batch",
        metavar="ROOT",
        help="Batch mode: 扫 ROOT/.omo/_knowledge, 修冲突标记 + frontmatter 字段",
    )
    args = parser.parse_args()

    if args.batch:
        root = Path(args.batch)
        c_fixed, f_fixed = _batch_fix(root)
        print(f"Batch fix: {c_fixed} conflict-marked, {f_fixed} field-updated files")
        return 0 if (c_fixed + f_fixed) > 0 else 1

    if not args.files:
        print("No files specified", file=sys.stderr)
        return 1
    fixed = 0
    for f in args.files:
        if fix_file(Path(f), dry_run=args.dry_run):
            fixed += 1
            if not args.dry_run:
                print(f"Fixed: {f}")


if __name__ == "__main__":
    sys.exit(main())
