#!/bin/bash
# sync-stable.sh — 稳定副本同步纪律 (协作协议条款 B 配套, 2026-08-25)
#
# runtime/ssot-stable/ 是 launchd/cron 常驻任务的抗断档副本(分支漂移
# 不断供, mail-daemon 8h 断档实锤后的制度)。本脚本在变更里程碑后手动跑,
# 把 bin/ssot 的运行时脚本同步过去。
#
# 用法: bash runtime/ssot-stable/sync-stable.sh
# (2026-08-25: 从 bin/ssot/ 挪入本目录 — bin 配额规则"增1须删1",
# 本脚本语义上就是 stable 目录的配套工具, 不该占 bin 名额)
set -euo pipefail

STABLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$STABLE/../.." && pwd)/bin/ssot"

FILES=(
  mail_daemon.py
  mail_agent.py
  mail_reader.py
  mail_sender.py
  doc_generator.py
  _llm_helper.py
  _shared.py
  journey-runner.py
  admin_scenes.py
)

for f in "${FILES[@]}"; do
  \cp -f "$SRC/$f" "$STABLE/$f"
done

echo "✅ 稳定副本已同步: ${#FILES[@]} files → $STABLE"
