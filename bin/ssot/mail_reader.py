#!/usr/bin/env python3
"""Mail Reader — 统一读取 Apple Mail + 网易邮箱大师, 输出标准化邮件列表.

Usage:
  python3 bin/ssot/mail_reader.py --json
  python3 bin/ssot/mail_reader.py --source apple --limit 5
  python3 bin/ssot/mail_reader.py --source netease --account work
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _shared import utc_now

HOME = Path.home()
APPLE_DB = HOME / "Library" / "Mail" / "V10" / "MailData" / "Envelope Index"
NETEASE_BASE = HOME / "Library" / "Containers" / "com.netease.macmail" / "Data" / "Library" / "Application Support" / "data"
NETEASE_ACCOUNTS = {"work": "ws-xxk@bjfsh.gov.cn_2160", "personal": "xia_mingxing@163.com_6928", "secondary": "fshxxk@163.com_8688"}


@dataclass
class Mail:
    source: str = ""
    subject: str = ""
    sender: str = ""
    recipient: str = ""
    date: str = ""
    body: str = ""
    attachments: list[str] = field(default_factory=list)
    unread: bool = False
    account: str = ""


def read_apple_mail(limit: int = 20, unread_only: bool = False) -> list[Mail]:
    if not APPLE_DB.exists():
        return []
    mails: list[Mail] = []
    try:
        conn = sqlite3.connect(f"file:{APPLE_DB}?mode=ro", uri=True)
        query = """
            SELECT m.ROWID, s.subject, a.address, m.summary, m.read, m.date_received
            FROM messages m
            LEFT JOIN subjects s ON m.subject = s.ROWID
            LEFT JOIN addresses a ON m.sender = a.ROWID
            WHERE s.subject IS NOT NULL AND s.subject != ''
        """
        if unread_only:
            query += " AND m.read = 0"
        query += " ORDER BY m.date_received DESC LIMIT ?"
        for row in conn.execute(query, (limit,)).fetchall():
            _, subject, sender, summary, read, date_rcv = row
            date_str = ""
            if date_rcv:
                dt = datetime(2001, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=date_rcv)
                date_str = dt.isoformat()[:19] + "Z"
            mails.append(Mail(source="apple_mail", subject=str(subject or "")[:200], sender=str(sender or ""), date=date_str, body=str(summary or "")[:500], unread=not read if read is not None else False))
        conn.close()
    except Exception:
        pass
    return mails


def read_netease_mail(account_key: str = "work", limit: int = 20, unread_only: bool = False) -> list[Mail]:
    acct_dir = NETEASE_ACCOUNTS.get(account_key, "")
    if not acct_dir:
        return []
    data_path = NETEASE_BASE / acct_dir
    if not data_path.exists():
        return []
    mail_db = data_path / "mail.db"
    if not mail_db.exists():
        return []

    # search.db: FTS5 c0=标题 c1=发件人 c5=正文 c6=附件名
    search_data: dict[int, dict] = {}
    search_db = data_path / "search.db"
    if search_db.exists():
        try:
            sconn = sqlite3.connect(f"file:{search_db}?mode=ro", uri=True)
            for sr in sconn.execute("SELECT id, c0, c1, c2, c5, c6 FROM Search_content ORDER BY id DESC LIMIT ?", (limit * 2,)).fetchall():
                search_data[sr[0]] = {"subject": str(sr[1] or "").strip()[:200], "sender": str(sr[2] or "").strip().split("\n")[0][:100], "recipients": str(sr[3] or "").strip()[:200], "body": str(sr[4] or "").strip()[:500], "attachment": str(sr[5] or "").strip()[:100]}
            sconn.close()
        except Exception:
            pass

    mails: list[Mail] = []
    try:
        conn = sqlite3.connect(f"file:{mail_db}?mode=ro", uri=True)
        # 先查 MailMeta 元数据 (总是执行, 不依赖 content.db)
        query = "SELECT LocalId, OrigDate, ReceivedDate, Unread FROM MailMeta"
        if unread_only:
            query += " WHERE Unread = 1"
        query += " ORDER BY ReceivedDate DESC LIMIT ?"
        rows = conn.execute(query, (limit,)).fetchall()
        local_ids = [r[0] for r in rows]

        # content.db 正文 (可选, 失败不影响元数据)
        body_map: dict[int, str] = {}
        content_db = data_path / "content.db"
        if content_db.exists() and local_ids:
            try:
                cconn = sqlite3.connect(f"file:{content_db}?mode=ro", uri=True)
                ph = ",".join("?" * len(local_ids))
                for cr in cconn.execute(f"SELECT MailId, OrigBody FROM MailContent WHERE MailId IN ({ph})", local_ids).fetchall():
                    body_map[cr[0]] = str(cr[1] or "")[:500]
                cconn.close()
            except Exception:
                pass

        for row in rows:
            local_id, orig_date, recv_date, unread = row
            sd = search_data.get(local_id, {})
            date_str = ""
            ts = recv_date or orig_date or 0
            if ts and ts > 100000000000:
                date_str = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()[:19] + "Z"
            body_text = sd.get("body", "") or body_map.get(local_id, "")
            attachments = [sd["attachment"]] if sd.get("attachment") else []
            mails.append(Mail(source=f"netease_{account_key}", subject=sd.get("subject", ""), sender=sd.get("sender", ""), recipient=sd.get("recipients", ""), date=date_str, body=body_text, attachments=attachments, unread=bool(unread), account=acct_dir.rsplit("_", 1)[0]))
        conn.close()
    except Exception:
        pass
    return mails


def read_all(limit: int = 20, unread_only: bool = False) -> list[Mail]:
    all_mails: list[Mail] = []
    all_mails.extend(read_apple_mail(limit, unread_only))
    all_mails.extend(read_netease_mail("work", limit, unread_only))
    all_mails.extend(read_netease_mail("personal", limit, unread_only))
    all_mails.sort(key=lambda m: m.date or "", reverse=True)
    return all_mails[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source", choices=["apple", "netease", "all"], default="all")
    parser.add_argument("--account", choices=["work", "personal", "secondary"], default="work")
    parser.add_argument("--unread-only", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)

    if args.source == "apple":
        mails = read_apple_mail(args.limit, args.unread_only)
    elif args.source == "netease":
        mails = read_netease_mail(args.account, args.limit, args.unread_only)
    else:
        mails = read_all(args.limit, args.unread_only)

    if args.json:
        print(json.dumps([asdict(m) for m in mails], ensure_ascii=False, indent=2))
    else:
        print(f"📧 邮件读取: {len(mails)} 封 ({utc_now()})")
        for m in mails:
            status = "●" if m.unread else "✓"
            print(f"  {status} [{m.source}] {m.subject[:50]}")
            print(f"    From: {m.sender[:40]}  Date: {m.date[:19]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
