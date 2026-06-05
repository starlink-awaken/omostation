#!/bin/bash
# eCOS E2E health check
# Usage: e2e-check.sh
SCRIPT="$0"
# Resolve symlink to the real script path
if [ -L "$SCRIPT" ]; then
    TARGET="$(readlink "$SCRIPT")"
    case "$TARGET" in
        /*) SCRIPT="$TARGET" ;;
        *) SCRIPT="$(dirname "$SCRIPT")/$TARGET" ;;
    esac
fi
cd "$(dirname "$SCRIPT")/.."
PYTHONPATH=src python3 src/runtime/e2e.py
