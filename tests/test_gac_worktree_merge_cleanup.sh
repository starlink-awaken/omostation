#!/bin/bash
# 回归: merge 的收尾清理不得被「本地镜像同步失败」阻断, 且收尾必须清掉 branch-claim
# (2026-09-29 加固).
#
# 背景 (三次同类实证: 僵尸 .git/index.lock / 主区脏树 / 本地 main 分叉):
#   旧实现在 `git pull --ff-only` 失败处受 `set -euo pipefail` 直接退出 ⇒
#   worktree / 本地分支 / branch-claim 三者全残留, 每次都要人肉补 `release`.
#   claim 残留的真因: **merge 从不调用 `branch-release`** —— 只有 release 会调
#   swarm_discipline.release_branch_lock, 删 `.omo/_delivery/branch-claims/<session>.json`.
#
# 覆盖 (直接测抽出的两个函数 + 接线契约; 无需绕过 resolve_root_remote 的 canonical 守卫):
#   C   接线: merge 非致命调 sync_local_main_best_effort / post_merge_release,
#             fail-closed 前置校验与 canonical-repo 契约字面量都还在.
#   A   收尾成功路径: worktree / 本地分支 / branch-claim 三者全清.
#   A2  收尾失败路径 (worktree 移除失败): 必须**保留** claim (不谎报成功).
#   B   镜像同步成功路径: rc=0 且静默.
#   B2  镜像同步失败路径: rc≠0 + 诊断, 且**本地 main 逐字节不变** (禁止 reset/merge).
#   D   守卫提示: merge/release 两处接线 print_dirty_worktree_hints, 且该 helper
#             (a) 干净态不误报 (b) 脏态**带子模块名**报明细 + 给出四类自清命令.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/bin/gac/gac-worktree.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf '❌ %s\n' "$1"; exit 1; }
GITENV=(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null)

# 只装载函数 (lib-only seam), 不执行命令分发; set +e 以免被函数返回码打断.
call_fn() {  # $1 = ws  $2 = bash 片段 (内可用 $FIXTMP)
  local ws="$1"
  local body="$2"
  ( cd "$ws" && env "${GITENV[@]}" WS_ROOT="$ws" WS_PARENT="$TMP" ROOT_REMOTE=origin FIXTMP="$TMP" \
      GAC_WORKTREE_LIB_ONLY=1 bash -c 'source "$1" >/dev/null 2>&1; set +e; '"$body" _ "$SCRIPT" 2>&1 )
}

# ── C: 接线契约 ─────────────────────────────────────────────────────────
echo "── C: 接线契约 ──"
grep -qF 'sync_local_main_best_effort || LOCAL_SYNC_RC=1' "$SCRIPT" \
  || fail "merge 未以非致命方式调用 sync_local_main_best_effort (旧版即在此 exit)"
echo "  ✅ 镜像同步: 非致命调用"
grep -qF 'post_merge_release "$session" "$branch" "$wt" || WT_RC=1' "$SCRIPT" \
  || fail "merge 未以非致命方式调用 post_merge_release"
echo "  ✅ 收尾: 非致命调用"
grep -qF 'verify_clean_for_force_removal "$wt" || exit 1' "$SCRIPT" || fail "fail-closed 前置校验丢失"
grep -qF 'remove_verified_pasw "$wt" || exit 1' "$SCRIPT" || fail "PASW fail-closed 校验丢失"
echo "  ✅ fail-closed 前置校验保留"
grep -qF 'git pull --ff-only "$ROOT_REMOTE" main' "$SCRIPT" || fail "canonical-repo 契约字面量丢失"
grep -qF 'branch-release' "$SCRIPT" || fail "branch-release 接线丢失 (claim 会残留)"
grep -qF 'GAC_WORKTREE_LIB_ONLY' "$SCRIPT" || fail "缺少 lib-only 测试缝 (本测试依赖它)"
echo "  ✅ canonical-repo 契约字面量 + claim 清理接线"

