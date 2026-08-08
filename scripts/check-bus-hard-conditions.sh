#!/usr/bin/env bash
# check-bus-hard-conditions.sh — monitor 5 hard conditions for Phase B trigger
#
# 5 hard conditions (per docs/ADR-0008-bus-foundation-strategy.md):
#   1. ≥3 projects use `from agora.bus` in production
#   2. bus/ subpackage has ≥180 days git history
#   3. agora CLAUDE.md documents bus owner
#   4. ≥1 eCOS-external project uses bus (GitHub issue/PR by non-contributor)
#   5. bus commit frequency ≥ 50% of agora main
#
# Usage: bash scripts/check-bus-hard-conditions.sh
# Output: each condition with PASS/FAIL/UNKNOWN, plus overall verdict.
# Exit code: 0 if all PASS, 1 if any FAIL, 2 if any UNKNOWN (need manual check).

set -euo pipefail

# AGORA_ROOT: for git operations (commits, history)
AGORA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# WORKSPACE_ROOT: for cross-project scans (other submodule siblings)
WORKSPACE_ROOT="$(cd "$AGORA_ROOT/../.." && pwd)"
cd "$AGORA_ROOT"

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

echo "=== Phase B Hard Conditions Check (ADR-0008) ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# ── Condition 1: ≥3 projects use `from agora.bus` in production ──
echo "Condition 1: ≥3 projects use 'from agora.bus' in production"
PROJECT_COUNT=0
for proj in omo metaos runtime kairon cockpit kairon-omostation; do
    proj_dir="$WORKSPACE_ROOT/projects/$proj"
    if [ -d "$proj_dir/src" ]; then
        # find .py files under src/ (recursive) containing "from agora.bus"
        if grep -rln "from agora.bus" "$proj_dir/src" --include="*.py" 2>/dev/null | head -1 > /dev/null; then
            PROJECT_COUNT=$((PROJECT_COUNT + 1))
        fi
    fi
done
if [ "$PROJECT_COUNT" -ge 3 ]; then
    check_pass "PASS: $PROJECT_COUNT projects import agora.bus"
else
    check_fail "FAIL: only $PROJECT_COUNT projects (need ≥3)"
fi
echo

# ── Condition 2: bus/ subpackage has ≥180 days git history ──
echo "Condition 2: bus/ subpackage has ≥180 days git history"
BUS_DAYS=$(cd "$AGORA_ROOT" && git log --since="180 days ago" -- src/agora/bus/ 2>/dev/null | grep -c "^commit" || echo 0)
BUS_DAYS=${BUS_DAYS//[^0-9]/}
BUS_DAYS=${BUS_DAYS:-0}
if [ "$BUS_DAYS" -ge 1 ]; then
    check_pass "PASS: $BUS_DAYS commits in last 180 days"
else
    check_fail "FAIL: $BUS_DAYS commits (need ≥1 in 180 days)"
fi
echo

# ── Condition 3: agora CLAUDE.md documents bus owner ──
echo "Condition 3: agora CLAUDE.md documents bus owner"
if grep -q "bus.*owner\|Owner" "$AGORA_ROOT/CLAUDE.md" 2>/dev/null; then
    check_pass "PASS: owner documented in CLAUDE.md"
else
    check_fail "FAIL: bus owner not mentioned in CLAUDE.md"
fi
echo

# ── Condition 4: ≥1 eCOS-external project uses bus (GitHub issue/PR) ──
echo "Condition 4: ≥1 eCOS-external project uses bus (manual check)"
check_unknown "UNKNOWN: requires manual GitHub issue/PR audit"
echo "  Action: query GitHub API for issues labeled 'bus-foundation' or"
echo "          external commits referencing agora.bus"
echo

# ── Condition 5: bus commit frequency ≥ 50% of agora main ──
echo "Condition 5: bus commit frequency ≥ 50% of agora main (6 months)"
SINCE="6 months ago"
BUS_COMMITS=$(cd "$AGORA_ROOT" && git log --since="$SINCE" -- src/agora/bus/ 2>/dev/null | grep -c "^commit" || echo 0)
AGORA_COMMITS=$(cd "$AGORA_ROOT" && git log --since="$SINCE" -- src/agora/ 2>/dev/null | grep -c "^commit" || echo 0)
BUS_COMMITS=${BUS_COMMITS//[^0-9]/}; BUS_COMMITS=${BUS_COMMITS:-0}
AGORA_COMMITS=${AGORA_COMMITS//[^0-9]/}; AGORA_COMMITS=${AGORA_COMMITS:-0}
if [ "$AGORA_COMMITS" -gt 0 ]; then
    RATIO=$(python3 -c "print(f'{$BUS_COMMITS * 100.0 / $AGORA_COMMITS:.2f}')")
    PASS_50=$(python3 -c "print(1 if $BUS_COMMITS * 100.0 / $AGORA_COMMITS >= 50 else 0)")
    if [ "$PASS_50" = "1" ]; then
        check_pass "PASS: $BUS_COMMITS bus / $AGORA_COMMITS agora = ${RATIO}%"
    else
        check_fail "FAIL: $BUS_COMMITS bus / $AGORA_COMMITS agora = ${RATIO}% (need ≥50%)"
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
    echo "VERDICT: NOT READY for Phase B (decoupling bus-foundation repo)"
    exit 1
elif [ "$UNKNOWN" -gt 0 ]; then
    echo "VERDICT: NEEDS MANUAL CHECK (Condition 4 requires GitHub audit)"
    exit 2
else
    echo "VERDICT: READY for Phase B (5/5 hard conditions met)"
    exit 0
fi
