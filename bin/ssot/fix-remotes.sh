#!/usr/bin/env bash
# 2026-09-13: 修复逻辑迁移至 fix-remotes.py (bash 版三重缺陷致自愈失效 + 反成污染源).
exec python3 "$(dirname "$0")/fix-remotes.py" "$@"