# ── 夹具: 裸 origin + 克隆 + session worktree + branch-claim + 工具替身 ──
setup() {  # $1 = mode(diverged|synced)  $2 = session
  local mode="$1"
  local session="$2"
  local ws="$TMP/ws-$mode-$session"
  git init -q --bare -b main "$TMP/origin-$session.git"
  git clone -q "$TMP/origin-$session.git" "$ws"
  git -C "$ws" config user.email t@example.invalid
  git -C "$ws" config user.name t
  git -C "$ws" commit -q --allow-empty -m init
  git -C "$ws" push -q origin main
  if [ "$mode" = "diverged" ]; then
    git -C "$ws" commit -q --allow-empty -m origin-side
    git -C "$ws" push -q origin main
    git -C "$ws" reset -q --hard HEAD~1
    git -C "$ws" commit -q --allow-empty -m local-side   # 本地另一条线 ⇒ 真分叉
    # 构造有效性: 必须真分叉, 否则本场景根本没被验证
    [ "$(git -C "$ws" rev-parse main)" != "$(git -C "$ws" rev-parse origin/main)" ] \
      || fail "夹具无效: diverged 态下 main 仍等于 origin/main"
    [ "$(git -C "$ws" rev-list --count origin/main..main)" != "0" ] \
      || fail "夹具无效: 本地 main 未领先"
    [ "$(git -C "$ws" rev-list --count main..origin/main)" != "0" ] \
      || fail "夹具无效: 本地 main 未落后"
  else
    [ "$(git -C "$ws" rev-parse main)" = "$(git -C "$ws" rev-parse origin/main)" ] \
      || fail "夹具无效: synced 态下 main 已分叉"
  fi
  git -C "$ws" worktree add -q -b "agent/governance-agent/$session" "$TMP/ws-$session" main
  mkdir -p "$ws/.omo/_delivery/branch-claims"
  printf '{"branch": "agent/governance-agent/%s"}\n' "$session" \
    > "$ws/.omo/_delivery/branch-claims/$session.json"
  # 工具替身: 只实现 gac-worktree.sh 依赖的 `branch-release` 契约;
  # 参数不符即非零退出 ⇒ 「接线正确」被真正验证, 而不是被替身掩盖.
  # 以 CWD 为根 (与真实工具的 root_from_cwd() 同构) ⇒ 不会碰真实工作区.
  mkdir -p "$ws/bin/gac"
  cat > "$ws/bin/gac/swarm-discipline-cli.py" <<'STUB'
import pathlib
import sys

args = sys.argv[1:]
if args[:1] != ["branch-release"] or "--session" not in args:
    print(f"unexpected args: {args}", file=sys.stderr)
    sys.exit(2)
session = args[args.index("--session") + 1]
claim = pathlib.Path.cwd() / ".omo" / "_delivery" / "branch-claims" / f"{session}.json"
if claim.is_file():
    claim.unlink()
print(f'{{"released": true, "session": "{session}"}}')
STUB
  printf '%s' "$ws"
}

# ── A: 收尾成功路径 ─────────────────────────────────────────────────────
echo ""
echo "── A: post_merge_release 成功路径 ⇒ worktree/分支/claim 全清 ──"
WS_A="$(setup diverged regress)"
out="$(call_fn "$WS_A" 'post_merge_release regress agent/governance-agent/regress "$FIXTMP/ws-regress"; printf "rc=%d\n" $?')"
printf '%s' "$out" | grep -q "rc=0" || { printf '%s\n' "$out" | tail -8; fail "post_merge_release 未返回 0"; }
echo "  ✅ rc=0"
[ ! -d "$TMP/ws-regress" ] || fail "worktree 未移除"
echo "  ✅ worktree 已移除"
git -C "$WS_A" rev-parse --verify -q "refs/heads/agent/governance-agent/regress" >/dev/null \
  && fail "本地分支未删除"
echo "  ✅ 本地分支已删除"
[ ! -f "$WS_A/.omo/_delivery/branch-claims/regress.json" ] || fail "branch-claim json 仍残留"
echo "  ✅ branch-claim 已删除"

# ── A2: 收尾失败路径 (worktree 移除失败) ⇒ 保留 claim ────────────────────
echo ""
echo "── A2: worktree 移除失败 ⇒ 保留 claim (不谎报成功) ──"
git -C "$WS_A" worktree add -q -b agent/governance-agent/regress2 "$TMP/ws-regress2" main
printf '{"branch": "agent/governance-agent/regress2"}\n' \
  > "$WS_A/.omo/_delivery/branch-claims/regress2.json"
out2="$(call_fn "$WS_A" 'post_merge_release regress2 agent/governance-agent/regress2 /nonexistent/ws-regress2; printf "rc=%d\n" $?')"
printf '%s' "$out2" | grep -q "rc=1" || { printf '%s\n' "$out2" | tail -6; fail "移除失败时应返回 1"; }
[ -f "$WS_A/.omo/_delivery/branch-claims/regress2.json" ] || fail "移除失败却删了 claim (应保留)"
echo "  ✅ rc=1 且 claim 保留"

# ── B: 镜像同步成功路径 ─────────────────────────────────────────────────
echo ""
echo "── B: sync_local_main_best_effort 成功路径 ⇒ rc=0 静默 ──"
WS_B="$(setup synced syncok)"
outb="$(call_fn "$WS_B" 'sync_local_main_best_effort; printf "rc=%d\n" $?')"
printf '%s' "$outb" | grep -q "rc=0" || { printf '%s\n' "$outb" | tail -6; fail "成功路径未返回 0"; }
printf '%s' "$outb" | grep -q "本地镜像未同步" && fail "成功路径不应告警"
echo "  ✅ rc=0 且无告警"
[ "$(git -C "$WS_B" rev-parse main)" = "$(git -C "$WS_B" rev-parse origin/main)" ] \
  || fail "成功路径后 main 未与 origin/main 对齐"
