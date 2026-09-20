#!/bin/bash
# closeout-pr.sh — B2 跨 repo closeout 一体化 (B2.1)
#
# 集成 A2 SOP 5 步 + 跨子模块 retro 模板统一:
#   1. 复用 gac-worktree.sh claim + 准备 closeout 步骤
#   2. 复制 retro 模板到 .omo/_knowledge/retros/<bet-id>.md (若不存在)
#   3. 检查子模块 closeout 状态 (调用 cross-repo-status.py)
#   4. 提示 PR 创建命令 (gh pr create)
#   5. 提示 merge + 清理
#
# 用法:
#   bash bin/closeout-pr.sh <bet-id>            # 主仓 closeout (omostation)
#   bash bin/closeout-pr.sh <bet-id> <repo>     # 指定子仓 (omostation-cockpit-ui 等)
#
# 依赖:
#   bin/gac/gac-worktree.sh
#   bin/mof/cross-repo-status.py
#   bin/ssot/retro-template.md
#
# 安全:
#   - 仅在已有 worktree 内运行 (worktree claim 已在前置)
#   - 所有 git 操作走 gac-worktree.sh (有 hook 守卫)
#   - 跨子模块 retro 复制仅限 .md 模板, 不复制二进制

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
if [ -z "$ROOT" ]; then
    echo "❌ 不在 git 仓库内"
    exit 1
fi

BET_ID="${1:-}"
REPO="${2:-omostation}"
RETRO_TEMPLATE="$ROOT/bin/ssot/retro-template.md"
RETRO_DIR=".omo/_knowledge/retros"

if [ -z "$BET_ID" ]; then
    echo "用法: bash bin/closeout-pr.sh <bet-id> [repo=omostation]"
    exit 1
fi

if [ ! -f "$RETRO_TEMPLATE" ]; then
    echo "❌ retro 模板不存在: $RETRO_TEMPLATE"
    exit 1
fi

echo "━━━ closeout-pr (B2.1) ━━━"
echo "BET: $BET_ID"
echo "Repo: $REPO"
echo

# 步骤 1: 检查 retro 是否已落盘
RETRO_PATH="$ROOT/$RETRO_DIR/$BET_ID.md"
if [ ! -f "$RETRO_PATH" ]; then
    echo "Step 1 · Retro 不存在, 复制模板"
    cp "$RETRO_TEMPLATE" "$RETRO_PATH"
    echo "  ✅ 已创建: $RETRO_PATH"
    echo "  ⚠️  请编辑 frontmatter + 正文 (本脚本不自动填充)"
else
    echo "Step 1 · Retro 已存在: $RETRO_PATH"
fi
echo

# 步骤 2: 跨子模块状态快照
echo "Step 2 · 跨子模块状态快照"
if [ -x "$ROOT/bin/mof/cross-repo-status.py" ]; then
    python3 "$ROOT/bin/mof/cross-repo-status.py" --bet "$BET_ID" 2>&1 | tail -20
else
    echo "  ⚠️  cross-repo-status.py 不存在, 跳过 (B2.2 待实施)"
fi
echo

# 步骤 3: 提示 PR 创建
echo "Step 3 · 创建 PR"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "  当前分支: $BRANCH"
echo "  推荐命令:"
echo "    gh pr create --title \"fix(<scope>): close $BET_ID — <一句话>\" \\"
echo "      --body-file <(cat <<EOF"
echo "    ## Summary"
echo "    <一句话>"
echo ""
echo "    [bet-retro/v1] $BET_ID"
echo "    EOF"
echo "    )"
echo

# 步骤 4: 提示 merge
echo "Step 4 · 合并 (admin squash)"
echo "  gh pr merge <pr-num> --admin --squash --delete-branch"
echo "  gac-worktree.sh release $BRANCH"
echo

# 步骤 5: 清理
echo "Step 5 · 清理"
echo "  cd ../.. && git worktree remove --force <worktree-path>"
echo "  git branch -D $BRANCH"
echo

echo "✅ closeout-pr 引导完成 — 按提示逐步执行"