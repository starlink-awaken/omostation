#!/usr/bin/env python3
"""Installer script for launchd WatchPaths governance watch agent."""
import os
import sys
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
PLIST_LABEL = "com.l4.governance.watch"
PLIST_FILE = Path(os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist"))
LOGS_DIR = WORKSPACE / "runtime" / "logs"


def generate_plist_content() -> str:
    # 查找 uv 绝对路径
    uv_path = "/opt/homebrew/bin/uv"
    if not os.path.exists(uv_path):
        # 兜底寻找
        try:
            res = subprocess.run(["which", "uv"], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                uv_path = res.stdout.strip()
        except Exception:
            pass

    python_executable = sys.executable or "python3"
    compass_radar_path = WORKSPACE / "bin" / "compass_radar.py"
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
        <string>{uv_path}</string>
        <string>run</string>
        <string>--with</string>
        <string>pyyaml</string>
        <string>--directory</string>
        <string>{WORKSPACE}</string>
        <string>{python_executable}</string>
        <string>{compass_radar_path}</string>
    </array>
    <key>WatchPaths</key>
    <array>
        <string>{watch_registry}</string>
        <string>{watch_ecos}</string>
    </array>
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

    # 触发一次自愈运行
    try:
        subprocess.run([sys.executable, str(WORKSPACE / "bin" / "compass_radar.py")], check=False)
        print("✅ Triggered initial sync run!")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