echo "  ✅ main 已与 origin/main 对齐"

# ── B2: 镜像同步失败路径 (本地 main 分叉 + 远端不可达) ───────────────────
echo ""
echo "── B2: 分叉 + 远端不可达 ⇒ rc≠0, 有诊断, main 不变 ──"
WS_C="$(setup diverged drift)"
MAIN_BEFORE="$(git -C "$WS_C" rev-parse main)"
outc="$(cd "$WS_C" && env "${GITENV[@]}" WS_ROOT="$WS_C" ROOT_REMOTE=origin \
  GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.proxy GIT_CONFIG_VALUE_0=http://127.0.0.1:9 \
  GIT_TERMINAL_PROMPT=0 GAC_WORKTREE_LIB_ONLY=1 \
  bash -c 'source "$1" >/dev/null 2>&1; set +e; sync_local_main_best_effort; printf "rc=%d\n" $?' _ "$SCRIPT" 2>&1)"
printf '%s' "$outc" | grep -q "rc=0" && { printf '%s\n' "$outc" | tail -6; fail "分叉+不可达时应失败"; }
printf '%s' "$outc" | grep -q "本地镜像未同步" || fail "缺未同步诊断"
printf '%s' "$outc" | grep -q "领先 origin/main" || fail "缺领先/落后计数"
printf '%s' "$outc" | grep -q "不会 reset" || fail "缺『不会 reset』承诺"
echo "  ✅ rc≠0 + 诊断齐全"
[ "$MAIN_BEFORE" = "$(git -C "$WS_C" rev-parse main)" ] || fail "本地 main 被改动 —— 禁止破坏性回退"
echo "  ✅ 本地 main 逐字节未变"

# ── D: 守卫提示 helper (release/merge 共用) ──────────────────────────────
echo ""
echo "── D: print_dirty_worktree_hints 报错即给解法 ──"
[ "$(grep -cF 'print_dirty_worktree_hints "$wt"' "$SCRIPT")" = "2" ] \
  || fail "release + merge 两处守卫都应接线 print_dirty_worktree_hints"
echo "  ✅ 接线: release + merge 两处"

# 夹具: 带一个**真实子模块**的 superproject (脏项只有子模块层才会出现)
WS_D="$TMP/ws-hint"
git init -q --bare -b main "$TMP/hint-child.git"
git init -q -b main "$TMP/hint-child"
printf 'x\n' > "$TMP/hint-child/f.txt"
git -C "$TMP/hint-child" add f.txt
git -C "$TMP/hint-child" -c user.email=t@example.invalid -c user.name=t commit -qm c
git -C "$TMP/hint-child" push -q "$TMP/hint-child.git" main
git init -q -b main "$WS_D"
git -C "$WS_D" -c protocol.file.allow=always submodule add -q "$TMP/hint-child.git" child
git -C "$WS_D" -c user.email=t@example.invalid -c user.name=t commit -qm add-sub

# D1 干净态: 不得误报
outd="$(call_fn "$WS_D" 'print_dirty_worktree_hints "$FIXTMP/ws-hint"; printf "rc=%d\n" $?')"
printf '%s' "$outd" | grep -q "rc=0" || { printf '%s\n' "$outd" | tail -8; fail "helper 非零退出"; }
printf '%s' "$outd" | grep -q "(无; 脏项在主仓 tracked 层" || fail "干净态误报子模块脏项"
echo "  ✅ 干净态: rc=0 且不误报"

# D2 脏态: 必须带子模块名 (--quiet 缺陷的回归守卫)
printf 'changed\n' >> "$WS_D/child/f.txt"
git -C "$WS_D" diff --quiet \
  && fail "夹具无效: 未构造出子模块脏态 (本用例将失去判别力)"
git -C "$WS_D" status --porcelain --untracked-files=no | grep -q '^ M child' \
  || fail "夹具无效: 主仓层面看不到子模块脏项"
outd2="$(call_fn "$WS_D" 'print_dirty_worktree_hints "$FIXTMP/ws-hint"; printf "rc=%d\n" $?')"
printf '%s' "$outd2" | grep -q "child: " \
  || { printf '%s\n' "$outd2" | tail -8; fail "脏项未带子模块名 —— --quiet 缺陷回归"; }
printf '%s' "$outd2" | grep -q " M f.txt" || fail "缺子模块层脏项明细"
printf '%s' "$outd2" | grep -q "checkout -- uv.lock" || fail "缺『uv.lock』自清命令"
printf '%s' "$outd2" | grep -q "submodule update --init" || fail "缺『未同步检出』自清命令"
printf '%s' "$outd2" | grep -q "reset --hard -q" || fail "缺『坏 index』自清命令"
echo "  ✅ 脏态: 带子模块名 + 四类自清命令齐全"

echo ""
echo "✅ merge 清理加固回归: PASS"
