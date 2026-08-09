#!/usr/bin/env bash
set -euo pipefail
# 机制: 检查 canonical .githooks/ 与实际执行位置是否一致
# 防止 hook 覆盖丢失 (#1257 教训)

canonical="$(git rev-parse --show-toplevel)/.githooks"
actual="$(git rev-parse --git-path hooks)"

[ -d "$canonical" ] || exit 0
[ -d "$actual" ] || exit 0

mismatch=""
for h in "$canonical"/*; do
  [ -f "$h" ] || continue
  name=$(basename "$h")
  if [ ! -f "$actual/$name" ]; then
    mismatch="$mismatch $name(缺失)"
  elif ! cmp -s "$h" "$actual/$name"; then
    mismatch="$mismatch $name(不一致)"
  fi
done

if [ -n "$mismatch" ]; then
  echo "[check-hook-sync] ⚠️ hook 不一致:$mismatch"
  echo "[check-hook-sync] ⚠️ 运行 install-hooks 同步: bash projects/ecos/scripts/install-hooks.sh"
  exit 1
fi

echo "[check-hook-sync] ✅ hook 一致性检查通过"
exit 0
