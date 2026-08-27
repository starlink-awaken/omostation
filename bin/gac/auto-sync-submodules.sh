#!/usr/bin/env bash
# Auto-sync stale submodule pointers to their remote main branches.
#
# Usage:
#     bash bin/gac/auto-sync-submodules.sh            # dry-run
#     bash bin/gac/auto-sync-submodules.sh --apply     # apply fixes
#     bash bin/gac/auto-sync-submodules.sh --json      # JSON output

set -euo pipefail

ROOT="$(git -C "$PWD" rev-parse --show-toplevel)"
cd "$ROOT"

APPLY=0
JSON=0
for arg in "$@"; do
    case "$arg" in
        --apply) APPLY=1 ;;
        --json) JSON=1 ;;
    esac
done

fixes=0
skipped=0
errors=0

for submod in $(git submodule --quiet status | awk '{print $2}'); do
    sub_name=$(basename "$submod")
    local_sha=$(git -C "$submod" rev-parse HEAD 2>/dev/null || echo "")
    remote_sha=$(git -C "$submod" rev-parse origin/main 2>/dev/null || echo "")

    if [ -z "$local_sha" ] || [ -z "$remote_sha" ]; then
        if [ "$JSON" -eq 0 ]; then
            echo "SKIP: $sub_name (cannot resolve SHAs)"
        fi
        skipped=$((skipped + 1))
        continue
    fi

    if [ "$local_sha" = "$remote_sha" ]; then
        continue
    fi

    behind=$(git -C "$submod" rev-list --count "$local_sha..$remote_sha" 2>/dev/null || echo "0")
    ahead=$(git -C "$submod" rev-list --count "$remote_sha..$local_sha" 2>/dev/null || echo "0")

    if [ "$ahead" -gt 0 ]; then
        if [ "$JSON" -eq 0 ]; then
            echo "SKIP: $sub_name (local ahead by $ahead, has unpushed commits)"
        fi
        skipped=$((skipped + 1))
        continue
    fi

    if [ "$JSON" -eq 0 ]; then
        echo "STALE: $sub_name (behind by $behind commits)"
    fi

    if [ "$APPLY" -eq 1 ]; then
        if git -C "$submod" checkout origin/main --quiet 2>/dev/null; then
            git add "$submod"
            fixes=$((fixes + 1))
            if [ "$JSON" -eq 0 ]; then
                echo "  FIXED: $sub_name -> $remote_sha"
            fi
        else
            errors=$((errors + 1))
            if [ "$JSON" -eq 0 ]; then
                echo "  ERROR: $sub_name checkout failed"
            fi
        fi
    else
        fixes=$((fixes + 1))
    fi
done

if [ "$JSON" -eq 1 ]; then
    echo "{\"fixed\":$fixes,\"skipped\":$skipped,\"errors\":$errors,\"applied\":$([ $APPLY -eq 1 ] && echo true || echo false)}"
else
    echo ""
    echo "Summary: fixed=$fixes skipped=$skipped errors=$errors applied=$([ $APPLY -eq 1 ] && echo true || echo false)"
    if [ "$APPLY" -eq 1 ] && [ "$fixes" -gt 0 ]; then
        echo "Run 'git commit -m \"chore: sync stale submodule pointers\"' to commit."
    fi
fi

exit 0
