#!/usr/bin/env python3
"""Mail Sender — .eml 草稿生成 (不自动发送, 人工确认).

Usage:
  python3 bin/ssot/mail-sender.py --draft --to xx --subject "通知" --body "内容"
  python3 bin/ssot/mail-sender.py --list-drafts
"""
from __future__ import annotations
import argparse
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from _shared import utc_now

DRAFTS_DIR = Path.home() / "Documents" / "@工作文档" / "卫健委" / "_drafts"


def create_draft(to: str, subject: str, body: str, cc: str = "", attachments: list[str] | None = None, from_addr: str = "ws-xxk@bjfsh.gov.cn") -> Path:
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"], msg["Date"] = from_addr, to, subject, utc_now()
    if cc:
        msg["Cc"] = cc
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if attachments:
        for fpath in attachments:
            p = Path(fpath)
            if p.exists():
                with open(p, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
                    msg.attach(part)
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "-" for c in subject[:20])
    path = DRAFTS_DIR / f"{utc_now()[:10]}-{safe}.eml"
    i = 1
    while path.exists():
        path = DRAFTS_DIR / f"{utc_now()[:10]}-{safe}-{i}.eml"
        i += 1
    path.write_bytes(msg.as_bytes())
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--list-drafts", action="store_true")
    parser.add_argument("--to", default="")
    parser.add_argument("--cc", default="")
    parser.add_argument("--subject", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--attach", nargs="*", default=[])
    args = parser.parse_args(argv)
    if args.list_drafts:
        if DRAFTS_DIR.exists():
            for f in sorted(DRAFTS_DIR.glob("*.eml"), key=lambda f: f.stat().st_mtime, reverse=True):
                print(f"  {f.name} ({f.stat().st_size // 1024}KB)")
        return 0
    if args.draft:
        path = create_draft(args.to, args.subject, args.body, args.cc, args.attach)
        print(f"✅ 草稿: {path}")
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
