#!/usr/bin/env bash
# Single entry point for submodule pointer closure.
#
# Flow:
#   1. acquire a root-level transaction lock
#   2. push submodule commits so gitlinks are reachable
#   3. verify root gitlinks are reachable from submodule origins
#   4. stage submodule pointers and optionally commit the root bump
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

commit_msg=""
dry=0
changed_from="${SUBMODULE_POINTER_BASE_REF:-}"
incremental=1

while [ "$#" -gt 0 ]; do
  case "$1" in
    --message|-m)
      commit_msg="${2:-}"
      shift 2
      ;;
    --dry-run)
      dry=1
      shift
      ;;
    --changed-from)
      changed_from="${2:-}"
      [ -n "$changed_from" ] || { echo "--changed-from requires a ref" >&2; exit 2; }
      shift 2
      ;;
    --all)
      changed_from=""
      incremental=0
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$incremental" = "1" ] && [ -z "$changed_from" ]; then
  if git rev-parse --verify --quiet "upstream/main^{commit}" >/dev/null; then
    changed_from="upstream/main"
  else
    changed_from="origin/main"
  fi
fi

if [ "$dry" = "0" ] && ! git diff --cached --quiet; then
  echo "index must be clean before a submodule pointer transaction" >&2
  echo "commit or unstage existing changes; the transaction will stage only its own gitlinks" >&2
  exit 2
fi

stage_paths=()
if [ -n "$changed_from" ]; then
  if ! git rev-parse --verify --quiet "${changed_from}^{commit}" >/dev/null; then
    echo "incremental base is not resolvable: $changed_from (use --all for a full transaction)" >&2
    exit 2
  fi
  if ! git diff --quiet "$changed_from" -- .gitmodules; then
    echo ".gitmodules changed; incremental staging is unsafe (rerun with --all)" >&2
    exit 2
  fi
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    if ! git diff --quiet "$changed_from" -- "$path"; then
      stage_paths+=("$path")
    fi
  done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')
else
  while IFS= read -r path; do
    [ -n "$path" ] && stage_paths+=("$path")
  done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')
  if ! git diff --quiet HEAD -- .gitmodules; then
    stage_paths+=(".gitmodules")
  fi
fi

lock="$(git rev-parse --path-format=absolute --git-path "submodule-pointer-transaction.lock")"
if ! mkdir "$lock" 2>/dev/null; then
  echo "❌ another submodule pointer transaction is active: $lock" >&2
  exit 1
fi
staged_by_transaction=0
cleanup() {
  status=$?
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "$staged_by_transaction" = "1" ]; then
    git restore --staged -- "${stage_paths[@]}" >/dev/null 2>&1 || true
  fi
  rmdir "$lock" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT

echo "== submodule pointer transaction =="
if [ "$dry" = "1" ]; then
  bash "$ROOT/bin/ssot/sync-submodules-push.sh" --dry-run
  gate_args=(--source worktree --require-main)
  if [ -n "$changed_from" ]; then
    gate_args+=(--changed-from "$changed_from")
  fi
  python3 "$ROOT/bin/ssot/submodule-reachability-gate.py" "${gate_args[@]}"
  exit 0
fi

bash "$ROOT/bin/ssot/sync-submodules-push.sh"
gate_args=(--source worktree --fetch --require-main)
if [ -n "$changed_from" ]; then
  gate_args+=(--changed-from "$changed_from")
fi
python3 "$ROOT/bin/ssot/submodule-reachability-gate.py" "${gate_args[@]}"

if [ "${#stage_paths[@]}" -gt 0 ]; then
  staged_by_transaction=1
  git add -- "${stage_paths[@]}"
fi
python3 "$ROOT/bin/change-lane-check.py" --staged
python3 "$ROOT/bin/ssot/ssot-guardian.py"

if git diff --cached --quiet; then
  # 「没有差集」与「有差集但本脚本不处理」必须分开说 —— 后者才是调用者真正卡住的形态。
  stale=0
  stale_list=""
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    # 未 init 的子模块: git -C 会向上解析到父仓 (AGENTS.md §7), 必须先验 toplevel。
    # 两个坑: ① $path 相对仓根而 --show-toplevel 返回绝对路径; ② macOS 上 /var 是
    # /private/var 的符号链接, --show-toplevel 给**物理路径**, 与 $ROOT 的字面路径不等
    # (实测: 直接 `= "$ROOT/$path"` 恒假 ⇒ 所有子模块被静默跳过)。故两侧都取物理路径。
    abs="$ROOT/$path"
    toplevel="$(git -C "$abs" rev-parse --show-toplevel 2>/dev/null || true)"
    physical="$(cd "$abs" 2>/dev/null && pwd -P || true)"
    [ -n "$toplevel" ] && [ "$toplevel" = "$physical" ] || continue
    pin="$(git ls-tree HEAD "$path" | awk '{print $3}')"
    head="$(git -C "$abs" rev-parse -q --verify origin/main 2>/dev/null || true)"
    if [ -n "$pin" ] && [ -n "$head" ] && [ "$pin" != "$head" ]; then
      stale=$((stale + 1))
      stale_list="${stale_list}  - ${path}: pin=${pin:0:9} origin/main=${head:0:9}"$'\n'
    fi
  done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')
  echo "no root submodule pointer changes to commit（本脚本未 stage 任何 gitlink）"
  if [ "$stale" -gt 0 ]; then
    echo "⚠️  但检测到 ${stale} 个子模块的 gitlink 落后于各自 origin/main —— 本脚本的增量模式"
    echo "    只处理「子仓本地有未推送 commit」这一形态（按它找差集），这种要走手动 bump："
    printf '%s' "$stale_list"
    echo "      git update-index --cacheinfo 160000,<origin/main 的 sha>,<path>"
    echo "      git commit -m 'chore(gitlink): bump <path> …'"
    echo "    （先 git -C <path> fetch origin main 让本地 origin/main 指向该 sha，"
    echo "      submodule-guard 的 fast-forward 判定才有「对齐 origin/main」分支放行）"
  fi
  exit 0
fi

if [ -n "$commit_msg" ]; then
  git commit -m "$commit_msg"
  staged_by_transaction=0
else
  echo "staged submodule pointers; pass --message to commit automatically"
fi
