#!/bin/bash
# sync-main.sh — 开工第一步: 同步 main + reset 工作树到 origin/main
# (PITFALL-COO-006 防本地工作树 ≠ origin/main 状态)
#
# 背景:
#   4018 实证: PR #3827 merge 后, 本地 (没 reset) 看到 47 jobs + 4 dups,
#   实际 main 已是 43 jobs + 0 dups. 差点据此开 #3829 重复做 PR #3827 已做的事.
#   根因: fetch 只更新 refs/remotes/origin/main, 工作树还停留 fetch 前的快照.
#
# 行为:
#   1. git fetch origin main  (拉最新 main 引用)
#   2. git reset --hard origin/main  (工作树完全同步)
#   3. git submodule update --init  (子模块物化, 治 l0-mapping 缺失 / cockpit 模块空目录)
#   4. git status --short  (报告当前 dirty 状态, 如果 dirty 拒绝 reset 防丢工作)
#
# 用法:
#   bin/gac/sync-main.sh
#   bin/gac/sync-main.sh --no-reset  (只 fetch, 不 reset — 留 dirty)
#   bin/gac/sync-main.sh --allow-dirty (强制 reset 覆盖 dirty)
#
# 安全:
#   - 默认若工作树 dirty, abort (拒绝 reset 覆盖, 防丢未提交改动)
#   - --allow-dirty 标志强制, 配合 bash 引用 $WORKTREE_DIRTY_BACKUP 自动 stash
#
# 退出码:
#   0 = 同步成功
#   1 = 拉取失败
#   2 = 工作树 dirty (--no-reset 也返回 2 if dirty + 没 --allow-dirty)
#   3 = submodule init 失败 (非阻断, 警告)
#
# 配套:
#   AGENTS.md §11 Key Patterns 引用 PITFALL-COO-006
#   bin/ssot/doc-ssot-lint.py (现在能 worktree 下不崩)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ALLOW_DIRTY=0
NO_RESET=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --allow-dirty) ALLOW_DIRTY=1; shift ;;
        --no-reset) NO_RESET=1; shift ;;
        -h|--help)
            sed -n '3,40p' "$0"
            exit 0 ;;
        *)
            echo "Unknown arg: $1" >&2
            exit 1 ;;
    esac
done

cd "$WORKSPACE_ROOT"

# Safety: 拒绝 dirty 工作树 reset
if [[ "$ALLOW_DIRTY" == "0" ]]; then
    if ! git diff --quiet HEAD 2>/dev/null || [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
        echo "❌ 工作树 dirty. 拒绝 reset (防丢未提交改动)."
        echo "   选项: 提交 → git add && git commit"
        echo "         stash → git stash push -u"
        echo "         强制 → bin/gac/sync-main.sh --allow-dirty"
        echo
        git status --short
        exit 2
    fi
fi

# 1. fetch
echo "▶ fetch origin main"
git fetch origin main 2>&1 | tail -3

if [[ "$NO_RESET" == "1" ]]; then
    echo
    echo "⏭ --no-reset, skip reset. 当前状态:"
    git log --oneline -3 origin/main
    exit 0
fi

# 2. reset
echo
echo "▶ reset --hard origin/main"
git reset --hard origin/main 2>&1 | tail -2

# 3. submodule update --init (治 l0-mapping 缺失)
echo
echo "▶ git submodule update --init"
# macOS bash 没 timeout 命令. 用纯 bash sleep+kill 替代.
git submodule update --init --recursive > /tmp/sync-main-sub.log 2>&1 &
SUB_PID=$!
SUB_TIMEOUT=60
sleep "$SUB_TIMEOUT" && kill "$SUB_PID" 2>/dev/null
wait "$SUB_PID" 2>/dev/null
SUB_EXIT=$?
if [[ $SUB_EXIT -eq 0 ]]; then
    echo "✅ submodule init OK"
elif [[ $SUB_EXIT -eq 143 ]]; then
    echo "⚠️  submodule update 超时 (${SUB_TIMEOUT}s). doc-ssot-lint 可能报 'L0 约束源缺失'"
    echo "   手动: git submodule update --init --recursive (后台跑, 完成后 sync-main.sh 重试)"
else
    echo "⚠️  submodule init 失败 exit=$SUB_EXIT. 后续验证可能误报"
fi
tail -5 /tmp/sync-main-sub.log 2>/dev/null || true

# 4. report
echo
echo "▶ 当前状态"
git status --short
echo
echo "HEAD: $(git rev-parse --short HEAD) — $(git log --oneline -1)"

# 5. 后续验证建议
echo
echo "▶ 建议跑 verify:"
echo "   python3 bin/plan/bet-ledger.py lint"
echo "   python3 bin/ssot/doc-ssot-lint.py"
echo "   python3 bin/ssot/check-index-drift.py"
echo "   make gac-local-gate"