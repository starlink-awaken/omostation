#!/bin/bash
# Run only the exact notification decision block; never probe or mount volumes.
# Usage: bash tests/bin/test_disk_keepalive_notify.sh [source-script]
set -euo pipefail
SOURCE="${1:-$(cd "$(dirname "$0")/../.." && pwd)/bin/ops/disk-keepalive.sh}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir "$TMP/fake-bin" "$TMP/state"
awk '
  /^ESCALATE_AFTER=|^NOTIFY_EVERY=|^NOTIFY_INTERVAL_S=|^log\(\)/ { print }
  /^if \[ "\$ALL_OK" = "1" \]; then$/ { body=1 }
  /^# 真实掉线采集放在最后:/ { body=0; ended=1 }
  body { print }
  END { if (!ended) exit 1 }
' "$SOURCE" > "$TMP/decision.sh"
cat > "$TMP/fake-bin/date" <<'EOF'
#!/bin/bash
[ "$1" = '+%s' ] || exit 90
printf '%s\n' "$FAKE_NOW"
EOF
cat > "$TMP/fake-bin/osascript" <<'EOF'
#!/bin/bash
printf '%s\n' "$FAKE_NOW" >> "$ATTEMPTS"
exit "${NOTIFY_EXIT:-0}"
EOF
chmod +x "$TMP/fake-bin/date" "$TMP/fake-bin/osascript"
export PATH="$TMP/fake-bin:$PATH"
export STATE="$TMP/state/count" NEEDS_ATTENTION="$TMP/state/attention"
export NOTIFIED_AT="$TMP/state/notified" LOG="$TMP/state/log"
export ATTEMPTS="$TMP/state/attempts" TS='fixture'
FAILURES=0
ASSERTIONS=0
check() {
    ASSERTIONS=$((ASSERTIONS + 1))
    if [ "$2" != "$3" ]; then
        echo "FAIL: $1 (expected=$3 actual=$2)"
        FAILURES=$((FAILURES + 1))
    fi
}
value() { cat "$1" 2>/dev/null || true; }
attempts() { if [ -f "$ATTEMPTS" ]; then wc -l < "$ATTEMPTS" | tr -d ' '; else echo 0; fi; }
step() {
    local healthy="$1" count="$2" now="$3" result="${4:-0}"
    ALL_OK="$healthy" FAIL_COUNT="$count" FAKE_NOW="$now" NOTIFY_EXIT="$result" \
        /bin/bash -u "$TMP/decision.sh"
}

step 0 8 1800000000
check 'count 9 does not notify' "$(attempts)" 0
check 'count 9 is retained' "$(value "$STATE")" 9
step 0 9 1800000000
check 'count 10 first attempt' "$(attempts)" 1
check 'first success records epoch' "$(value "$NOTIFIED_AT")" 1800000000
check 'count 10 escalates' "$(test -f "$NEEDS_ATTENTION" && echo yes)" yes
step 0 9999 1800003599
check '3599 seconds suppresses regardless of count' "$(attempts)" 1
step 0 10000 1800003600
check '3600 seconds permits' "$(attempts)" 2
check 'second success records epoch' "$(value "$NOTIFIED_AT")" 1800003600
step 1 10001 1800003700
check 'recovery resets count' "$(value "$STATE")" 0
check 'recovery clears attention' "$(test ! -f "$NEEDS_ATTENTION" && echo yes)" yes
check 'recovery preserves successful epoch' "$(value "$NOTIFIED_AT")" 1800003600
step 0 9 1800007199
check 'new event under one hour stays suppressed' "$(attempts)" 2
step 0 10 1800007200 1
check 'eligible failed attempt runs' "$(attempts)" 3
check 'failure preserves previous successful epoch' "$(value "$NOTIFIED_AT")" 1800003600
step 0 11 1800007200
check 'failure retries at same epoch on next invocation' "$(attempts)" 4
check 'retry success records epoch' "$(value "$NOTIFIED_AT")" 1800007200

rm -f "$NOTIFIED_AT"
step 0 9 1800010800 1
check 'first failed attempt leaves stamp absent' "$(test ! -f "$NOTIFIED_AT" && echo yes)" yes
step 0 10 1800010800
check 'first failure remains retryable' "$(attempts)" 6
echo 30 > "$NOTIFIED_AT"
step 0 31 1800010801 1
check 'legacy count permits first current attempt' "$(attempts)" 7
check 'failed migration does not forge epoch' "$(value "$NOTIFIED_AT")" 30
step 0 32 1800010801
check 'legacy retry permits success' "$(attempts)" 8
check 'legacy count replaced only after success' "$(value "$NOTIFIED_AT")" 1800010801
echo "assertions=$ASSERTIONS failures=$FAILURES"
[ "$FAILURES" -eq 0 ]
