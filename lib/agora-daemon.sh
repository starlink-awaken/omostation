#!/usr/bin/env bash
# agora-daemon wrapper (ADR-0435 模式, 2026-09-10 修复 exit 78 崩循环).
# 旧 plist 双重死: WorkingDirectory 指向已清理的 T1-12 临时 worktree
# (ws-t1-12-agora-launchd-deploy) + 裸 python3 无依赖环境。
# 正确形态: uv run (装齐 agora 依赖) + 由脚本自身位置推出仓根, cd 后跑 daemon.py。
set -euo pipefail
# 仓库根 = 本脚本所在 lib/ 的上一级 (安装位与检出根各自自推, 互不引用)
_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_SELF_DIR/.." && pwd)"
cd "$_REPO_ROOT/projects/agora"
exec /opt/homebrew/bin/uv run python src/agora/daemon.py
