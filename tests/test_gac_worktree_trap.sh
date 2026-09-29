#!/bin/bash
# B2 (ADR-0367): gac-worktree.sh claim 异常路径下 claim marker 必须被 trap 清理.
#
# 验证: claim 流程中 marker (.ws-<session>.claiming) 创建后若发生失败,
# EXIT trap 必须清理 marker, 否则残留 marker 会永久阻塞该 session 后续 claim.
#
# 场景 1 (核心): canonical remote + 无效 HTTPS 代理 → resolve 通过,
#               fetch 失败 (marker 已创建) → EXIT trap 清理 marker.
# 场景 2 (正常): 真实 github fetch (若网络不可达则跳过, 不阻塞验收).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAIM_SCRIPT="$ROOT/bin/gac/gac-worktree.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
CANONICAL="https://github.com/starlink-awaken/omostation.git"

TEST_REPO="$TMP/test-repo"
git init -q -b main "$TEST_REPO"
git -C "$TEST_REPO" config user.email trap@test
git -C "$TEST_REPO" config user.name trap
git -C "$TEST_REPO" commit --allow-empty -qm init
git -C "$TEST_REPO" remote add origin "$CANONICAL"

echo "── B2-1: 失败路径 (fetch 因无效代理失败 → trap 必须清 marker) ──"
# 2026-09-29: 必须隔离宿主 git config (GIT_CONFIG_GLOBAL/SYSTEM=/dev/null)。
# 否则宿主全局的 `url.*.insteadOf` 会把 https://github.com 改写成 SSH ⇒ 请求绕过 http.proxy
# 并凭本机 key 成功 ⇒ 本场景的「fetch 必失败」前提不成立 (实测 claim 会成功, 该测试恒红)。
set +e
OUT=$(WS_ROOT="$TEST_REPO" WS_PARENT="$TMP" OMOSTATION_ROOT_REMOTE=origin \
  SKIP_SUBMODULE_INIT=1 \
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
  GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0="http.proxy" GIT_CONFIG_VALUE_0="http://127.0.0.1:9" \
  bash "$CLAIM_SCRIPT" claim trap-session 2>&1)
RC=$?
set -e
echo "  claim exit=$RC"; echo "$OUT" | tail -4
if [ "$RC" -eq 0 ]; then
  echo "❌ 预期 fetch 失败, 实际 claim 成功"
  exit 1
fi
if [ -f "$TMP/.ws-trap-session.claiming" ]; then
  echo "❌ EXIT trap 未清理 claim marker: .ws-trap-session.claiming 残留"
  echo "$OUT" | tail -5
  exit 1
fi
echo "  ✅ 失败路径 marker 已被 trap 清理"

echo ""
echo "── B2-2: 正常完成路径 (真实 fetch; 需真网络+凭据 ⇒ 默认跳过) ──"
# 2026-09-29: 默认**不跑**该场景 —— 它依赖真实网络 + 可用凭据, 在隔离宿主 config 后通常必然失败,
# 却要干等满 45s 超时 (实测该测试因此 54s, 不适合进 CI)。要跑它: SHELL_TEST_NET=1 bash 本文件。
if [ "${SHELL_TEST_NET:-0}" != "1" ]; then
  echo "  ⏭  跳过 (设 SHELL_TEST_NET=1 可跑; 该场景需真网络)"
else
  # macOS 无 timeout 命令, 用 perl 实现 (45s 上限)
  # 同样隔离宿主 config: 保证走 HTTPS 而非被改写成 SSH, 且不误用宿主的凭据缓存。
  set +e
  OUT=$(WS_ROOT="$TEST_REPO" WS_PARENT="$TMP" OMOSTATION_ROOT_REMOTE=origin \
    SKIP_SUBMODULE_INIT=1 \
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 \
    perl -e 'alarm shift; exec @ARGV' 45 bash "$CLAIM_SCRIPT" claim ok-session 2>&1)
  RC=$?
  set -e
  if [ "$RC" -eq 0 ]; then
    if [ -f "$TMP/.ws-ok-session.claiming" ]; then
      echo "❌ 正常完成未清理 marker"
      exit 1
    fi
    echo "  ✅ 正常路径 marker 已清理"
    git -C "$TEST_REPO" worktree remove --force "$TMP/ws-ok-session" 2>/dev/null || true
    git -C "$TEST_REPO" branch -D work/ok-session 2>/dev/null || true
  else
    echo "  ⚠️  真实 fetch 失败 (exit=$RC), 该场景跳过 — B2 由场景 1 覆盖"
  fi
fi

echo ""
echo "✅ B2 trap 清理验证完成"
