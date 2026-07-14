#!/usr/bin/env python3
"""Installer for launchd WatchPaths governance watch agent.

Plist 单源: 委托 bin/mof/gen-service-configs.py 从 .omo/_truth/registry/services.yaml 生.
本脚本不再硬编码 plist (治活火山: 原 generate_plist_content() 与 services.yaml 不一致致 drift 反复,
见 [[feedback-loop-recovery-generator-trap]] + [[services-yaml-registry-landed]]).

职责: gen plist (SSOT) → launchctl reload → 触发首次 state_stale.
"""
import os
import shutil
import sys
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
PLIST_LABEL = "com.l4.governance.watch"
PLIST_FILE = Path(os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist"))
LOGS_DIR = WORKSPACE / "runtime" / "logs"


def main() -> int:
    print("🚀 Installing launchd WatchPaths Agent (委托 gen-service-configs 从 services.yaml 生 plist)...")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 1. 委托 gen-service-configs 从 services.yaml 生 plist (SSOT 单源, 治活火山)
    python3 = shutil.which("python3") or "/opt/homebrew/bin/python3"
    gen = WORKSPACE / "bin" / "gen-service-configs.py"
    r = subprocess.run(
        [python3, str(gen), "--write"],
        cwd=WORKSPACE, capture_output=True, text=True, check=False,
    )
    if r.stdout:
        print(r.stdout.strip())
    if r.returncode != 0:
        print(f"❌ gen-service-configs --write failed: {r.stderr}", file=sys.stderr)
        return 1

    # 2. launchctl reload (unload 旧 + load 新)
    try:
        subprocess.run(["launchctl", "unload", str(PLIST_FILE)], capture_output=True, text=True, check=False)
    except Exception:
        pass
    try:
        res = subprocess.run(["launchctl", "load", str(PLIST_FILE)], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print("✅ Successfully loaded watch agent via launchctl!")
        else:
            print(f"⚠️ launchctl load failed (exit {res.returncode}): {res.stderr}")
            print("   Note: sandboxed CLI may need manual 'launchctl load'.")
    except Exception as e:
        print(f"⚠️ launchctl invocation error: {e}")

    # 3. 触发首次 state_stale 事件 (即时 echo, 不等 launchd RunAtLoad 调度).
    # args --trigger=install-watch-agent 标记手动触发源 (与 plist launchd 触发 --trigger=watchpaths 区分).
    try:
        registry = WORKSPACE / ".omo" / "_truth" / "registry"
        ecos_ssot = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot"
        subprocess.run(
            [
                python3,
                str(WORKSPACE / "bin" / "state-stale-emit.py"),
                "--source", "launchd-watch",
                "--trigger", "install-watch-agent",
                "--surface", str(registry),
                "--surface", str(ecos_ssot),
            ],
            check=False,
        )
        print("✅ Emitted initial state_stale event!")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
