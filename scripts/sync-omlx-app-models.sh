#!/bin/bash
# 同步 oMLX App 的模型软链目录 (~/omlx/app-models) 与 config.toml 的注册状态。
# omlxc 内建的 `models reconcile` 命令尚未接入 daemon (E100 unsupported)，
# 在它实装前用这个脚本代替，避免 config.toml 删模型后 app-models 留下死链接
# (2026-08-21 实测：曾有 5 个死链接 + 2 个指向已删除文件的悬空链接，
#  静默拖垮了 omlx-app 后端全部 placement 的可用性)。
set -uo pipefail

CONFIG="$HOME/.config/omlxc/config.toml"
APP_MODELS="$HOME/omlx/app-models"

echo "=== 扫描 config.toml 中 omlx-app 后端引用的 model_id ==="
registered=$(python3 - "$CONFIG" <<'EOF'
import re, sys
content = open(sys.argv[1]).read()
blocks = re.split(r'\n(?=\[\[placements\]\])', content)
ids = set()
for b in blocks:
    if 'backend_id = "mbp-m5-max-128g-omlx-app"' in b:
        m = re.search(r'backend_model_id = "([^"]+)"', b)
        if m:
            ids.add(m.group(1))
for i in sorted(ids):
    print(i)
EOF
)

echo "config.toml 声明: $(echo "$registered" | wc -l | tr -d ' ') 个"

echo ""
echo "=== 检查死链接 (config 已删但 app-models 还在) ==="
removed=0
for link in "$APP_MODELS"/*; do
  name=$(basename "$link")
  [ "$name" = ".omlxc-managed.json" ] && continue
  [ -L "$link" ] || continue
  if ! echo "$registered" | grep -qx "$name"; then
    echo "  移除: $name -> $(readlink "$link")"
    rm -f "$link"
    removed=$((removed+1))
  fi
done
echo "共移除 $removed 个"

echo ""
echo "=== 检查悬空链接 (目标文件已不存在) ==="
broken=0
for link in "$APP_MODELS"/*; do
  [ -L "$link" ] || continue
  if [ ! -e "$link" ]; then
    echo "  悬空: $(basename "$link") -> $(readlink "$link") (目标已删除)"
    rm -f "$link"
    broken=$((broken+1))
  fi
done
echo "共清理 $broken 个悬空链接"

echo ""
echo "=== 检查缺失 (config 有但 app-models 没有对应软链，需人工确认源路径) ==="
missing=0
for id in $registered; do
  if [ ! -e "$APP_MODELS/$id" ]; then
    echo "  缺失: $id (config.toml 声明了 omlx-app placement，但 app-models 下没有软链)"
    missing=$((missing+1))
  fi
done
if [ "$missing" -eq 0 ]; then
  echo "  无缺失"
fi

echo ""
echo "=== 完成: 移除 $removed 死链接, 清理 $broken 悬空链接, $missing 项待人工补齐 ==="
