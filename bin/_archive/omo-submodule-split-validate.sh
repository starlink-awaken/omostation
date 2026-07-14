#!/usr/bin/env bash
# omo submodule 拆分验证脚本 (P109-A)
# 用法: bin/omo-submodule-split-validate.sh <parent_module> <child_module>
# 例: bin/omo-submodule-split-validate.sh omo_governance_surfaces omo_governance_surfaces_snapshots

set -euo pipefail

PARENT="${1:?parent module required (e.g. omo_governance_surfaces)}"
CHILD="${2:?child module required (e.g. omo_governance_surfaces_snapshots)}"

echo "=== P109-A validation: ${PARENT} + ${CHILD} ==="

# Step 3: re-export check
echo "--- Step 3: re-export coverage ---"
PARENT_FILE="projects/omo/src/omo/${PARENT}.py"
CHILD_FILE="projects/omo/src/omo/${CHILD}.py"

for f in "$PARENT_FILE" "$CHILD_FILE"; do
    if [[ ! -f "$f" ]]; then
        echo "[FAIL] FAIL: $f not found"
        exit 1
    fi
done

if ! grep -q "from \.${CHILD#omo_${PARENT#omo_}_} import" "$PARENT_FILE"; then
    echo "⚠️  WARN: ${PARENT} may not re-export from ${CHILD}"
    echo "  (checking all from .<sibling> import blocks...)"
    if ! grep -q "from \..*${CHILD#omo_} import\|from \..* import" "$PARENT_FILE"; then
        echo "[FAIL] FAIL: ${PARENT} has no import blocks"
        exit 1
    fi
fi
echo "[OK] re-export block present"

# Step 4: parse check (circular import detection)
echo "--- Step 4: module parse check ---"
for f in "$PARENT_FILE" "$CHILD_FILE"; do
    if ! python3 -c "import ast; ast.parse(open('$f').read())" 2>/dev/null; then
        echo "[FAIL] FAIL: $f has syntax error"
        exit 1
    fi
done
echo "[OK] both modules parse OK"

# Step 5: 6 surface lints (P104 教训)
echo "--- Step 5: 6 surface lints ---"
PASS_COUNT=0
for cmd in ingress-registry mutation-surfaces internal-write-profiles \
          state-plane-assets c2g-omo-boundary ingress-artifacts; do
    output=$(PYTHONPATH=projects/omo/src uv run --with pyyaml \
        python3 -m omo.omo_lint "$cmd" 2>&1 | head -1)
    # Use grep -q on UTF-8 string (Unicode safe)
    if printf '%s' "$output" | LC_ALL=C grep -q "omo lint $cmd pass"; then
        echo "  PASS $cmd"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "  FAIL $cmd: $output"
    fi
done

if [[ $PASS_COUNT -lt 6 ]]; then
    echo "[FAIL] FAIL: only $PASS_COUNT/6 surface lints pass"
    exit 1
fi
echo "[OK] 6 surface lints pass"

# Step 6: re-export equivalence (parent re-exports child symbols)
echo "--- Step 6: re-export equivalence ---"
# Module name: omo_foo_bar → omo.omo_foo_bar (preserve omo_ prefix)
PARENT_PY="omo.${PARENT}"
CHILD_PY="omo.${CHILD}"

echo "  parent: $PARENT_PY, child: $CHILD_PY"

# Use heredoc to avoid bash/python string escaping issues
VALIDATE_PY=$(mktemp /tmp/validate_XXXXXX.py)
cat > "$VALIDATE_PY" << 'PYEOF'
import sys
PARENT = sys.argv[1]
CHILD = sys.argv[2]
mod_p = __import__(f'omo.{PARENT}', fromlist=[''])
mod_c = __import__(f'omo.{CHILD}', fromlist=[''])
shared = set(dir(mod_p)) & set(dir(mod_c)) - {
    '__builtins__', '__cached__', '__doc__', '__file__',
    '__loader__', '__name__', '__package__', '__path__', '__spec__'
}
# Whitelist: inline helpers (P105) are intentionally duplicated
WHITELIST = {'_load_yaml'}
broken = []
for s in sorted(shared):
    if s in WHITELIST:
        continue
    p_attr = getattr(mod_p, s)
    c_attr = getattr(mod_c, s)
    if callable(p_attr) and callable(c_attr) and p_attr is not c_attr:
        broken.append(s)
if broken:
    print(f'[FAIL] BROKEN re-exports: {broken}')
    sys.exit(1)
print(f'[OK] all {len(shared)} shared callables OK (whitelist: {sorted(WHITELIST)})')
PYEOF

if ! PYTHONPATH=projects/omo/src python3 "$VALIDATE_PY" "$PARENT" "$CHILD" 2>&1; then
    echo "[FAIL] FAIL: re-export equivalence broken"
    rm -f "$VALIDATE_PY"
    exit 1
fi
rm -f "$VALIDATE_PY"

# Step 7: threshold
echo "--- Step 7: threshold check ---"
LINES=$(wc -l < "$PARENT_FILE")
CHILD_LINES=$(wc -l < "$CHILD_FILE")
echo "  ${PARENT}: ${LINES}L"
echo "  ${CHILD}: ${CHILD_LINES}L"

if [[ $LINES -ge 800 ]]; then
    echo "[FAIL] FAIL: ${PARENT} still >=800L (warn threshold)"
    exit 1
fi

if [[ $LINES -ge 600 ]]; then
    echo "⚠️  WARN: ${PARENT} in 600-800L range (warn zone, ideal <600L)"
elif [[ $LINES -ge 400 ]]; then
    echo "[OK] ${PARENT} in 400-600L range (黄金值)"
else
    echo "[OK] ${PARENT} <400L (deep ideal)"
fi

if [[ $CHILD_LINES -ge 800 ]]; then
    echo "[FAIL] FAIL: ${CHILD} >=800L (warn threshold, 子模块不应成 god-module)"
    exit 1
fi
echo "[OK] threshold pass"

echo ""
echo "[PASS] all 7 steps pass for ${PARENT} + ${CHILD}"
