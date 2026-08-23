#!/bin/bash
# heartbeat-wrapper.sh — cron job 心跳包装器 (ADR-D)
# 用法: bash bin/gac/heartbeat-wrapper.sh <job_name> <command...>
# 效果: 运行 command 后在 .omo/state/heartbeats/<job_name>.json 写心跳

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
