#!/usr/bin/env bash
# resident-event-ingest wrapper (T6-15 R2b producer repair).
#
# The com.l4.resident.event-ingest launchd plist was generated as
#   uv <omo-dir> resident ingest --once
# which can never work (no `resident` console script in projects/omo, and
# `uv <dir> <cmd>` is not a valid invocation). This wrapper is the
# generator-expressible form of the working invocation:
#   uv run --frozen --project <omo> python -m omo.resident.cli ingest
# (--frozen 强制 launchd 定时任务不改写安装位受跟踪的 projects/omo/uv.lock)
#
# ADR-0456 B4b: 项目根由脚本自身位置推导 (BASH_SOURCE), 不写死检出根 ——
# 检出根与安装位两份拷贝逐字节相同, 各自跑各自根下的 projects/omo。
set -euo pipefail

_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_SELF_DIR/.." && pwd)"
OMO_PROJECT="$_REPO_ROOT/projects/omo"
_LEDGER="${OMO_EVENT_LEDGER_DB:-${OMOSTATION_STATE_ROOT:+${OMOSTATION_STATE_ROOT}/runtime/omo/event-ledger.sqlite3}}"
_LEDGER="${_LEDGER:-$_REPO_ROOT/runtime/omo/event-ledger.sqlite3}"

exec /opt/homebrew/bin/uv run --frozen --project "$OMO_PROJECT" \
  python -m omo.resident.cli ingest --ledger "$_LEDGER" "$@"
