#!/usr/bin/env python3
"""universal-private-ingest.py — 360° 本地私有源数据抓取器

包含:
1. Chrome 深度浏览历史 (Chrome History DB)
2. iPhone SMS 运营商短信 (chat.db)
3. Hermes 微信网关消息 (state.db)
4. 原生 Mac 微信接收物理文件/公文 (WeChat Native Files & Documents) — 100% 物理落地!

v3.0 (Native WeChat Files & Chat Ingestion) | 2026-07-31
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path("/Users/xiamingxing/Documents")
INBOX_DIR = DOCS_ROOT / "_inbox"


def fetch_chrome_real_history(limit: int = 15) -> list[dict[str, str]]:
    history_db = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"
    if not history_db.exists():
        return []

    temp_db = Path("/tmp/chrome_history_temp.db")
    items = []
    try:
        if temp_db.exists():
            temp_db.unlink()
        temp_db.write_bytes(history_db.read_bytes())

        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT url, title, visit_count FROM urls ORDER BY last_visit_time DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        for r in rows:
            url, title, _ = r
            if title and url:
                items.append({"title": title.strip(), "url": url.strip()})
    except Exception as e:
        print(f"⚠️ 读取 Chrome 历史数据库异常: {e}")
    finally:
        if temp_db.exists():
            temp_db.unlink()

    return items


def fetch_iphone_real_sms(limit: int = 15) -> list[dict[str, str]]:
    sms_db = Path.home() / "Library" / "Messages" / "chat.db"
    if not sms_db.exists():
        return []

    items = []
    try:
        conn = sqlite3.connect(str(sms_db))
        cursor = conn.cursor()
        cursor.execute("SELECT text, date FROM message WHERE text IS NOT NULL ORDER BY date DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        for r in rows:
            text, date_val = r
            if text:
                items.append({"text": str(text).replace("\n", " ").strip(), "date": str(date_val)})
    except Exception as e:
        print(f"⚠️ 读取 SMS chat.db 异常: {e}")

    return items


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


def fetch_native_wechat_files(limit: int = 10) -> list[dict[str, str]]:
    """物理提取 Mac 原生微信接收到的解密文件与公文附件."""
    wechat_container = Path.home() / "Library" / "Containers" / "com.tencent.xinWeChat" / "Data"
    if not wechat_container.exists():
        return []

    items = []
    try:
        # 扫描微信 Documents 下的文件与附件
        docs_dir = wechat_container / "Documents"
        for f in docs_dir.glob("**/*"):
            if f.is_file() and f.suffix.lower() in [".pdf", ".docx", ".doc", ".txt", ".md", ".png", ".jpg"]:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()
                items.append({
                    "file_name": f.name,
                    "file_path": str(f),
                    "mtime": mtime,
                    "size_bytes": str(f.stat().st_size)
                })
                if len(items) >= limit:
                    break
    except Exception as e:
        print(f"⚠️ 扫描 Mac 微信原生接收文件异常: {e}")

    return items


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
    sms_items = fetch_iphone_real_sms()
    if sms_items:
        target_path = INBOX_DIR / f"{now_str}-auto-iphone-sms.md"
        lines = [f"# iPhone 真实 SMS 运营商短信 — {now_str}\n\n> 来源: 本地 SMS Messages 数据库\n"]
        for sms in sms_items:
            lines.append(f"- **[{sms['date']}]**: {sms['text']}")
        target_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"✅ 真实 iPhone SMS 短信抓取成功 ──► {target_path.name}")
        count += 1

    # 3. 真实 微信 网关聊天与指令抓取
    wechat_items = fetch_real_wechat_messages()
    if wechat_items:
        target_path = INBOX_DIR / f"{now_str}-auto-wechat-chat.md"
        lines = [f"# 微信网关真实聊天与指令记录 — {now_str}\n\n> 来源: 本地 Hermes 微信网关 state.db 数据库\n"]
        for msg in wechat_items:
            lines.append(f"- **[{msg['role']} @ {msg['timestamp']}]** ({msg['session_id']}): {msg['content']}")
        target_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"✅ 真实 微信 网关消息物理抓取成功 ──► {target_path.name}")
        count += 1

    # 4. 原生 Mac 微信接收物理文件抓取 (全新落地!)
    wechat_files = fetch_native_wechat_files()
    if wechat_files:
        target_path = INBOX_DIR / f"{now_str}-auto-wechat-native-files.md"
        lines = [f"# Mac 原生微信接收物理文件与公文附件 — {now_str}\n\n> 来源: com.tencent.xinWeChat 物理文件区\n"]
        for wf in wechat_files:
            lines.append(f"- **[{wf['file_name']}]** (路径: `{wf['file_path']}`, 大小: {wf['size_bytes']} 字节, 修改时间: {wf['mtime']})")
        target_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"✅ 原生 Mac 微信物理接收文件抓取成功 ──► {target_path.name}")
        count += 1

    return count


def main() -> int:
    print("🔒 启动真实 Chrome 历史、iPhone SMS、微信网关与 原生微信接收文件 抓取...")
    count = ingest_chrome_and_sms()
    print(f"🎉 真实抓取完成: 成功抓取入库 {count} 个私有源数据块")
    return 0


if __name__ == "__main__":
    sys.exit(main())
