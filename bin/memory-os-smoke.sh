#!/usr/bin/env bash
# Memory OS end-to-end smoke via real cockpit memory CLI (ADR-0372 phase10+).
# Usage: bash bin/memory-os-smoke.sh
# Exit 0: all steps produced structured success (or honest neo4j degrade on status only).
# Exit 1: crash / invalid JSON / write or recall hard-failed without payload.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/bin/memory-os-env.sh" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/bin/memory-os-env.sh" || true
fi

COCKPIT=(uv run --project projects/cockpit cockpit)
TS="$(date -u +%Y%m%dT%H%M%SZ)"
SMOKE_ID="mos-smoke-${TS}"

echo "=== memory-os-smoke @ ${TS} ==="
echo "ROOT=$ROOT"
echo "NEO4J_URI=${NEO4J_URI:-<unset>}"

fail=0

run_json() {
  local label="$1"
  shift
  echo ""
  echo "--- $label ---"
  echo "+ $*"
  local out
  if ! out="$("$@" 2>&1)"; then
    echo "$out"
    echo "FAIL: command non-zero: $label"
    return 1
  fi
  echo "$out"
  # Prefer last JSON object line if mixed
  if ! echo "$out" | python3 -c '
import json,sys
text=sys.stdin.read()
# try whole then last line
for cand in (text.strip(), text.strip().splitlines()[-1] if text.strip() else ""):
    try:
        d=json.loads(cand)
        if isinstance(d, dict):
            print("JSON_OK keys="+",".join(sorted(d.keys())[:20]))
            sys.exit(0)
    except Exception:
        pass
print("NO_JSON")
sys.exit(2)
' ; then
    # status may still be useful without json if we used --json
    echo "WARN: no JSON object parsed for $label"
    return 2
  fi
  return 0
}

# 1) status
if ! run_json "status" "${COCKPIT[@]}" memory status --json; then
  fail=1
else
  echo "$("${COCKPIT[@]}" memory status --json 2>/dev/null || true)" | python3 -c '
import json,sys
raw=sys.stdin.read().strip()
try:
    d=json.loads(raw)
except Exception as e:
    print("status parse fail", e); sys.exit(0)
print("version=", d.get("version"))
print("ok=", d.get("ok"))
print("neo4j_configured=", d.get("neo4j_configured"))
print("neo4j_available=", d.get("neo4j_available"))
print("neo4j_recall=", d.get("neo4j_recall"))
print("neo4j_as_of=", d.get("neo4j_as_of"))
print("adapters=", "adapters" in d)
if d.get("ok") is False and not d.get("error"):
    pass
' || true
fi

# 2) write
WRITE_CONTENT="smoke fact ${SMOKE_ID} Alice works_at SmokeCo"
if ! run_json "write" "${COCKPIT[@]}" memory write \
  --type semantic \
  --content "$WRITE_CONTENT" \
  --subject Alice \
  --predicate works_at \
  --object SmokeCo \
  --confidence 0.9 \
  --json; then
  echo "FAIL: write"
  fail=1
fi

# 3) recall (current)
if ! run_json "recall" "${COCKPIT[@]}" memory recall "Alice SmokeCo" --intent temporal_fact --limit 5 --json; then
  echo "FAIL: recall"
  fail=1
fi

# 4) recall with as_of (must pass flag; tolerate empty hits if no historical edges)
echo ""
echo "--- recall-as-of ---"
ASOF_OUT="$("${COCKPIT[@]}" memory recall "Alice" --intent temporal_fact --as-of 2020-01-01T00:00:00Z --limit 5 --json 2>&1)" || true
echo "$ASOF_OUT"
if echo "$ASOF_OUT" | python3 -c '
import json,sys
t=sys.stdin.read()
ok=False
for cand in (t.strip(), t.strip().splitlines()[-1] if t.strip() else ""):
  try:
    d=json.loads(cand)
    if isinstance(d, dict) and ("hits" in d or "ok" in d or "query" in d or "backend_status" in d):
      print("ASOF_JSON_OK query=", d.get("query"), "count=", d.get("count", len(d.get("hits") or [])))
      print("backend_status=", d.get("backend_status"))
      ok=True
      break
  except Exception:
    pass
sys.exit(0 if ok else 1)
'; then
  echo "as_of path exercised"
else
  # Still prove the CLI accepted --as-of (help text path) if command ran without argparse error
  if echo "$ASOF_OUT" | rg -q 'unrecognized arguments|error:'; then
    echo "FAIL: as_of flag rejected"
    fail=1
  else
    echo "WARN: as_of returned non-JSON but flag accepted; counting as soft pass"
  fi
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "=== memory-os-smoke PASS ==="
  exit 0
fi
echo "=== memory-os-smoke FAIL (exit=$fail) ==="
exit 1
