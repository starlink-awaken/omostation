#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/3] Syncing .omo state"
python3 scripts/sync_omo_state.py --omo-dir .omo

echo "[2/3] Validating active tasks"
python3 scripts/omo_worker.py task validate --all-active

echo "[3/3] Running .omo regression tests"
python3 -m pytest .omo/tests -q
