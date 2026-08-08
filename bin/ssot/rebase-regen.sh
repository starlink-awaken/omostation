#!/usr/bin/env bash
# Rebase-regen automation (ADR-0384 D1): 一键后置并发 PR 后的全量再生成.
#
# 流程: M1 重派生 + 文档重生成 + bos-registry 同步 + ruff 修复 + M1 再同步 + stat bump.
# 每步独立可重入, 不调用 --apply/--force.
#
# 用法: bash bin/ssot/rebase-regen.sh [--no-bump] [--quiet]
# 退出码: 0 = clean, 1 = 有差异待 commit

set -euo pipefail

WORKSPACE="${WORKSPACE:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$WORKSPACE"

QUIET=0
BUMP=1
for arg in "$@"; do
    case "$arg" in
        --quiet|-q) QUIET=1 ;;
        --no-bump) BUMP=0 ;;
        *) echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

log() { [[ "$QUIET" -eq 0 ]] && echo "$@"; }
fail() { echo "❌ $@" >&2; exit 1; }

# 1. 安全: 检查工作树是否脏 (有未提交改动)
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    fail "工作树有未提交改动, 请先 commit/stash:
  $(git status --short | head -10)"
fi

log "▶ Step 1/7: gac-m1-sync (re-derive from registry)"
uv run --with pyyaml python bin/gac/gac-m1-sync.py --sync --json > /tmp/rebase-regen-m1.json
m1_created=$(python3 -c "import json,sys;d=json.load(open('/tmp/rebase-regen-m1.json'));a=d.get('actions',{});print(len(a.get('created',[])))")
log "  created=$m1_created M1 instances"

log "▶ Step 2/7: gen-capability-registry"
uv run --with pyyaml python bin/cockpit/gen-capability-registry.py --quiet
log "  gen-capability-registry ok"

log "▶ Step 2b/7: gen-ci-surfaces-triggers (workflow_triggers 登记对齐)"
uv run --with pyyaml python bin/ssot/gen-ci-surfaces-triggers.py --write > /tmp/rebase-regen-ci.log 2>&1 || \
    log "  ci-surfaces triggers already aligned"
log "  gen-ci-surfaces-triggers ok"

log "▶ Step 3/7: sync-bos-registry"
uv run --with pyyaml python bin/ssot/sync-bos-registry.py --write > /tmp/rebase-regen-bos.log 2>&1 || \
    log "  bos-registry drift unchanged"
log "  bos-registry synced"

log "▶ Step 4/7: gen-help-docs"
uv run --with pyyaml python bin/cockpit/gen-help-docs.py > /dev/null 2>&1 || true
log "  gen-help-docs ok"

log "▶ Step 5/7: ruff --fix on bin/ scripts/"
uv run ruff check --fix --select E4,E7,E9,F --ignore F401,F821,E402,E722,F841,F541 \
    $(git ls-files 'bin/*.py' 'scripts/*.py') > /tmp/rebase-regen-ruff.log 2>&1 || true
ruff_changed=$(git status --short | grep -cE "^\s*M.*\.py$" || true)
log "  ruff --fix touched $ruff_changed files"

if [[ "$ruff_changed" -gt 0 ]]; then
    log "▶ Step 6/7: gac-m1-sync (post-ruff re-derive)"
    git add -A
    # re-derive after ruff changes
    uv run --with pyyaml python bin/gac/gac-m1-sync.py --sync --json > /tmp/rebase-regen-m1b.json || true
fi

if [[ "$BUMP" -eq 1 ]]; then
    log "▶ Step 7/7: mof-capabilities stat bump"
    uv run --with pyyaml python bin/mof/check-mof-capabilities-drift.py --bump-stats > /tmp/rebase-regen-mof.log 2>&1 || \
        log "  mof stats already aligned"
fi

# Final summary
echo ""
echo "═══ rebase-regen summary ═══"
changed=$(git status --short | wc -l | tr -d ' ')
echo "uncommitted changes: $changed"
if [[ "$changed" -gt 0 ]]; then
    echo ""
    git status --short | head -10
    echo ""
    echo "next: review diff → git add -A → commit"
    exit 1
fi
echo "✅ clean (no changes needed)"
exit 0
