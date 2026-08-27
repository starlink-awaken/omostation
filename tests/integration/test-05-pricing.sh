#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "=== [05] Pricing Consistency ==="
# Check all three pricing configs exist
for p in projects/metaos/src/metaos/config/pricing_config.yaml; do
  if [ -f "$ROOT/$p" ]; then
    echo "  EXISTS: $p"
  else
    echo "  MISSING: $p"
    exit 1
  fi
done
echo "PASS"
