#!/usr/bin/env bash
# List (or remove) local worktrees whose commits are patch-equivalent on origin/main.
# Default: dry-run. Use --apply to remove clean candidates only.
#
# Safety:
# - never touches main worktree
# - skips dirty worktrees unless --force-dirty
# - skips branches with unique patches (git cherry +)
set -euo pipefail

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
GIT="${GIT:-/usr/bin/git}"
ROOT="$($GIT rev-parse --show-toplevel 2>/dev/null)" || {
  echo "not in a git repo" >&2
  exit 1
}
cd "$ROOT"
$GIT fetch origin main --prune >/dev/null 2>&1 || true

APPLY=0
FORCE_DIRTY=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --force-dirty) FORCE_DIRTY=1 ;;
    -h|--help)
      echo "usage: $0 [--apply] [--force-dirty]"
      exit 0
      ;;
  esac
done

main_wt="$ROOT"
echo "origin/main=$($GIT rev-parse --short origin/main 2>/dev/null || echo '?')"
echo "mode=$([ "$APPLY" = 1 ] && echo APPLY || echo DRY-RUN)"

$GIT worktree list --porcelain | awk '
  /^worktree / { wt=$2 }
  /^branch / {
    br=$2
    sub(/^refs\/heads\//,"",br)
    print wt, br
  }
' | while read -r wt br; do
  [ -n "$wt" ] || continue
  [ "$wt" = "$main_wt" ] && continue
  case "$br" in
    main|master) continue ;;
  esac
  if [ ! -d "$wt" ]; then
    continue
  fi
  dirty="$($GIT -C "$wt" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  unique="$($GIT cherry origin/main "$br" 2>/dev/null | grep -c '^+' || true)"
  unique=${unique:-0}
  if [ "$unique" != "0" ]; then
    echo "KEEP unique=$unique dirty=$dirty $wt ($br)"
    continue
  fi
  if [ "$dirty" != "0" ] && [ "$FORCE_DIRTY" != "1" ]; then
    echo "KEEP dirty=$dirty (use --force-dirty) $wt ($br)"
    continue
  fi
  echo "CANDIDATE dirty=$dirty $wt ($br)"
  if [ "$APPLY" = 1 ]; then
    $GIT worktree remove --force "$wt"
    $GIT branch -D "$br" 2>/dev/null || true
    echo "  removed"
  fi
done

echo "done."
