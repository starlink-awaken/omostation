#!/usr/bin/env bash
# restore-cold-snapshot.sh — 冷备份单键还原 (BET-Y2Q1-T10-01)
#
# 用法:
#   bin/ops/restore-cold-snapshot.sh <snapshot-dir> [--verify-only] [--dest DIR]
#
# 流程: manifest digest 校验 → (可选 GPG 解密) → 恢复 git 仓与数据面 →
#       子模块 init 提示 → 依赖 bootstrap 指令打印 (不自动执行)。
# 裸机全量重建 (环境+依赖+记忆) 目标 ≤15 分钟; 本脚本负责快照侧,
# uv/pnpm 等依赖安装按打印的 bootstrap 清单执行。
#
# 环境变量: COLD_BACKUP_PASSPHRASE (加密快照解密必需, fail-closed)。

set -euo pipefail

SNAP_DIR="${1:-}"
DEST="$(pwd)/restored"
VERIFY_ONLY=0

shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify-only) VERIFY_ONLY=1; shift ;;
    --dest) DEST="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$SNAP_DIR" || ! -d "$SNAP_DIR" ]]; then
  echo "用法: $0 <snapshot-dir> [--verify-only] [--dest DIR]" >&2
  exit 2
fi

echo "════════ 冷备份还原 $( [[ $VERIFY_ONLY -eq 1 ]] && echo '(verify-only)' ) ════════"
echo "snapshot: $SNAP_DIR"

# ── 1. manifest 校验 ──
MANIFEST="$SNAP_DIR/manifest.sha256"
if [[ ! -f "$MANIFEST" ]]; then
  echo "❌ manifest.sha256 缺失 — 快照不完整, 拒绝还原。" >&2
  exit 3
fi
( cd "$SNAP_DIR" && shasum -a 256 -c manifest.sha256 --quiet ) \
  && echo "✅ manifest digest 校验通过" \
  || { echo "❌ manifest digest 校验失败 — 快照损坏。" >&2; exit 4; }

# ── 2. 定位产物 (加密/明文) ──
ARCHIVE_GPG="$(find "$SNAP_DIR" -maxdepth 1 -name '*.tar.gpg' | head -1)"
ARCHIVE_TAR="$(find "$SNAP_DIR" -maxdepth 1 -name '*.tar' ! -name '*.gpg' | head -1)"

if [[ -n "$ARCHIVE_GPG" ]]; then
  if [[ -z "${COLD_BACKUP_PASSPHRASE:-}" ]]; then
    echo "❌ fail-closed: 加密快照需要 COLD_BACKUP_PASSPHRASE。" >&2
    exit 3
  fi
  DECRYPTED_TEMPLATE="$(mktemp -t restore-XXXXXX)"
  DECRYPTED="${DECRYPTED_TEMPLATE}.tar"
  printenv COLD_BACKUP_PASSPHRASE | gpg --batch --quiet --decrypt \
    --passphrase-fd 0 --output "$DECRYPTED" "$ARCHIVE_GPG"
  ARCHIVE_TAR="$DECRYPTED"
elif [[ -z "$ARCHIVE_TAR" ]]; then
  echo "❌ 未找到快照产物 (*.tar / *.tar.gpg)" >&2
  exit 3
fi

if [[ $VERIFY_ONLY -eq 1 ]]; then
  echo "✅ verify-only: manifest 与产物校验通过, 未落盘。"
  [[ -n "${DECRYPTED:-}" ]] && rm -f "$DECRYPTED" "${DECRYPTED_TEMPLATE:-}"
  exit 0
fi

# ── 3. 恢复 ──
mkdir -p "$DEST"
tar -xf "$ARCHIVE_TAR" -C "$DEST"
[[ -n "${DECRYPTED:-}" ]] && rm -f "$DECRYPTED" "${DECRYPTED_TEMPLATE:-}"
echo "✅ 已解包至: $DEST"

if [[ -f "$DEST/data/submodule-status.txt" ]]; then
  echo ""
  echo "📌 子模块恢复 (在 $DEST/workspace 内执行):"
  echo "   git submodule update --init"
fi

cat <<'BOOTSTRAP'

📌 裸机依赖 bootstrap 清单 (按序人工执行):
   1. 安装 Homebrew / uv / pnpm / gpg
   2. cd <restored>/workspace && uv sync && uv run --with pyyaml python bin/agent-workflow.py bootstrap
   3. projects/cockpit: uv sync && pnpm install (如涉 UI)
   4. 恢复数据面: cp -R <restored>/data/.omo <workspace>/
   5. 校验: make ssot-guardian && python3 bin/gac/meta-doctor.py --workspace . --json

BOOTSTRAP
echo "✅ 还原完成。"
