#!/usr/bin/env bash
# anchor-install-root.sh — 把运行时安装位重锚到指定 SHA (ADR-0456 B4a/B4b)
#
# 为什么需要它: ADR-0456 §5 明确「锚点改为落位时记录的 SHA」——安装位是 detached
# 在某个 SHA 上的独立 clone, 而检出根每天都在往前走。没有重锚, 常驻族 6 条
# runtime_root=install 的服务会**静默跑旧代码** (代码根解耦了, 没人提醒)。
#
# 用法:
#   bin/ssot/anchor-install-root.sh                    # 重锚到检出根当前 HEAD
#   bin/ssot/anchor-install-root.sh <sha>              # 重锚到指定 SHA
#   bin/ssot/anchor-install-root.sh --status           # 只报当前锚点, 不改
#   bin/ssot/anchor-install-root.sh --check            # 检出根 HEAD != 锚点时 exit 1 (供 cron/巡检用)
#
# 只读检视之外的动作: fetch + checkout --detach + submodule sync。不启停任何服务
# (服务切路径是 B4b 的事, 由 gen-service-configs.py --write + launchctl 换)。
set -euo pipefail

INSTALL_ROOT="${OMOSTATION_INSTALL_ROOT:-$HOME/.local/opt/omostation}"
CHECKOUT="${OMOSTATION_CHECKOUT:-$HOME/Workspace}"
MARKER="docs/project-registry.yaml"

if [[ ! -d "$INSTALL_ROOT/.git" ]]; then
  echo "安装位不存在或不是 git 仓: $INSTALL_ROOT" >&2
  exit 2
fi

current_anchor() { git -C "$INSTALL_ROOT" rev-parse HEAD 2>/dev/null || echo "(none)"; }

CHECK_ONLY=0
case "${1:-}" in
  --status)
    echo "install_root: $INSTALL_ROOT"
    echo "anchor_sha:   $(current_anchor)"
    echo "anchor_date:  $(git -C "$INSTALL_ROOT" log -1 --format=%ci 2>/dev/null || echo '-')"
    echo "checkout_sha: $(git -C "$CHECKOUT" rev-parse HEAD 2>/dev/null || echo '-')"
    exit 0
    ;;
  --check)
    CHECK_ONLY=1
    ;;
esac

target="${1:-}"
if [[ -z "$target" || "$target" == "--check" ]]; then
  target="$(git -C "$CHECKOUT" rev-parse HEAD)"
fi
cur="$(current_anchor)"

if [[ "$CHECK_ONLY" = 1 ]]; then
  if [[ "$cur" == "$target" ]]; then
    echo "锚点一致: $cur"
    exit 0
  fi
  lag=$(git -C "$INSTALL_ROOT" rev-list --count "${cur}..${target}" 2>/dev/null || echo "?")
  days=$(( ( $(date +%s) - $(git -C "$INSTALL_ROOT" log -1 --format=%ct 2>/dev/null || date +%s) ) / 86400 ))
  echo "锚点落后 ${lag} 个提交 (锚点距今 ${days} 天): 锚点=$cur 目标=$target"
  echo "  → 常驻族在跑旧代码; 重锚: bin/ssot/anchor-install-root.sh"
  exit 1
fi

echo "== 重锚安装位 =="
echo "  install_root: $INSTALL_ROOT"
echo "  current:      $cur"
echo "  target:       $target"

# target 可能是分支名 (如 origin/main) 而非 40 位 SHA。若直接 cat-file, 命中的是
# **本地远端跟踪引用** —— 它可能是陈旧的, 于是下面「取不到就 fetch」的分支被整段跳过,
# checkout 静默落在旧码上, 而脚本还会报「完成」。
# 2026-11-09 实证: 安装位 origin/main 停在 8fb45cfb3 (= #5176), 而 origin/main 实为
# 5cec6612a; `anchor-install-root.sh origin/main` 打印「HEAD is now at 8fb45cfb3」并
# 报完成, 常驻族继续跑 6 个 PR 之前的代码 —— 正是本脚本存在的理由被自己复刻了一遍。
# 故: 分支名一律先 fetch 刷新, 再解析成 SHA。fetch 失败不静默 (见下)。
if ! [[ "$target" =~ ^[0-9a-f]{40}$ ]]; then
  echo "-- target 是分支名: 先刷新远端跟踪引用"
  fetch_ok=0
  git -C "$INSTALL_ROOT" fetch origin >/dev/null 2>&1 && fetch_ok=1
  git -C "$INSTALL_ROOT" fetch "$CHECKOUT" main >/dev/null 2>&1 && fetch_ok=1
  if [[ "$fetch_ok" != 1 ]]; then
    echo "fetch 全部失败 —— 拒绝用可能陈旧的本地 ref 重锚 (避免静默跑旧码)" >&2
    exit 4
  fi
  resolved="$(git -C "$INSTALL_ROOT" rev-parse "$target" 2>/dev/null || true)"
  if [[ -z "$resolved" ]]; then
    echo "分支解析失败: $target" >&2
    exit 3
  fi
  echo "-- 解析为 SHA: $resolved"
  target="$resolved"
fi

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

git -C "$INSTALL_ROOT" checkout --detach "$target" >/dev/null
echo "-- 同步子模块"
git -C "$INSTALL_ROOT" submodule update --init --recursive >/dev/null 2>&1 || true
echo "-- 同步 omo venv (常驻族运行依赖)"
(cd "$INSTALL_ROOT/projects/omo" && uv sync --frozen >/dev/null 2>&1) || echo "   ⚠️ omo venv 同步失败 (需人工检查)"

echo "-- 自报校验"
(cd "$INSTALL_ROOT" && /opt/homebrew/bin/python3 bin/lib/repo_root.py --json 2>/dev/null | head -6) || true
echo "== 完成: 锚点 $(current_anchor) =="
