#!/usr/bin/env bash
# resident-event-ingest wrapper (T6-15 R2b producer repair).
#
# The com.l4.resident.event-ingest launchd plist was generated as
#   uv <omo-dir> resident ingest --once
# which can never work (no `resident` console script in projects/omo, and
# `uv <dir> <cmd>` is not a valid invocation). This wrapper is the
# generator-expressible form of the working invocation:
#   uv run --project <omo> python -m omo.resident.cli ingest
#
# ADR-0456 B4b: 项目根由脚本自身位置推导 (BASH_SOURCE), 不写死检出根 ——
# 检出根与安装位两份拷贝逐字节相同, 各自跑各自根下的 projects/omo。
set -euo pipefail

_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_SELF_DIR/.." && pwd)"
OMO_PROJECT="$_REPO_ROOT/projects/omo"

exec /opt/homebrew/bin/uv run --project "$OMO_PROJECT" \
  python -m omo.resident.cli ingest
