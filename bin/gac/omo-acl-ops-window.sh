#!/usr/bin/env bash
# omo-acl-ops-window.sh — guided Scheme C 5c host ACL ops window (ADR-0206)
#
# Default: READ-ONLY (lint path-acl + plan + plan --acl). Never mutates host.
# Apply: dual-gate — OMO_OS_ACL=1 (already in env) AND --yes AND --apply.
# This script does NOT export OMO_OS_ACL (prevents CI/agent accidents).
#
# Usage:
#   bash bin/gac/omo-acl-ops-window.sh
#   bash bin/gac/omo-acl-ops-window.sh --json
#   bash bin/gac/omo-acl-ops-window.sh --probe-macos
#   export OMO_OS_ACL=1
#   bash bin/gac/omo-acl-ops-window.sh --apply --yes          # chmod plan only
#   bash bin/gac/omo-acl-ops-window.sh --apply --yes --acl    # chmod + named ACE
#
set -euo pipefail

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

JSON=0
APPLY=0
YES=0
WITH_ACL=0
PROBE_MACOS=0
WS_ROOT="$ROOT"

usage() {
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

for a in "$@"; do
  case "$a" in
    --json) JSON=1 ;;
    --apply) APPLY=1 ;;
    --yes) YES=1 ;;
    --acl) WITH_ACL=1 ;;
    --probe-macos) PROBE_MACOS=1 ;;
    -h|--help) usage ;;
    --workspace-root=*) WS_ROOT="${a#*=}" ;;
    *)
      echo "unknown arg: $a (try --help)" >&2
      exit 2
      ;;
  esac
done

omo_cli() {
  if [ -d "$ROOT/projects/omo/src/omo" ]; then
    PYTHONPATH="$ROOT/projects/omo/src${PYTHONPATH:+:$PYTHONPATH}" \
      python3 -m omo.cli "$@"
    return $?
  fi
  if command -v uv >/dev/null 2>&1; then
    uv run --project "$ROOT/projects/omo" python -m omo.cli "$@"
    return $?
  fi
  echo "❌ cannot run omo.cli (missing projects/omo/src)" >&2
  return 127
}

summarize_lint() {
  python3 -c '
import json, sys
d = json.load(sys.stdin)
print("ok=%s warn=%s halt=%s" % (d.get("ok"), d.get("warn_count"), d.get("halt_count")))
for f in d.get("findings") or []:
    if f.get("severity") in ("info",):
        continue
    print("  [%s] %s: %s" % (f.get("severity"), f.get("surface"), f.get("detail")))
'
}

summarize_plan() {
  python3 -c '
import json, sys
d = json.load(sys.stdin)
print("actions=%s omo_os_acl=%s" % (d.get("action_count"), d.get("omo_os_acl_enabled")))
'
}

summarize_named() {
  python3 -c '
import json, sys
d = json.load(sys.stdin)
na = d.get("named_acl") or {}
print("platform=%s setfacl=%s commands=%s" % (
    na.get("platform"), na.get("setfacl_available"), na.get("command_count")))
for c in (na.get("commands") or [])[:8]:
    print("  - %s %s (%s)" % (c.get("op"), c.get("path"), c.get("subject")))
n = na.get("command_count") or 0
if n > 8:
    print("  ...")
'
}

echo "=== omo-acl-ops-window (ADR-0206) ==="
echo "workspace: $WS_ROOT"
echo "mode: $([ "$APPLY" = 1 ] && echo APPLY || echo DRY-RUN)"
echo "OMO_OS_ACL=${OMO_OS_ACL:-<unset>}"
echo "platform: $(uname -s)/$(uname -m)"
if command -v setfacl >/dev/null 2>&1; then
  echo "setfacl: $(command -v setfacl)"
else
  echo "setfacl: missing (ok on macOS)"
fi

if [ "$PROBE_MACOS" = 1 ]; then
  if [ "$(uname -s)" != "Darwin" ]; then
    echo "probe-macos: skip (not Darwin)"
  else
    tmp=$(mktemp -d /tmp/omo-acl-probe.XXXX)
    echo probe >"$tmp/f"
    user=$(id -un)
    if chmod +a "$user allow read,write,execute" "$tmp/f" 2>/dev/null; then
      echo "probe-macos: chmod +a OK for user=$user"
      ls -le "$tmp/f" 2>/dev/null | head -5 || true
    else
      echo "probe-macos: chmod +a FAILED" >&2
    fi
    rm -rf "$tmp"
  fi
fi

echo ""
echo "--- lint path-acl ---"
LINT_JSON=$(omo_cli lint path-acl --workspace-root "$WS_ROOT" --json)
if [ "$JSON" = 1 ]; then
  printf '%s\n' "$LINT_JSON"
else
  printf '%s\n' "$LINT_JSON" | summarize_lint
fi

echo ""
echo "--- acl plan ---"
PLAN_JSON=$(omo_cli acl plan --workspace-root "$WS_ROOT" --json)
if [ "$JSON" = 1 ]; then
  printf '%s\n' "$PLAN_JSON"
else
  printf '%s\n' "$PLAN_JSON" | summarize_plan
fi

echo ""
echo "--- acl plan --acl (named ACE dry-run) ---"
PLAN_ACL_JSON=$(omo_cli acl plan --acl --workspace-root "$WS_ROOT" --json)
if [ "$JSON" = 1 ]; then
  printf '%s\n' "$PLAN_ACL_JSON"
else
  printf '%s\n' "$PLAN_ACL_JSON" | summarize_named
fi

if [ "$APPLY" != 1 ]; then
  cat <<EOF

✅ dry-run complete (no host mutation).
To apply after review:
  export OMO_OS_ACL=1
  bash bin/gac/omo-acl-ops-window.sh --apply --yes          # chmod plan
  bash bin/gac/omo-acl-ops-window.sh --apply --yes --acl    # + named ACE
EOF
  exit 0
fi

if [ "${OMO_OS_ACL:-}" != "1" ]; then
  cat >&2 <<EOF
❌ apply refused: OMO_OS_ACL is not 1
   This script will not set it for you.
   export OMO_OS_ACL=1   # then re-run with --apply --yes [--acl]
EOF
  exit 3
fi
if [ "$YES" != 1 ]; then
  echo "❌ apply refused: pass --yes after reviewing dry-run plan" >&2
  exit 4
fi

echo ""
echo "--- APPLY (host mutation) ---"
if [ "$WITH_ACL" = 1 ]; then
  echo "running: omo acl apply --yes --acl"
  omo_cli acl apply --yes --acl --workspace-root "$WS_ROOT" --json
else
  echo "running: omo acl apply --yes"
  omo_cli acl apply --yes --workspace-root "$WS_ROOT" --json
fi

echo ""
echo "--- post-apply lint ---"
POST=$(omo_cli lint path-acl --workspace-root "$WS_ROOT" --json)
printf '%s\n' "$POST" | summarize_lint

echo "✅ ops window apply finished"
