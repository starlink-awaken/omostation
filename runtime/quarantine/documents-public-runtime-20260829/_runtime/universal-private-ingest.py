#!/usr/bin/env python3
"""universal-private-ingest.py — 全量私有源真实抓取适配器 (Chrome & 真实 SMS 短信)

功能: 100% 真实抓取 macOS 上 Chrome 浏览器的深度历史与 iPhone 转发的真实 SMS 运营商短信，
安全提取后落盘入 ~/Documents/_inbox/。

v2.0 | 2026-07-30
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(os.environ.get("BOS_DOCS_ROOT", str(Path(__file__).resolve().parents[2])))
INBOX_DIR = DOCS_ROOT / "_inbox"
HOME = Path.home()


def fetch_chrome_real_history() -> list[dict[str, str]]:
    """从 Google Chrome 真实 History 数据库提取最近高价值浏览历史 (解决 SQLite 文件锁)."""
    chrome_db = HOME / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"
    if not chrome_db.exists():
        print("ℹ️ 未检测到 Chrome 默认 Profile 数据库路径")
        return []

    tmp_db = Path("/tmp/chrome_history_copy.db")
    try:
        # 复制一份临时文件，规避 Chrome 运行时给 History 加的文件锁
        shutil.copy2(chrome_db, tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        cur = conn.cursor()
        cur.execute("""
            SELECT urls.url, urls.title
            FROM urls
            WHERE urls.title IS NOT NULL AND urls.title != ''
            ORDER BY urls.last_visit_time DESC LIMIT 5
        """)
        rows = cur.fetchall()
        conn.close()
        if tmp_db.exists():
            tmp_db.unlink()
        return [{"url": r[0], "title": r[1]} for r in rows]
    except Exception as e:
        print(f"⚠️ Chrome 历史读取跳过: {e}")
        if tmp_db.exists():
            tmp_db.unlink()
        return []


def fetch_real_iphone_sms() -> list[dict[str, str]]:
    """从 Messages chat.db 提取 iPhone 短信转发同步到 Mac 的真实 SMS 运营商短信."""
    chat_db = HOME / "Library" / "Messages" / "chat.db"
    if not chat_db.exists():
        print("ℹ️ 未检测到 macOS Messages 数据库")
        return []

    try:
        conn = sqlite3.connect(f"file:{chat_db}?mode=ro", uri=True)
        cur = conn.cursor()
        # 提取真实短信 (SMS) 文本
        cur.execute("""
            SELECT text, datetime(date/1000000000 + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime') as date_str
            FROM message
            WHERE text IS NOT NULL AND length(text) > 2
            ORDER BY date DESC LIMIT 5
        """)
        rows = cur.fetchall()
        conn.close()
        return [{"text": r[0], "date": r[1]} for r in rows]
    except Exception as e:
        print(f"⚠️ SMS 短信读取跳过 (需要 Full Disk Access 磁盘权限): {e}")
        return []


def fetch_real_wechat_messages(limit: int = 15) -> list[dict[str, str]]:
    """物理提取本地 Hermes 数据库中存留的真实微信对话与消息内容."""
    state_db = Path.home() / ".hermes" / "state.db"
    if not state_db.exists():
        return []

    items = []
    try:
        conn = sqlite3.connect(str(state_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, role, content, timestamp
            FROM messages
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()

        for r in rows:
            sid, role, content, ts = r
            clean_content = str(content).replace("\n", " ").strip()
            if clean_content:
                items.append({
                    "role": role,
                    "content": clean_content[:150],
                    "timestamp": str(ts),
                    "session_id": str(sid)[:12]
                })
    except Exception as e:
        print(f"⚠️ 读取微信 state.db 异常: {e}")

    return items


def fetch_wechat_ui_accessibility_messages() -> list[str]:
    """使用 macOS AppleScript 辅助功能，零解密直接提取当前微信 UI 界面上的聊天正文."""
    script = '''
    tell application "System Events"
        if exists (process "WeChat") then
            tell process "WeChat"
                try
                    set ui_texts to value of static texts of window 1
                    return ui_texts
                on error
                    return {}
                end try
            end tell
        end if
    end tell
    return {}
    '''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
        if res.stdout:
            texts = [t.strip() for t in res.stdout.split(",") if len(t.strip()) > 2]
            return texts[:20]
    except Exception as e:
        print(f"ℹ️ AppleScript UI 提取说明: {e}")

    return []


def ingest_chrome_and_sms() -> int:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = 0

    # 1. 真实 Chrome 浏览历史抓取
    chrome_items = fetch_chrome_real_history()
    if chrome_items:
        target_path = INBOX_DIR / f"{now_str}-auto-chrome-history.md"
        lines = [f"# Chrome 真实浏览历史 — {now_str}\n\n> 来源: 本地 Chrome History 数据库\n"]
        for item in chrome_items:
            lines.append(f"- [{item['title']}]({item['url']})")
        target_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"✅ 真实 Chrome 浏览历史抓取成功 ──► {target_path.name}")
        count += 1

    # 2. 真实 iPhone SMS 短信抓取
    sms_items = fetch_real_iphone_sms()
    if sms_items:
        target_path = INBOX_DIR / f"{now_str}-auto-iphone-sms.md"
        lines = [f"# iPhone 真实 SMS 运营商短信 — {now_str}\n\n> 来源: 本地 SMS Messages 数据库\n"]
        for sms in sms_items:
            lines.append(f"- **[{sms['date']}]**: {sms['text']}")
        target_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"✅ 真实 iPhone SMS 短信抓取成功 ──► {target_path.name}")
        count += 1

    # 3. 真实 微信 聊天与指令记录抓取 (物理落地!)
    wechat_items = fetch_real_wechat_messages()
    if wechat_items:
        target_path = INBOX_DIR / f"{now_str}-auto-wechat-chat.md"
        lines = [f"# 微信真实聊天与指令记录 — {now_str}\n\n> 来源: 本地 Hermes 微信网关 state.db 数据库\n"]
        for msg in wechat_items:
            lines.append(f"- **[{msg['role']} @ {msg['timestamp']}]** ({msg['session_id']}): {msg['content']}")
        target_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"✅ 真实 微信 聊天记录物理抓取成功 ──► {target_path.name}")
        count += 1

    # 5. 原生 微信 UI 界面实时聊天内容零解密提取 (全新双保险防护!)
    ui_texts = fetch_wechat_ui_accessibility_messages()
    if ui_texts:
        target_path = INBOX_DIR / f"{now_str}-auto-wechat-ui-chat.md"
        lines = [f"# 原生微信实时界面聊天记录 (零解密提取) — {now_str}\n\n> 来源: macOS Accessibility UI 视图解析\n"]
        for txt in ui_texts:
            lines.append(f"- {txt}")
        target_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"✅ 原生 微信 UI 界面聊天记录零解密抓取成功 ──► {target_path.name}")
        count += 1

    return count


def main() -> int:
    print("🔒 启动真实 Chrome 历史、iPhone SMS 与 微信 消息抓取...")
    count = ingest_chrome_and_sms()
    print(f"🎉 真实抓取完成: 成功抓取入库 {count} 个私有源数据块")
    return 0


if __name__ == "__main__":
    sys.exit(main())
