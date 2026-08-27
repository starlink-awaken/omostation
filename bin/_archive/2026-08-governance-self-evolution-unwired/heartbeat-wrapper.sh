#!/bin/bash
# Archived unwired cron heartbeat prototype (ADR-D).
# Re-enable only after runtime-root parameterization, tests, governed wiring,
# and subtraction-quota evidence are supplied.

JOB_NAME="$1"; shift
HB_DIR="$HOME/Workspace/.omo/state/heartbeats"
mkdir -p "$HB_DIR"

START_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
"$@"
EXIT_CODE=$?
END_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

python3 -c "
import json, sys
hb = {
    'job': '$JOB_NAME',
    'last_run': '$END_TS',
    'exit_code': $EXIT_CODE,
    'ok': $EXIT_CODE == 0,
}
open('$HB_DIR/$JOB_NAME.json', 'w').write(json.dumps(hb, indent=2))
" 2>/dev/null || true

exit $EXIT_CODE
