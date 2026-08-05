#!/usr/bin/env bash
# Seed bi-temporal demo facts for Memory OS as_of comparison (ADR-0372 Phase 10).
# Usage: bash bin/memory-os-asof-seed.sh [--json]
# Requires: source bin/memory-os-env.sh (optional Neo4j; FileStore+TemporalShadow still work)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
cd "$ROOT"

# Save argv before sourcing env (env.sh reads $@ for --export/--check)
_ASOF_ARGV=("$@")
set --
if [[ -f "$ROOT/bin/memory-os-env.sh" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/bin/memory-os-env.sh" || true
fi
set -- "${_ASOF_ARGV[@]+"${_ASOF_ARGV[@]}"}"

COCKPIT=(uv run --project projects/cockpit cockpit)
JSON_FLAG=()
if [[ "${1:-}" == "--json" ]]; then
  JSON_FLAG=(--json)
fi

SUBJECT="${MOS_ASOF_SUBJECT:-AliceDemo}"
echo "=== memory-os-asof-seed subject=${SUBJECT} ==="
echo "NEO4J_URI=${NEO4J_URI:-<unset>}"

# Past employment (world-valid 2019–2021)
"${COCKPIT[@]}" memory write \
  --type semantic \
  --content "${SUBJECT} works_at OldCo (valid 2019-2021)" \
  --subject "$SUBJECT" \
  --predicate works_at \
  --object OldCo \
  --confidence 0.95 \
  --valid-from 2019-01-01T00:00:00Z \
  --valid-to 2021-01-01T00:00:00Z \
  "${JSON_FLAG[@]}" || true

# Current employment (world-valid 2021–)
"${COCKPIT[@]}" memory write \
  --type semantic \
  --content "${SUBJECT} works_at NewCo (valid 2021-present)" \
  --subject "$SUBJECT" \
  --predicate works_at \
  --object NewCo \
  --confidence 0.95 \
  --valid-from 2021-01-01T00:00:00Z \
  "${JSON_FLAG[@]}" || true

echo ""
echo "=== as_of comparison (expect different employers) ==="
echo "--- as_of 2020-06-01 (expect OldCo) ---"
"${COCKPIT[@]}" memory recall "$SUBJECT" --intent temporal_fact \
  --as-of 2020-06-01T00:00:00Z --limit 10 --json || true

echo ""
echo "--- as_of 2023-01-01 (expect NewCo) ---"
"${COCKPIT[@]}" memory recall "$SUBJECT" --intent temporal_fact \
  --as-of 2023-01-01T00:00:00Z --limit 10 --json || true

echo ""
echo "--- current (no as_of; expect NewCo / non-invalidated) ---"
"${COCKPIT[@]}" memory recall "$SUBJECT" --intent temporal_fact --limit 10 --json || true

echo ""
echo "=== seed complete ==="
echo "Doc: docs/operations/memory-os-neo4j-local.md § as_of 对照"
echo "Ops:  .omo/standards/memory-os-ops.md Phase 10"
exit 0
