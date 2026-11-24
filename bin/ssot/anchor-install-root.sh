#!/usr/bin/env bash
# anchor-install-root.sh — 把运行时安装位重锚到指定 SHA (ADR-0456 B4a/B4b)
#
# 为什么需要它: ADR-0456 §5 明确「锚点改为落位时记录的 SHA」——安装位是 detached
# 在某个 SHA 上的独立 clone, 而检出根每天都在往前走。没有重锚, 常驻族 6 条
# runtime_root=install 的服务会**静默跑旧代码** (代码根解耦了, 没人提醒)。
#
# 参考基准是 **origin/main**, 不是检出根 HEAD (2026-11-17 修): ADR-0456 §5 原文是
# 「detached 在**记录在案的 `origin/main` SHA**」, 而检出根 (`~/Workspace`) 是
# **读平面**, 可能任意陈旧 —— 实测该检出停在 `db1b13813` (比锚点旧 7 天), 于是
# 旧实现报「锚点落后 0 个提交」并同时说「常驻族在跑旧代码」, 而真实读数是
# **落后 origin/main 206 个提交**; 更危险的是默认重锚目标也是检出根 HEAD,
# 照做会把安装位**往回降级**。
#
# 用法:
#   bin/ssot/anchor-install-root.sh                    # 重锚到 origin/main
#   bin/ssot/anchor-install-root.sh <sha|ref>          # 重锚到指定 SHA/引用
#   bin/ssot/anchor-install-root.sh --status           # 只报当前锚点, 不改
#   bin/ssot/anchor-install-root.sh --check            # 锚点落后 origin/main 时 exit 1 (供 cron/巡检用)
#
# 降级防护: 目标是当前锚点的祖先时拒绝执行 (exit 5), 需要时用
# ANCHOR_ALLOW_DOWNGRADE=1 显式放行。
#
# 只读检视之外的动作: fetch + checkout --detach + submodule sync。不启停任何服务
# (服务切路径是 B4b 的事, 由 gen-service-configs.py --write + launchctl 换)。
set -euo pipefail

INSTALL_ROOT="${OMOSTATION_INSTALL_ROOT:-$HOME/.local/opt/omostation}"
CHECKOUT="${OMOSTATION_CHECKOUT:-$HOME/Workspace}"
DEFAULT_REF="origin/main"

if [[ ! -d "$INSTALL_ROOT/.git" ]]; then
  echo "安装位不存在或不是 git 仓: $INSTALL_ROOT" >&2
  exit 2
fi

current_anchor() { git -C "$INSTALL_ROOT" rev-parse HEAD 2>/dev/null || echo "(none)"; }

CHECK_ONLY=0
case "${1:-}" in
  --status)
    echo "install_root:  $INSTALL_ROOT"
    echo "anchor_sha:    $(current_anchor)"
    echo "anchor_date:   $(git -C "$INSTALL_ROOT" log -1 --format=%ci 2>/dev/null || echo '-')"
    echo "origin_main:   $(git -C "$INSTALL_ROOT" rev-parse "$DEFAULT_REF" 2>/dev/null || echo '-')"
    echo "checkout_sha:  $(git -C "$CHECKOUT" rev-parse HEAD 2>/dev/null || echo '-') (读平面, 仅参考)"
    if [[ -f "$INSTALL_ROOT/runtime/release-manifest.json" ]]; then
      echo "manifest:      $INSTALL_ROOT/runtime/release-manifest.json"
    fi
    exit 0
    ;;
  --manifest)
    manifest_file=""
    if [[ -f "$INSTALL_ROOT/runtime/release-manifest.json" ]]; then
      manifest_file="$INSTALL_ROOT/runtime/release-manifest.json"
    elif [[ -f "$CHECKOUT/runtime/release-manifest.json" ]]; then
      manifest_file="$CHECKOUT/runtime/release-manifest.json"
    fi
    if [[ -n "$manifest_file" && -f "$manifest_file" ]]; then
      cat "$manifest_file"
      exit 0
    else
      echo "❌ 尚未生成 release-manifest.json (请先运行 anchor-install-root.sh 发布)" >&2
      exit 1
    fi
    ;;
  --check)
    CHECK_ONLY=1
    ;;
esac

target="${1:-}"
if [[ -z "$target" || "$target" == "--check" ]]; then
  target="$DEFAULT_REF"
fi
cur="$(current_anchor)"

