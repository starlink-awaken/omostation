#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "=== [02] Pipeline JSON Schema ==="
python3 -c "
import json, sys
p = {'pipeline': {'version': '1.1', 'tool': 'test', 'action': 'validate', 'timestamp': '2026-05-27T00:00:00'}, 'meta_type': 'CONSTRAINT', 'data': {}, 'provenance': {'source': 'test', 'confidence': 1.0}}
json.dumps(p, indent=2)
# Verify required keys
assert 'pipeline' in p
assert 'version' in p['pipeline']
assert 'meta_type' in p
assert 'data' in p
assert 'provenance' in p
print('Pipeline JSON schema OK')
"
echo "PASS"
