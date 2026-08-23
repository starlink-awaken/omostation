#!/bin/bash
# Record one governed cron command result under the selected Workspace runtime root.

set -u

usage() {
  echo "usage: heartbeat-wrapper.sh <job-name> <command> [args...]" >&2
}

if [ "$#" -lt 2 ]; then
  usage
  exit 64
fi

job_name="$1"
shift

if [[ ! "$job_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]; then
  echo "heartbeat-wrapper: invalid job name" >&2
  exit 64
fi

workspace_root="${OMO_WORKSPACE_ROOT:-}"
if [ -z "$workspace_root" ]; then
  workspace_root="$(pwd -P)"
fi
case "$workspace_root" in
  /*) ;;
  *)
    echo "heartbeat-wrapper: OMO_WORKSPACE_ROOT must be absolute" >&2
    exit 64
    ;;
esac
if [ ! -d "$workspace_root/.omo" ]; then
  echo "heartbeat-wrapper: workspace root has no .omo directory" >&2
  exit 66
fi

heartbeat_dir="$workspace_root/.omo/state/heartbeats"
if ! mkdir -p -- "$heartbeat_dir"; then
  echo "heartbeat-wrapper: cannot create heartbeat directory" >&2
  exit 73
fi

started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
"$@"
command_exit=$?
finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

temporary_file="$(mktemp "$heartbeat_dir/.${job_name}.XXXXXX")" || {
  echo "heartbeat-wrapper: cannot allocate atomic heartbeat file" >&2
  if [ "$command_exit" -ne 0 ]; then
    exit "$command_exit"
  fi
  exit 73
}
cleanup_temporary_file() {
  rm -f -- "$temporary_file"
}
trap cleanup_temporary_file EXIT HUP INT TERM

if ! python3 -c '
import json
import os
import sys

output_path, job, started_at, finished_at, exit_code_text = sys.argv[1:]
exit_code = int(exit_code_text)
payload = {
    "job": job,
    "started_at": started_at,
    "last_run": finished_at,
    "exit_code": exit_code,
    "ok": exit_code == 0,
}
with open(output_path, "w", encoding="utf-8") as stream:
    json.dump(payload, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
    stream.flush()
    os.fsync(stream.fileno())
' "$temporary_file" "$job_name" "$started_at" "$finished_at" "$command_exit"; then
  echo "heartbeat-wrapper: cannot serialize heartbeat" >&2
  if [ "$command_exit" -ne 0 ]; then
    exit "$command_exit"
  fi
  exit 74
fi

if ! mv -f -- "$temporary_file" "$heartbeat_dir/$job_name.json"; then
  echo "heartbeat-wrapper: cannot publish heartbeat atomically" >&2
  if [ "$command_exit" -ne 0 ]; then
    exit "$command_exit"
  fi
  exit 74
fi
trap - EXIT HUP INT TERM

exit "$command_exit"
