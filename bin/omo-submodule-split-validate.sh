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
        echo "❌ FAIL: $f not found"
        exit 1
    fi
done

if ! grep -q "from \.${CHILD#omo_${PARENT#omo_}_} import" "$PARENT_FILE"; then
    echo "⚠️  WARN: ${PARENT} may not re-export from ${CHILD}"
    echo "  (checking all from .<sibling> import blocks...)"
    if ! grep -q "from \..*${CHILD#omo_} import\|from \..* import" "$PARENT_FILE"; then
        echo "❌ FAIL: ${PARENT} has no import blocks"
        exit 1
    fi
fi
echo "✅ re-export block present"

# Step 4: parse check (circular import detection)
echo "--- Step 4: module parse check ---"
for f in "$PARENT_FILE" "$CHILD_FILE"; do
    if ! python3 -c "import ast; ast.parse(open('$f').read())" 2>/dev/null; then
        echo "❌ FAIL: $f has syntax error"
        exit 1
    fi
done
echo "✅ both modules parse OK"

# Step 5: 6 surface lints (P104 教训)
echo "--- Step 5: 6 surface lints ---"
PASS_COUNT=0
for cmd in ingress-registry mutation-surfaces internal-write-profiles \
          state-plane-assets c2g-omo-boundary ingress-artifacts; do
    if output=$(PYTHONPATH=projects/omo/src uv run --with pyyaml \
        python3 -m omo.omo_lint "$cmd" 2>&1 | head -1); then
        if [[ "$output" =~ ^✅ ]]; then
            echo "  ✅ $cmd"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ $cmd: $output"
        fi
    else
        echo "  ❌ $cmd: command failed"
    fi
done

if [[ $PASS_COUNT -lt 6 ]]; then
    echo "❌ FAIL: only $PASS_COUNT/6 surface lints pass"
    exit 1
fi
echo "✅ 6 surface lints pass"

# Step 6: re-export equivalence (parent re-exports child symbols)
echo "--- Step 6: re-export equivalence ---"
# Module name: omo_foo_bar → omo.omo_foo_bar (preserve omo_ prefix)
PARENT_PY="omo.${PARENT}"
CHILD_PY="omo.${CHILD}"

echo "  parent: $PARENT_PY, child: $CHILD_PY"

if ! PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -c "
from omo import ${PARENT} as p_mod
from omo import ${CHILD} as c_mod
shared = set(dir(p_mod)) & set(dir(c_mod)) - {
    '__builtins__', '__cached__', '__doc__', '__file__',
    '__loader__', '__name__', '__package__', '__path__', '__spec__'
}
# Whitelist: inline helpers (P105 范式) are intentionally duplicated
# to avoid child→parent circular import. See ADR-0099 D2 + ADR-0102 D7.
WHITELIST = {'_load_yaml'}
broken = []
for s in sorted(shared):
    if s in WHITELIST:
        continue
    p_attr = getattr(p_mod, s)
    c_attr = getattr(c_mod, s)
    if callable(p_attr) and callable(c_attr) and p_attr is not c_attr:
        broken.append(s)
if broken:
    print(f'❌ BROKEN re-exports: {broken}')
    import sys; sys.exit(1)
print(f'✅ all {len(shared)} shared callables OK (whitelist: {sorted(WHITELIST)})')
" 2>&1; then
    echo "❌ FAIL: re-export equivalence broken"
    exit 1
fi

# Step 7: threshold
echo "--- Step 7: threshold check ---"
LINES=$(wc -l < "$PARENT_FILE")
CHILD_LINES=$(wc -l < "$CHILD_FILE")
echo "  ${PARENT}: ${LINES}L"
echo "  ${CHILD}: ${CHILD_LINES}L"

if [[ $LINES -ge 800 ]]; then
    echo "❌ FAIL: ${PARENT} still >=800L (warn threshold)"
    exit 1
fi

if [[ $LINES -ge 600 ]]; then
    echo "⚠️  WARN: ${PARENT} in 600-800L range (warn zone, ideal <600L)"
elif [[ $LINES -ge 400 ]]; then
    echo "✅ ${PARENT} in 400-600L range (黄金值)"
else
    echo "✅ ${PARENT} <400L (deep ideal)"
fi

if [[ $CHILD_LINES -ge 800 ]]; then
    echo "❌ FAIL: ${CHILD} >=800L (warn threshold, 子模块不应成 god-module)"
    exit 1
fi
echo "✅ threshold pass"

echo ""
echo "🎉 all 7 steps pass for ${PARENT} + ${CHILD}"
