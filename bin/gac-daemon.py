#!/usr/bin/env python3
"""gac-daemon — GaC 物理沙箱 P3 POC (omo daemon 架构验证).

P3 (FS 沙箱) 最小 POC: unix socket daemon, write API 替代直写.
证明 "经 daemon 写" 架构可行 (socket + write + 客户端 + 原子写).

真正 P3 (chmod .omo daemon 独占写, 非 daemon 物理写不了) 留完整实现 (长期).
本 POC 不 chmod (避免全局影响), 只验证 daemon 写 API 工作 + 原子写.

架构:
  client (gac-daemon --write) → unix socket → daemon (--start) → 原子写文件

用法:
  python3 bin/gac-daemon.py --start              # 启动 daemon (前台, 阻塞)
  python3 bin/gac-daemon.py --write PATH CONTENT  # 经 daemon 写
  python3 bin/gac-daemon.py --stop               # 停 daemon
  python3 bin/gac-daemon.py --ping               # 查 daemon 活

POC 验证: 经 daemon 写文件 + 原子写 (mkstemp + os.replace) + 客户端/daemon 通信.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

SOCKET_PATH = "/tmp/gac-daemon.sock"
BUFFER = 65536


def daemon_loop() -> None:
    """daemon 主循环 (unix socket, recv write/stop 请求, 原子写)."""
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCKET_PATH)
    srv.listen(5)
    print(f"gac-daemon listening {SOCKET_PATH}", file=sys.stderr)
    try:
        while True:
            conn, _ = srv.accept()
            try:
                data = conn.recv(BUFFER).decode("utf-8")
                req = json.loads(data)
                cmd = req.get("cmd")
                if cmd == "ping":
                    conn.sendall(json.dumps({"ok": True, "pong": True}).encode())
                elif cmd == "write":
                    path = Path(req["path"])
                    content = req["content"]
                    # 原子写 (mkstemp + os.replace, 防半写)
                    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".gac-daemon-")
                    try:
                        os.write(fd, content.encode("utf-8"))
                        os.close(fd)
                        os.replace(tmp, path)
                        conn.sendall(json.dumps({"ok": True, "path": str(path)}).encode())
                    except Exception as e:
                        conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode())
                elif cmd == "stop":
                    conn.sendall(json.dumps({"ok": True}).encode())
                    break
                else:
                    conn.sendall(json.dumps({"ok": False, "error": f"未知 cmd: {cmd}"}).encode())
            finally:
                conn.close()
    finally:
        srv.close()
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)


def _send(req: dict) -> dict:
    """客户端: 连 daemon socket 发请求."""
    if not os.path.exists(SOCKET_PATH):
        return {"ok": False, "error": f"daemon 未启动 ({SOCKET_PATH})"}
    cli = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    cli.connect(SOCKET_PATH)
    cli.sendall(json.dumps(req).encode())
    resp = json.loads(cli.recv(BUFFER).decode("utf-8"))
    cli.close()
    return resp


def main() -> int:
    parser = argparse.ArgumentParser(description="GaC 物理沙箱 P3 POC (omo daemon)")
    parser.add_argument("--start", action="store_true", help="启动 daemon (前台阻塞)")
    parser.add_argument("--write", nargs=2, metavar=("PATH", "CONTENT"), help="经 daemon 写")
    parser.add_argument("--stop", action="store_true", help="停 daemon")
    parser.add_argument("--ping", action="store_true", help="查 daemon 活")
    parser.add_argument(
        "--lockdown",
        metavar="OMO_DIR",
        help="P3 独占写激活: chmod OMO_DIR 0700 (owner-only, agent 直写失败需经 daemon --write). ⚠️影响全局",
    )
    parser.add_argument(
        "--unlock",
        metavar="OMO_DIR",
        help="解锁 P3 lockdown: chmod OMO_DIR 0755 恢复默认",
    )
    args = parser.parse_args()

    if args.lockdown:
        from pathlib import Path

        omo = Path(args.lockdown).resolve()
        if not omo.exists():
            print(f"❌ OMO_DIR not found: {omo}", file=sys.stderr)
            return 1
        for p in [omo, *omo.rglob("*")]:
            if p.is_dir():
                p.chmod(0o700)
        print(f"🔒 P3 lockdown: {omo} chmod 0700 (owner-only write, agent 需经 daemon --write)")
        print(f"   解锁: gac-daemon.py --unlock {omo}")
        return 0
    if args.unlock:
        from pathlib import Path

        omo = Path(args.unlock).resolve()
        if not omo.exists():
            print(f"❌ OMO_DIR not found: {omo}", file=sys.stderr)
            return 1
        for p in [omo, *omo.rglob("*")]:
            if p.is_dir():
                p.chmod(0o755)
        print(f"🔓 P3 unlock: {omo} chmod 0755 (默认恢复)")
        return 0

    if args.start:
        daemon_loop()
        return 0
    if args.ping:
        print(json.dumps(_send({"cmd": "ping"}), ensure_ascii=False))
        return 0
    if args.write:
        path, content = args.write
        result = _send({"cmd": "write", "path": path, "content": content})
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    if args.stop:
        print(json.dumps(_send({"cmd": "stop"}), ensure_ascii=False))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