# target 可能是分支名 (如 origin/main) 而非 40 位 SHA。若直接 cat-file, 命中的是
# **本地远端跟踪引用** —— 它可能是陈旧的, 于是下面「取不到就 fetch」的分支被整段跳过,
# checkout 静默落在旧码上, 而脚本还会报「完成」。
# 2026-11-09 实证: 安装位 origin/main 停在 8fb45cfb3 (= #5176), 而 origin/main 实为
# 5cec6612a; `anchor-install-root.sh origin/main` 打印「HEAD is now at 8fb45cfb3」并
# 报完成, 常驻族继续跑 6 个 PR 之前的代码 —— 正是本脚本存在的理由被自己复刻了一遍。
# 故: 分支名一律先 fetch 刷新, 再解析成 SHA。fetch 失败不静默 (见下)。
# 2026-11-17: 这段从「仅重锚路径」提前到 --check 之前 —— 否则 --check 用的还是
# 那个陈旧引用, 读数与重锚目标会不一致。
if ! [[ "$target" =~ ^[0-9a-f]{40}$ ]]; then
  echo "-- target 是引用 ($target): 先刷新远端跟踪引用"
  fetch_ok=0
  git -C "$INSTALL_ROOT" fetch origin >/dev/null 2>&1 && fetch_ok=1
  git -C "$INSTALL_ROOT" fetch "$CHECKOUT" main >/dev/null 2>&1 && fetch_ok=1
  if [[ "$fetch_ok" != 1 ]]; then
    echo "fetch 全部失败 —— 拒绝用可能陈旧的本地 ref (避免静默跑旧码)" >&2
    exit 4
  fi
  resolved="$(git -C "$INSTALL_ROOT" rev-parse "$target" 2>/dev/null || true)"
  if [[ -z "$resolved" ]]; then
    echo "引用解析失败: $target" >&2
    exit 3
  fi
  echo "-- 解析为 SHA: $resolved"
  target="$resolved"
fi

checkout_sha="$(git -C "$CHECKOUT" rev-parse HEAD 2>/dev/null || echo '-')"

if [[ "$CHECK_ONLY" = 1 ]]; then
  if [[ "$cur" == "$target" ]]; then
    echo "锚点一致 origin/main: $cur"
    exit 0
  fi
  behind=$(git -C "$INSTALL_ROOT" rev-list --count "${cur}..${target}" 2>/dev/null || echo "?")
  ahead=$(git -C "$INSTALL_ROOT" rev-list --count "${target}..${cur}" 2>/dev/null || echo "?")
  days=$(( ( $(date +%s) - $(git -C "$INSTALL_ROOT" log -1 --format=%ct 2>/dev/null || date +%s) ) / 86400 ))
  if [[ "$behind" != "0" && "$behind" != "?" ]]; then
    echo "锚点落后 origin/main ${behind} 个提交 (锚点距今 ${days} 天): 锚点=$cur 目标=$target"
    echo "  检出根 HEAD=$checkout_sha (读平面, 仅参考 —— 安装位按 ADR-0456 §5 锚在 origin/main SHA)"
    echo "  → 常驻族在跑旧代码; 重锚: bin/ssot/anchor-install-root.sh"
    exit 1
  fi
  echo "锚点 ($cur) 不落后于 origin/main ($target): behind=${behind} ahead=${ahead}"
  echo "  检出根 HEAD=$checkout_sha (读平面, 仅参考)"
  exit 0
fi

# 降级防护: 目标比当前锚点更旧 ⇒ 照做会把常驻族**往回**切。
# 默认参考既是 origin/main, 这条正常情况下不会触发; 触发即说明有人显式传了旧 SHA。
if [[ "${ANCHOR_ALLOW_DOWNGRADE:-0}" != "1" && "$target" != "$cur" ]] && git -C "$INSTALL_ROOT" merge-base --is-ancestor "$target" "$cur" 2>/dev/null; then
  echo "拒绝: 目标 $target 是当前锚点 $cur 的祖先 —— 重锚会**降级**安装位." >&2
  echo "  若确实要回退, 用 ANCHOR_ALLOW_DOWNGRADE=1 显式放行." >&2
  exit 5
fi

echo "== 重锚安装位 =="
echo "  install_root: $INSTALL_ROOT"
echo "  current:      $cur"
echo "  target:       $target"

