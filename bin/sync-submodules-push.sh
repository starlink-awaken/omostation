#!/usr/bin/env bash
# Compatibility wrapper — SSOT lives at bin/ssot/sync-submodules-push.sh
# (bin rationalization). pre-push and older docs may call this path.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/bin/ssot/sync-submodules-push.sh" "$@"
