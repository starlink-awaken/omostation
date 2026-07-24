#!/usr/bin/env python3
"""Governance checker and builder for cockpit-ui static asset alignment."""
import os
import sys
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
configured_dist = os.environ.get("COCKPIT_UI_DIST", "").strip()
if configured_dist:
    configured_path = Path(configured_dist).expanduser()
    COCKPIT_UI_DIR = configured_path.parent if configured_path.name == "dist" else configured_path
else:
    COCKPIT_UI_DIR = WORKSPACE / "projects" / "cockpit-ui"
DIST_INDEX = COCKPIT_UI_DIR / "dist" / "index.html"


def try_build() -> bool:
    print("ℹ cockpit-ui static assets (dist/index.html) missing. Attempting self-heal build...")
    
    # 尝试使用 bun 或是 npm 进行构建
    managers = [
        ("bun", ["bun", "run", "build"]),
        ("npm", ["npm", "run", "build"])
    ]
    
    for name, cmd in managers:
        try:
            # 检查命令是否存在
            subprocess.run(["which", cmd[0]], capture_output=True, check=True)
            print(f"🚀 Found {name}. Running '{' '.join(cmd)}' in {COCKPIT_UI_DIR}...")
            
            # 运行 build 进程
            res = subprocess.run(
                cmd,
                cwd=COCKPIT_UI_DIR,
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                print(f"✅ Successfully built cockpit-ui static assets using {name}!")
                return True
            else:
                print(f"⚠️ {name} build failed: {res.stderr}")
        except Exception:
            pass
            
    return False


def main() -> int:
    if not COCKPIT_UI_DIR.is_dir():
        print(f"⏭️  Skip: cockpit-ui directory not found at {COCKPIT_UI_DIR} (not a submodule, not in CI)")
        return 0

    if DIST_INDEX.is_file():
        print("✅ cockpit-ui static assets are aligned and present in dist/.")
        return 0
        
    # 如果不存在，尝试自愈构建
    if try_build() and DIST_INDEX.is_file():
        return 0
        
    # 如果自愈构建失败，抛出错误并提供明确的人工干预指南
    print("\n🚨 ARCHITECTURE FAULT: cockpit-ui static assets (dist/index.html) are missing!")
    print("   This causes FastAPI / dashboard web console to return 404 Not Found.")
    print("👉 Human decision needed: Please navigate to projects/cockpit-ui and execute:")
    print("   1) bun install (or npm install)")
    print("   2) bun run build (or npm run build)")
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
