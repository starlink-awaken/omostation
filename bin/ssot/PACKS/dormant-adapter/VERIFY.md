#!/usr/bin/env bash
# VERIFY: Dormant Adapter Detector Pack
#
# Run all checks; exit 0 on full pass, non-zero on any failure.
# Adapted from PAI Pack verification pattern.

set -euo pipefail

WS="/Users/xiamingxing/Workspace"
PACK="$WS/bin/ssot/PACKS/dormant-adapter"
ENTRY="$WS/bin/ssot/bus-usage-report.py"

echo "==> Verifying dormant-adapter Pack..."

# 1. Required files exist
echo "[1/4] File existence"
for f in SKILL.md INSTALL.md VERIFY.md src/dormant_adapter.py; do
  if [[ ! -f "$PACK/$f" ]]; then
    echo "  ❌ Missing: $PACK/$f"
    exit 1
  fi
  echo "  ✓ $f"
done

# 2. Entry point resolves through symlink to PACK
echo "[2/4] Entry point symlink"
if [[ ! -L "$ENTRY" ]]; then
  echo "  ❌ $ENTRY is not a symlink"
  exit 1
fi
TARGET=$(readlink "$ENTRY")
if [[ "$TARGET" != *"PACKS/dormant-adapter/src/dormant_adapter.py" ]]; then
  echo "  ❌ Symlink target wrong: $TARGET"
  exit 1
fi
echo "  ✓ $ENTRY -> $TARGET"

# 3. SKILL.md has required frontmatter
echo "[3/4] SKILL.md frontmatter"
FRONTMATTER=$(awk '/^---$/{c++; next} c==1' "$PACK/SKILL.md" || true)
for k in name version status triggers scope; do
  if ! grep -q "^$k:" <<< "$FRONTMATTER"; then
    echo "  ❌ Missing frontmatter key: $k"
    exit 1
  fi
done
echo "  ✓ All required frontmatter keys present"

# 4. Pack produces expected output
echo "[4/4] Runtime smoke test"
OUTPUT=$(python3 "$ENTRY" 2>&1 || true)
if ! echo "$OUTPUT" | grep -qE "active|dormant"; then
  echo "  ❌ Pack did not produce expected output"
  echo "  Output: $OUTPUT"
  exit 1
fi
if echo "$OUTPUT" | grep -qE "DORMANT"; then
  if [[ "${ALLOW_DORMANT:-0}" != "1" ]]; then
    echo "  ⚠️  Pack reports DORMANT consumers (set ALLOW_DORMANT=1 to allow)"
    echo "  Output:"
    echo "$OUTPUT" | sed 's/^/    /'
  fi
fi
echo "  ✓ Pack produced output"

echo
echo "✅ VERIFY: dormant-adapter PASS"