# 目标 SHA 可能只在检出根里 (未推 origin) —— 先试本地, 再试 origin
if ! git -C "$INSTALL_ROOT" cat-file -e "${target}^{commit}" 2>/dev/null; then
  echo "-- 从检出根取目标提交"
  git -C "$INSTALL_ROOT" fetch "$CHECKOUT" main >/dev/null 2>&1 || true
fi
if ! git -C "$INSTALL_ROOT" cat-file -e "${target}^{commit}" 2>/dev/null; then
  echo "-- 从 origin 取目标提交"
  git -C "$INSTALL_ROOT" fetch origin >/dev/null 2>&1 || true
fi
if ! git -C "$INSTALL_ROOT" cat-file -e "${target}^{commit}" 2>/dev/null; then
  echo "目标 SHA 不可达: $target" >&2
  exit 3
fi

# 工作区脏状态预检: 严禁盲目覆盖或破坏已修改的安装位状态 (-uall 确保仅含 release-manifest.json 的新 runtime/ 不折叠误判)
dirty_status="$(git -C "$INSTALL_ROOT" status --porcelain -uall 2>/dev/null | grep -vE '^\?\? runtime/release-manifest\.json$' || true)"
if [[ -n "$dirty_status" && "${ANCHOR_ALLOW_DIRTY:-0}" != "1" ]]; then
  echo "拒绝: 安装位工作区存在未提交的修改 (dirty):" >&2
  echo "$dirty_status" | head -20 >&2
  echo "  请先在 $INSTALL_ROOT 提交或丢弃改动，或使用 ANCHOR_ALLOW_DIRTY=1 显式放行。" >&2
  exit 6
fi

git -C "$INSTALL_ROOT" checkout --detach "$target" >/dev/null
echo "-- 同步子模块"
git -C "$INSTALL_ROOT" submodule update --init --recursive --no-fetch >/dev/null 2>&1 || git -C "$INSTALL_ROOT" submodule update --init --recursive >/dev/null 2>&1 || true
echo "-- 同步 omo venv (常驻族运行依赖)"
(cd "$INSTALL_ROOT/projects/omo" && uv sync --frozen >/dev/null 2>&1) || echo "   ⚠️ omo venv 同步失败 (需人工检查)"

echo "-- 生成发布溯源清单 (release-manifest.json)"
cur_anchor_sha="$(current_anchor)"
manifest_json="$(python3 -c "
import json, subprocess, sys
from datetime import datetime, timezone

install_root = sys.argv[1]
target = sys.argv[2]
cur_head = sys.argv[3]
checkout_sha = sys.argv[4]

submodules = {}
try:
    p = subprocess.run(['git', '-C', install_root, 'submodule', 'status', '--recursive'],
                       capture_output=True, text=True, check=False)
    for line in p.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            sha = parts[0].lstrip('+-U')
            name = parts[1]
            submodules[name] = sha
except Exception:
    pass

manifest = {
    'released_at': datetime.now(timezone.utc).isoformat(),
    'source_commit': target,
    'install_root': install_root,
    'install_root_sha': cur_head,
    'checkout_sha': checkout_sha,
    'producer': 'bin/ssot/anchor-install-root.sh',
    'submodule_shas': submodules,
}
print(json.dumps(manifest, indent=2))
" "$INSTALL_ROOT" "$target" "$cur_anchor_sha" "$checkout_sha")"

mkdir -p "$INSTALL_ROOT/runtime" 2>/dev/null || true
if [[ -d "$INSTALL_ROOT/runtime" ]]; then
  echo "$manifest_json" > "$INSTALL_ROOT/runtime/release-manifest.json" 2>/dev/null || true
fi

state_root="$CHECKOUT"
if [[ -f "$CHECKOUT/bin/lib/repo_root.py" ]]; then
  detected_state_root="$(python3 "$CHECKOUT/bin/lib/repo_root.py" --json 2>/dev/null | grep -o '"state_root": "[^"]*"' | cut -d'"' -f4 || true)"
  if [[ -n "$detected_state_root" && -d "$detected_state_root" ]]; then
    state_root="$detected_state_root"
  fi
fi
mkdir -p "$state_root/runtime" 2>/dev/null || true
if [[ -d "$state_root/runtime" ]]; then
  echo "$manifest_json" > "$state_root/runtime/release-manifest.json" 2>/dev/null || true
fi

echo "-- 自报校验"
(cd "$INSTALL_ROOT" && /opt/homebrew/bin/python3 bin/lib/repo_root.py --json 2>/dev/null | head -6) || true
echo "== 完成: 锚点 $(current_anchor) =="
