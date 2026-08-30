#!/usr/bin/env bash
# resident-event-ingest wrapper (T6-15 R2b producer repair).
#
# The com.l4.resident.event-ingest launchd plist was generated as
#   uv <omo-dir> resident ingest --once
# which can never work (no `resident` console script in projects/omo, and
# `uv <dir> <cmd>` is not a valid invocation). This wrapper is the
# generator-expressible form of the working invocation:
#   uv run --project <omo> python -m omo.resident.cli ingest
set -euo pipefail
exec /opt/homebrew/bin/uv run --project /Users/xiamingxing/Workspace/projects/omo \
  python -m omo.resident.cli ingest
