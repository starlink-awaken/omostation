#!/bin/bash
# TaskObject CLI — dispatches a TaskObject envelope to Runtime MCP tools
# Usage: taskobject.sh '{"target":{"tool":"runtime_health","params":{}}}'
set -e
# Resolve symlink to find the real project root
SCRIPT="$0"
while [ -L "$SCRIPT" ]; do
  SCRIPT="$(readlink "$SCRIPT")"
done
cd "$(dirname "$SCRIPT")/.."
PAYLOAD="$1"
if [ -z "$PAYLOAD" ]; then
  echo '{"error":"Missing JSON payload","usage":"taskobject.sh ..."}'
  exit 1
fi
PYTHONPATH=src python3 -c "
import sys, json
from runtime.taskobject_adapter import dispatch_taskobject
payload = json.loads(sys.argv[1])
result = dispatch_taskobject(payload)
print(json.dumps(result, ensure_ascii=False))
" "$PAYLOAD"
