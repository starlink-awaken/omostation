#!/bin/bash
# distribute-submodule-workflows.sh — 批量为全量子模块配置 Auto-PR 薄工作流
#
# 遍历 .gitmodules 中的所有子模块，在其 .github/workflows/ 目录下生成/更新
# bump-main-pr.yml，调用主仓的 reusable-submodule-bump-pr.yml。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== 开始全量子模块 Auto-PR 工作流分发 ==="

# 提取 .gitmodules 中的所有 path
submodules=$(git -C "$WS_ROOT" config --file .gitmodules --get-regexp path | awk '{print $2}')

count=0
for sub in $submodules; do
    sub_dir="$WS_ROOT/$sub"
    if [ ! -d "$sub_dir" ]; then
        echo "⏭️  子模块目录不存在 (未初始化): $sub，跳过"
        continue
    fi

    workflows_dir="$sub_dir/.github/workflows"
    mkdir -p "$workflows_dir"
    workflow_file="$workflows_dir/bump-main-pr.yml"

    cat << YAML_EOF > "$workflow_file"
name: Submodule Bump Main PR

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      target_sha:
        description: 'Target commit SHA (leave empty for latest main)'
        required: false
        default: ''

jobs:
  trigger-bump:
    uses: starlink-awaken/omostation/.github/workflows/reusable-submodule-bump-pr.yml@main
    with:
      submodule_path: $sub
      target_sha: \${{ github.event.inputs.target_sha }}
      release_tag: \${{ github.event.release.tag_name }}
    secrets:
      bot_token: \${{ secrets.OMOSTATION_BOT_TOKEN }}
YAML_EOF

    echo "✅ 已生成: $sub/.github/workflows/bump-main-pr.yml"
    count=$((count + 1))
done

echo ""
echo "=== 分发完成: 共处理 $count 个子模块 ==="
