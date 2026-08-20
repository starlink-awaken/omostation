#!/usr/bin/env python3
"""apple_mail_watcher.py — Apple Mail 真实信号 watcher (W4-D3)."""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, time
from pathlib import Path

MAIL_DIR = Path.home() / "Library" / "Mail"
ROUTED = Path(".omo/state/routed-signals.json")

def scan_inbox() -> list:
    """扫描 Apple Mail INBOX 提取真实信号."""
    r = subprocess.run(["find", str(MAIL_DIR), "-name", "INBOX.mbox"], capture_output=True, text=True)
    files = [f for f in r.stdout.strip().split("\n") if f] if r.stdout.strip() else []
    signals = []
    for f in files:
        try:
            stat = os.stat(f)
            signals.append({
                "source": "apple_mail",
                "file": f,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "signal_id": hashlib.sha1(f.encode()).hexdigest()[:12],
            })
        except Exception:
            pass
    return signals

def main():
    signals = scan_inbox()
    routed = []
    if ROUTED.exists():
        routed = json.loads(ROUTED.read_text())
    seen = {r.get("signal_id") for r in routed}
    new = [s for s in signals if s["signal_id"] not in seen]
    for s in new:
        s["routed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        s["source_scene"] = "document-review"  # Apple Mail 默认路由
        routed.append(s)
    ROUTED.write_text(json.dumps(routed, indent=2, ensure_ascii=False))
    print(f"扫描: {len(signals)} 个 mbox, 新增: {len(new)} 个信号")

if __name__ == "__main__":
    sys.exit(main() or 0)
