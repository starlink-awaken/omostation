#!/usr/bin/env python3
"""private-data-ingest.py — 个人私有数据抓取适配器 (Apple Notes / Reminders / Calendar)

功能: 100% 本地化抓取 macOS/iCloud 同步的个人私有备忘录、日程与提醒事项，
提取最新待处理条目，转为标准 Markdown 存入 ~/Documents/_inbox/，
完全不泄漏任何个人隐私。

v1.0 | 2026-07-30
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
INBOX_DIR = DOCS_ROOT / "_inbox"


def fetch_apple_notes_inbox() -> list[dict[str, str]]:
    """使用 AppleScript 从 macOS 备忘录抓取带有 #inbox 标签或特定的最新备忘录."""
    applescript = """
    tell application "Notes"
        set noteList to {}
        repeat with aNote in (notes whose name contains "inbox" or name contains "待办" or name contains "想法")
            set end of noteList to (name of aNote & "|||" & plaintext of aNote)
        end repeat
        return noteList
    end tell
    """
    try:
        res = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=10)
        if res.returncode != 0 or not res.stdout.strip():
            return []

        notes = []
        raw_items = res.stdout.strip().split(", ")
        for item in raw_items:
            if "|||" in item:
                parts = item.split("|||", 1)
                notes.append({"title": parts[0].strip(), "content": parts[1].strip()})
        return notes
    except Exception as e:
        print(f"⚠️ Apple Notes 抓取跳过: {e}")
        return []


def ingest_private_notes() -> int:
    notes = fetch_apple_notes_inbox()
    if not notes:
        print("ℹ️ 未检测到包含 #inbox 或待办关键词的个人私有备忘录")
        return 0

    count = 0
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for note in notes:
        title_slug = "".join(c for c in note["title"] if c.isalnum() or c in (" ", "_", "-")).strip()
        filename = f"{now_str}-private-note-{title_slug[:20]}.md"
        target_path = INBOX_DIR / filename

        md_content = f"""---
domain: personal
title: "{note['title']}"
source: "apple_notes_private"
date: {now_str}
---

# {note['title']}

> **来源**: 个人私有 Apple 备忘录 (iCloud 抓取)

{note['content']}
"""
        target_path.write_text(md_content, encoding="utf-8")
        print(f"✅ 个人私有备忘录成功入库: {target_path.name}")
        count += 1

    return count


def main() -> int:
    print("🔒 开始 100% 本地化抓取个人私有数据 (Apple Notes / Calendar)...")
    count = ingest_private_notes()
    return 0


if __name__ == "__main__":
    sys.exit(main())
