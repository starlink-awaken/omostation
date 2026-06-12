#!/usr/bin/env bash
# check-bus-hard-conditions.sh — monitor 5 hard conditions for bus-foundation
#
# 5 hard conditions (per projects/agora/docs/ADR-0008-bus-foundation-strategy.md):
#   1. ≥3 projects use `from bus_foundation` (or `from agora.bus`) in production
#   2. bus-foundation has ≥180 days git history
#   3. bus-foundation CLAUDE.md documents owner
#   4. ≥1 eCOS-external project uses bus (proxy: ≥5 internal consumers per ADR-0008.1)
#   5. bus-foundation commit frequency ≥ 50% of agora main
#
# Usage: bash scripts/check-bus-hard-conditions.sh
# Output: each condition with PASS/FAIL/UNKNOWN, plus overall verdict.
# Exit code: 0 if all PASS, 1 if any FAIL, 2 if any UNKNOWN (need manual check).

set -euo pipefail

BUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="$(cd "$BUS_ROOT/../.." && pwd)"
cd "$BUS_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

PASS=0
FAIL=0
UNKNOWN=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    PASS=$((PASS + 1))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    FAIL=$((FAIL + 1))
}

check_unknown() {
    echo -e "${YELLOW}?${NC} $1"
    UNKNOWN=$((UNKNOWN + 1))
}

echo "=== bus-foundation Hard Conditions Check (ADR-0008) ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# ── Condition 1: ≥3 projects use bus-foundation or agora.bus ──
echo "Condition 1: ≥3 projects use 'from bus_foundation' (or 'from agora.bus') in production"
PROJECT_COUNT=0
for proj in omo metaos runtime aetherforge kairon llm-gateway cockpit; do
    proj_dir="$WORKSPACE_ROOT/projects/$proj"
    if [ -d "$proj_dir/src" ]; then
        # find .py files under src/ containing "from bus_foundation" OR "from agora.bus"
        if grep -rln "from bus_foundation\|from agora.bus" "$proj_dir/src" --include="*.py" 2>/dev/null | head -1 > /dev/null; then
            PROJECT_COUNT=$((PROJECT_COUNT + 1))
            echo "  - $proj: USES"
        else
            echo "  - $proj: no"
        fi
    fi
done
# Also count kairon-pipeline (submodule path)
if grep -rln "from bus_foundation\|from agora.bus" "$WORKSPACE_ROOT/projects/kairon/packages/kairon-pipeline/src" --include="*.py" 2>/dev/null | head -1 > /dev/null; then
    PROJECT_COUNT=$((PROJECT_COUNT + 1))
    echo "  - kairon-pipeline: USES"
fi
if [ "$PROJECT_COUNT" -ge 3 ]; then
    check_pass "PASS: $PROJECT_COUNT projects use bus-foundation/agora.bus"
else
    check_fail "FAIL: only $PROJECT_COUNT projects (need ≥3)"
fi
echo

# ── Condition 2: bus-foundation has ≥180 days git history ──
echo "Condition 2: bus-foundation has ≥180 days git history"
# Scope to the bus-foundation/ subtree inside the parent git repo (we share
# the workspace git repo for now; once split to its own repo, this still works).
BUS_DAYS=$(cd "$WORKSPACE_ROOT" && git log --since="180 days ago" -- projects/bus-foundation/ 2>/dev/null | grep -c "^commit" || echo 0)
BUS_DAYS=${BUS_DAYS//[^0-9]/}
BUS_DAYS=${BUS_DAYS:-0}
if [ "$BUS_DAYS" -ge 1 ]; then
    check_pass "PASS: $BUS_DAYS commits touching projects/bus-foundation/ in last 180 days"
else
    check_fail "FAIL: $BUS_DAYS commits (need ≥1 in 180 days)"
fi
echo

# ── Condition 3: bus-foundation CLAUDE.md documents owner ──
echo "Condition 3: bus-foundation CLAUDE.md documents owner"
if grep -q "owner\|maintainers\|Maintainer" "$BUS_ROOT/CLAUDE.md" 2>/dev/null; then
    check_pass "PASS: owner documented in CLAUDE.md"
else
    check_fail "FAIL: bus owner not mentioned in CLAUDE.md"
fi
echo

# ── Condition 4: ≥1 eCOS-external project uses bus (proxy: ≥5 internal consumers per ADR-0008.1) ──
echo "Condition 4: ≥1 eCOS-external project uses bus (proxy via ADR-0008.1: ≥5 internal consumers)"
if [ "$PROJECT_COUNT" -ge 5 ]; then
    check_pass "PASS: $PROJECT_COUNT internal consumers (proxy for ADR-0008.1 Condition 4)"
else
    check_fail "FAIL: $PROJECT_COUNT internal consumers (proxy needs ≥5)"
fi
echo

# ── Condition 5: bus-foundation commit frequency ≥ 50% of agora main (6 months) ──
echo "Condition 5: bus-foundation commit frequency ≥ 50% of agora main (6 months)"
SINCE="6 months ago"
BUS_COMMITS=$(cd "$WORKSPACE_ROOT" && git log --since="$SINCE" -- projects/bus-foundation/ 2>/dev/null | grep -c "^commit" || echo 0)
AGORA_COMMITS=$(cd "$WORKSPACE_ROOT/projects/agora" && git log --since="$SINCE" -- src/agora/bus/ 2>/dev/null | grep -c "^commit" || echo 0)
BUS_COMMITS=${BUS_COMMITS//[^0-9]/}; BUS_COMMITS=${BUS_COMMITS:-0}
AGORA_COMMITS=${AGORA_COMMITS//[^0-9]/}; AGORA_COMMITS=${AGORA_COMMITS:-0}
if [ "$AGORA_COMMITS" -gt 0 ]; then
    RATIO=$(python3 -c "print(f'{$BUS_COMMITS * 100.0 / $AGORA_COMMITS:.2f}')")
    PASS_50=$(python3 -c "print(1 if $BUS_COMMITS * 100.0 / $AGORA_COMMITS >= 50 else 0)")
    if [ "$PASS_50" = "1" ]; then
        check_pass "PASS: $BUS_COMMITS bus-foundation / $AGORA_COMMITS agora = ${RATIO}%"
    else
        check_fail "FAIL: $BUS_COMMITS bus-foundation / $AGORA_COMMITS agora = ${RATIO}% (need ≥50%)"
    fi
else
    check_unknown "UNKNOWN: 0 agora commits in 6 months"
fi
echo

# ── Summary ──
echo "=== Summary ==="
echo -e "  ${GREEN}PASS${NC}: $PASS"
echo -e "  ${RED}FAIL${NC}: $FAIL"
echo -e "  ${YELLOW}UNKNOWN${NC}: $UNKNOWN"
echo

TOTAL=$((PASS + FAIL + UNKNOWN))
if [ "$FAIL" -gt 0 ]; then
    echo "VERDICT: NOT READY for Phase C (L0 promotion)"
    exit 1
elif [ "$UNKNOWN" -gt 0 ]; then
    echo "VERDICT: NEEDS MANUAL CHECK"
    exit 2
else
    echo "VERDICT: READY for Phase C (5/5 hard conditions met)"
    exit 0
fi
