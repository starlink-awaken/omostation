#!/bin/bash
# sync-gitignore.sh — 统一子模块 .gitignore (报告债务②, .omc/cache 外溢)
#
# 从通用 patterns 同步到 projects/*/.gitignore, 扼杀 .omc/cache/lock 外溢.
# 报告建议2 (CTO 路线图): 工作区 Ignore 分发机制.
#
# 用法:
#   sync-gitignore.sh --check   # 查子模块 .gitignore 缺哪些通用 ignore
#   sync-gitignore.sh --sync    # 追加通用 ignore 到子模块 .gitignore

set -e

WS="$(cd "$(dirname "$0")/.." && pwd)"
# 通用 ignore patterns (子模块都该有, 防 .omc/cache 外溢)
COMMON_PATTERNS=(".omc/" "cache/" "*.tmp" ".DS_Store" "__pycache__/")

cmd="${1:---check}"

case "$cmd" in
  --check)
    echo "=== 子模块 .gitignore 通用 ignore 覆盖检查 ==="
    total=0; ok=0; missing_count=0
    for proj in "$WS"/projects/*/; do
      [ -d "$proj/.git" ] || continue  # 只 git 子模块
      total=$((total + 1))
      name="$(basename "$proj")"
      gi="$proj.gitignore"
      if [ ! -f "$gi" ]; then
        echo "  ❌ $name: 无 .gitignore"
        missing_count=$((missing_count + 1))
        continue
      fi
      missing=()
      for p in "${COMMON_PATTERNS[@]}"; do
        grep -qF "$p" "$gi" || missing+=("$p")
      done
      if [ ${#missing[@]} -gt 0 ]; then
        echo "  ⚠️  $name: 缺 ${missing[*]}"
        missing_count=$((missing_count + 1))
      else
        ok=$((ok + 1))
      fi
    done
    echo ""
    echo "总计: $total 子模块 | ✅ $ok 完整 | ⚠️/❌ $missing_count 缺"
    ;;

  --sync)
    echo "=== 同步通用 ignore 到子模块 (追加, 不覆盖现有) ==="
    synced=0
    for proj in "$WS"/projects/*/; do
      [ -d "$proj/.git" ] || continue
      gi="$proj.gitignore"
      touch "$gi"
      added=0
      for p in "${COMMON_PATTERNS[@]}"; do
        if ! grep -qF "$p" "$gi"; then
          echo "$p" >> "$gi"
          added=$((added + 1))
        fi
      done
      if [ "$added" -gt 0 ]; then
        echo "  ✅ $(basename "$proj"): +$added patterns"
        synced=$((synced + 1))
      fi
    done
    echo ""
    echo "同步 $synced 子模块. 验证: sync-gitignore.sh --check"
    ;;

  *)
    echo "sync-gitignore.sh — 统一子模块 .gitignore (报告债务②)"
    echo ""
    echo "用法: sync-gitignore.sh {--check|--sync}"
    echo "  --check   查子模块缺哪些通用 ignore"
    echo "  --sync    追加通用 ignore (.omc/ cache/ *.tmp .DS_Store __pycache__/)"
    exit 1
    ;;
esac
