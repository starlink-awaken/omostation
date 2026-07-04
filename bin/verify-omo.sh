#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] Syncing .omo state"
python3 scripts/sync_omo_state.py --omo-dir .omo

echo "[2/5] Running governance lint gates"
pushd projects/omo >/dev/null
uv sync --quiet   # 显式 sync (确保 pydantic 等依赖装好, 避免 CI uv 缓存致 import fail)
uv run python -m omo.cli lint direct-omo-io
uv run python -m omo.cli lint sensitive-governed-writes
uv run python -m omo.cli lint ingress-registry --workspace-root ../..
uv run python -m omo.cli lint mutation-surfaces --workspace-root ../..
uv run python -m omo.cli lint internal-write-profiles --workspace-root ../..
uv run python -m omo.cli lint state-plane-assets --workspace-root ../..
uv run python -m omo.cli lint c2g-omo-boundary --workspace-root ../..
uv run python -m omo.cli lint ingress-artifacts --workspace-root ../..
uv run python -m omo.cli lint mutation-ledger --workspace-root ../..
uv run python -m omo.cli lint task-policy --all --workspace-root ../..
popd >/dev/null

echo "[3/5] Validating active and planned tasks"
PYTHONPATH=projects/omo/src python3 -m omo.omo_worker task validate --all-active
PYTHONPATH=projects/omo/src python3 -m omo.omo_worker task validate --all-planned

echo "[4/5] Running governance regression tests"
pushd projects/omo >/dev/null
uv run pytest \
  tests/test_omo_ingress.py \
  tests/test_omo_cockpit_bridge.py \
  tests/test_omo_gc.py \
  tests/test_omo_governance.py \
  tests/test_omo_governance_surfaces.py \
  tests/test_omo_direct_io_gate.py \
  tests/test_omo_task_policy.py \
  tests/test_opc_phase_governance_alignment.py \
  tests/test_opc_p5_p7_runtime.py \
  -q
popd >/dev/null

echo "[5/5] Running legacy .omo regression tests"
python3 -m pytest .omo/tests -q
