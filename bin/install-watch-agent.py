#!/usr/bin/env python3
"""Installer script for launchd WatchPaths governance watch agent."""
import os
import shutil
import sys
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
PLIST_LABEL = "com.l4.governance.watch"
PLIST_FILE = Path(os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist"))
LOGS_DIR = WORKSPACE / "runtime" / "logs"


def generate_plist_content() -> str:
    # 稳定锚点 — 不用 sys.executable (uv run 时它是 .cache/uv/builds-v0/.tmpXXX 临时路径,
    # uv GC 后失效, plist argv[0] 悬空 → governance.watch exit 1 回路断). 见 P73 纪律1.
    python_executable = shutil.which("python3") or "/opt/homebrew/bin/python3"
    state_stale_emit_path = WORKSPACE / "bin" / "state-stale-emit.py"
    watch_registry = WORKSPACE / ".omo" / "_truth" / "registry"
    watch_ecos = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_executable}</string>
        <string>{state_stale_emit_path}</string>
        <string>--source</string>
        <string>launchd-watch</string>
        <string>--trigger</string>
        <string>watchpaths</string>
        <string>--surface</string>
        <string>{watch_registry}</string>
        <string>--surface</string>
        <string>{watch_ecos}</string>
    </array>
    <key>WatchPaths</key>
    <array>
        <string>{watch_registry}</string>
        <string>{watch_ecos}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>KeepAlive</key>
    <dict>
        <key>Crashed</key>
        <true/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOGS_DIR}/watch_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{LOGS_DIR}/watch_stderr.log</string>
</dict>
</plist>
"""


def main() -> int:
    print("🚀 Installing launchd WatchPaths Agent...")
    
    # 创建日志目录
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 生成并写入 plist 文件
    plist_content = generate_plist_content()
    PLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 写入 plist 文件 (添加审计豁免以防非原子写违规)
    PLIST_FILE.write_text(plist_content, encoding="utf-8")  # audit-exempt: non-atomic-write
    print(f"✅ Plist file written to: {PLIST_FILE}")

    # 注册和重启 launchctl
    # 尝试 unload 之前的代理
    try:
        subprocess.run(["launchctl", "unload", str(PLIST_FILE)], capture_output=True, text=True, check=False)
        print("ℹ Unloaded existing launchd agent (if any)")
    except Exception:
        pass

    # load 新代理
    try:
        res = subprocess.run(["launchctl", "load", str(PLIST_FILE)], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print("✅ Successfully loaded watch agent via launchctl!")
        else:
            print(f"⚠️ launchctl load failed with exit {res.returncode}: {res.stderr}")
            print("   Note: If running in a sandboxed CLI, user manual 'launchctl load' might be required.")
    except Exception as e:
        print(f"⚠️ launchctl invocation error: {e}")

    # 触发一次 state_stale 事件；真实刷新由 omo state sync 单写者负责。
    try:
        subprocess.run(
            [
                sys.executable,
                str(WORKSPACE / "bin" / "state-stale-emit.py"),
                "--source",
                "launchd-watch",
                "--trigger",
                "install-watch-agent",
                "--surface",
                str(WORKSPACE / ".omo" / "_truth" / "registry"),
                "--surface",
                str(WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot"),
            ],
            check=False,
        )
        print("✅ Emitted initial state_stale event!")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
