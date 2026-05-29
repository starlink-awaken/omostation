#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "=== [01] A1 Identity Validation ==="
TMP=$(mktemp -d)
cat > "$TMP/identity.yaml" << 'EOF'
agent_identity:
  id: "io.github.test.agent"
  name: "Test Agent"
  role: "testing"
  version: "1.0.0"
  meta_type: "DOMAIN"
  sovereignty_level: CONDITIONAL
  capabilities:
    - id: "test-capability"
      description: "test capability"
EOF
python3 ~/.hermes/scripts/validate-A1-identity "$TMP/identity.yaml"
echo "PASS"
rm -rf "$TMP"
