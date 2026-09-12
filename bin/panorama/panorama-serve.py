#!/usr/bin/env python3
"""panorama-serve.py — 织星全景驾驶舱静态服务。

serve runtime/dashboard/（panorama-collect.py 的产物）于 http://127.0.0.1:43910。
只读静态服务，无 API、无写入。生产由 launchd 常驻（com.omostation.panorama-dashboard）。

用法：
    python3 bin/panorama/panorama-serve.py            # 前台服务（Ctrl-C 停）
    python3 bin/panorama/panorama-serve.py --once     # 只采集+生成，不 serve
"""

from __future__ import annotations

import argparse
import http.server
import os
import subprocess
import sys
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "runtime" / "dashboard"
COLLECT = ROOT / "bin" / "panorama" / "panorama-collect.py"
PORT = int(os.environ.get("PANORAMA_PORT", "43910"))


def ensure_fresh() -> int:
    r = subprocess.run([sys.executable, str(COLLECT)], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
    return r.returncode


def _refresh_loop(interval: int = 300) -> None:
    import threading
    import time

    def loop() -> None:
        while True:
            time.sleep(interval)
            try:
                subprocess.run([sys.executable, str(COLLECT)], cwd=ROOT,
                               capture_output=True, text=True, timeout=300)
            except Exception:  # noqa: BLE001
                pass

    threading.Thread(target=loop, daemon=True, name="panorama-refresh").start()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="只采集生成，不启动服务")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-refresh", action="store_true", help="服务内不启用 5min 自动刷新")
    args = ap.parse_args()

    code = ensure_fresh()
    if code != 0:
        return code
    if args.once:
        return 0

    if not (OUT_DIR / "index.html").is_file():
        print(f"ERROR: {OUT_DIR}/index.html 不存在，先运行 collect")
        return 1

    if not args.no_refresh:
        _refresh_loop()

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT_DIR))
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None  # 静默
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as srv:
        print(f"🛰  织星全景驾驶舱: http://127.0.0.1:{args.port}  (只读静态 · 5min 自动刷新 · Ctrl-C 停)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")
    return 0


if __name__ == "__main__":
    sys.exit(main())
