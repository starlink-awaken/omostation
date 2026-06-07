#!/usr/bin/env python3
"""
eCOS v5 X1 — Vault 审计钩子 (Git 变更追踪)
=============================================
Phase X1 / BKL-010 / DEBT-X-001
追踪 Vault 中 Markdown 文件的 Git 变更，映射到审计记录。

用法:
    # 查看最近变更
    python3 check-vault-audit.py --vault <path> --since "7 days ago"

    # 输出 JSON（供 Agora 事件总线消费）
    python3 check-vault-audit.py --vault <path> --json

    # 部署为 Git post-commit hook:
    # ln -s check-vault-audit.py .git/hooks/post-commit

依赖:
    - Git repository
    - cards.db (可选，用于关联 CARDS 条目)

退出码:
    0 = 审计记录生成成功
    1 = 警告（非 git 仓库等）
"""

import sys
import json
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path


def get_git_log(vault_path: str, since: str, max_entries: int = 50) -> list[dict]:
    """获取 Git 变更日志"""
    try:
        result = subprocess.run(
            [
                "git", "-C", vault_path, "log",
                f"--since={since}",
                "--name-only",
                "--pretty=format:%H|%ai|%an|%s",
                f"--max-count={max_entries}",
                "--", "*.md", "*.yaml", "*.py", "*.sh",
            ],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if result.returncode != 0:
        return []

    entries = []
    current_commit = None

    for line in result.stdout.strip().split("\n"):
        if "|" in line and not line.startswith(" ") and not line.startswith("\t"):
            # Commit header: hash|date|author|message
            parts = line.split("|", 3)
            if len(parts) == 4:
                current_commit = {
                    "hash": parts[0][:8],
                    "date": parts[1].strip(),
                    "author": parts[2].strip(),
                    "message": parts[3].strip(),
                    "files": [],
                }
                entries.append(current_commit)
        elif current_commit and line.strip():
            # Changed file
            filepath = line.strip()
            if filepath.endswith((".md", ".yaml", ".py", ".sh")):
                current_commit["files"].append(filepath)

    return [e for e in entries if e["files"]]


def classify_changes(entries: list[dict]) -> dict:
    """分类变更到功能域"""
    domains = {
        "驾驶舱": [],
        "Vault": [],
        "工作域": [],
        "领域知识库": [],
        "工具箱": [],
        "家庭域": [],
        "unknown": [],
    }

    domain_patterns = {
        "驾驶舱": ["驾驶舱/"],
        "Vault": ["学习进化/"],
        "工作域": ["工作文档/"],
        "领域知识库": ["领域知识库/"],
        "工具箱": ["工具箱/"],
        "家庭域": ["家庭生活/"],
    }

    for entry in entries:
        for fpath in entry["files"]:
            classified = False
            for domain, patterns in domain_patterns.items():
                if any(p in fpath for p in patterns):
                    domains[domain].append({
                        "file": fpath,
                        "commit": entry["hash"],
                        "date": entry["date"],
                        "author": entry["author"],
                        "message": entry["message"],
                    })
                    classified = True
                    break
            if not classified:
                domains["unknown"].append({
                    "file": fpath,
                    "commit": entry["hash"],
                    "date": entry["date"],
                })

    return domains


def format_report(entries: list[dict], domains: dict, since: str) -> str:
    """人类可读审计报告"""
    total_files = sum(len(d["files"]) for d in entries)
    total_commits = len(entries)

    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — Vault 变更审计报告")
    lines.append("=" * 64)
    lines.append(f"  审计区间: {since} → {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"  提交数: {total_commits}  变更文件: {total_files}")
    lines.append("")

    if not entries:
        lines.append("  ✅ 无变更 — 审计区间内无文件修改")
        lines.append("")
        lines.append("=" * 64)
        return "\n".join(lines)

    # 按域汇总
    lines.append("  按域汇总:")
    lines.append("  " + "-" * 60)
    for domain in ["驾驶舱", "Vault", "工作域", "领域知识库", "工具箱", "家庭域"]:
        count = len(domains.get(domain, []))
        bar = "█" * min(count, 20) if count > 0 else "—"
        lines.append(f"  {domain:10s}  {count:3d} 变更  {bar}")

    if domains.get("unknown"):
        lines.append(f"  {'未知':10s}  {len(domains['unknown']):3d} 变更")

    lines.append("")

    # 最近提交
    lines.append("  最近提交:")
    lines.append("  " + "-" * 60)
    for entry in entries[:10]:
        files_str = ", ".join(entry["files"][:3])
        if len(entry["files"]) > 3:
            files_str += f" (+{len(entry['files']) - 3})"
        lines.append(f"  {entry['date'][:10]}  {entry['hash']}  {entry['author']}")
        lines.append(f"    {entry['message'][:60]}")
        lines.append(f"    → {files_str}")
        lines.append("")

    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 Vault 审计钩子")
    parser.add_argument("--vault", required=True, help="Vault Git 仓库路径")
    parser.add_argument("--since", default="7 days ago", help="审计区间")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--max-entries", type=int, default=50)
    parser.add_argument("--card-db", type=str, help="cards.db 路径（可选，用于写入 card_history）")
    args = parser.parse_args()

    vault_path = Path(args.vault)
    if not vault_path.exists():
        print(f"❌ Vault 路径不存在: {vault_path}", file=sys.stderr)
        sys.exit(2)

    # 检查是否为 git 仓库
    git_dir = vault_path / ".git"
    if not git_dir.exists():
        print(f"⚠️  {vault_path} 不是 Git 仓库——Vault 审计需要 Git 追踪文件变更。", file=sys.stderr)
        print(f"    建议: cd {vault_path} && git init && git add -A && git commit -m 'init'", file=sys.stderr)
        # 非致命——继续运行但生成空报告
    elif not (vault_path / ".git" / "logs").exists():
        print(f"⚠️  {vault_path} 是 Git 仓库但无提交历史。", file=sys.stderr)

    entries = get_git_log(str(vault_path), args.since, args.max_entries)
    domains = classify_changes(entries)

    result = {
        "generated_at": datetime.now().isoformat(),
        "since": args.since,
        "total_commits": len(entries),
        "total_files": sum(len(e["files"]) for e in entries),
        "domains": {d: len(f) for d, f in domains.items()},
        "entries": entries,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(entries, domains, args.since))

    # 可选: 写入 card_history（需 cards.db 路径）
    if hasattr(args, 'card_db') and args.card_db:
        write_card_history(entries, args.card_db)

    sys.exit(0)


def write_card_history(entries: list[dict], db_path: str):
    """将变更记录写入 card_history 表"""
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for entry in entries:
            for fpath in entry["files"]:
                cursor.execute(
                    "INSERT INTO card_history (timestamp, action, detail) VALUES (?, ?, ?)",
                    (entry["date"], "vault_change",
                     f"file={fpath} commit={entry['hash']} author={entry['author']} "
                     f"message={entry['message'][:100]}")
                )
        conn.commit()
        conn.close()
        print(f"  ✅ 已写入 card_history: {sum(len(e['files']) for e in entries)} 条记录", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠️ card_history 写入失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
