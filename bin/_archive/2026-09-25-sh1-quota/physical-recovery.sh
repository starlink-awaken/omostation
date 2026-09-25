#!/usr/bin/env bash
# STRAT-P81 Batch2 C1 — one-shot physical recovery entry (default dry-run).
# Usage:
#   bash bin/delivery/physical-recovery.sh
#   PHYSICAL_RECOVERY_HOSTS=host1,host2 bash bin/delivery/physical-recovery.sh
#   bash bin/delivery/physical-recovery.sh --live   # still fail-closed without hosts
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
exec python3 "$ROOT/bin/delivery/physical_recovery.py" --dry-run "$@"
