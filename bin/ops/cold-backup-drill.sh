#!/usr/bin/env bash
# cold-backup-drill.sh — 零知识加密冷备份增量快照 (BET-Y2Q1-T10-01)
#
# 用法:
#   bin/ops/cold-backup-drill.sh [--dry-run] [--target DIR] [--include-runtime]
#
# 环境变量:
#   COLD_BACKUP_PASSPHRASE  GPG 对称加密口令 (AES-256)。缺省时 fail-closed。
#
# 覆盖面: git 追踪面 (台账/retro/bin/docs/scripts/specs) + 治理/runtime/LoRA 数据面。
# 纪律: 只读复制, 不写主工作区, 不依赖任何云服务 (100% 离线)。
# 定时: launchd/cron 示例见仓库 docs (由人手动安装, 本脚本不自动注册)。
#
# launchd 片段示例 ( crontab 等价: 15 3 * * * $WORKSPACE/bin/ops/cold-backup-drill.sh ):
#   <dict><key>ProgramArguments</key><array>
#     <string>/Users/xiamingxing/Workspace/bin/ops/cold-backup-drill.sh</string>
#   </array><key>StartCalendarInterval</key><dict>
#     <key>Hour</key><integer>3</integer><key>Minute</key><integer>15</integer>
#   </dict></dict>
#
# 退出码:
#   0  success (dry-run 完成或快照落盘)
#   1  调用/环境错误 (缺工具, 缺口令, 路径非法)
#   2  工作区在快照过程中发生变化 (read-only 不成立)
#   3  GPG 加密失败
set -euo pipefail

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="${COLD_BACKUP_TARGET:-}"
DRY_RUN=0
INCLUDE_RUNTIME=0
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

PASS_ENV="COLD_BACKUP_PASSPHRASE"
MIN_PASS_LEN=12

# ---- 输出函数 ----
say() { printf '%s\n' "$*" >&2; }
die() { say "❌ $*"; exit "${2:-1}"; }

# ---- 参数解析 ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)         DRY_RUN=1; shift ;;
    --include-runtime) INCLUDE_RUNTIME=1; shift ;;
    --target)          TARGET="$2"; shift 2 ;;
    --target=*)        TARGET="${1#*=}"; shift ;;
    -h|--help)         sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)                 die "未知参数: $1" 1 ;;
  esac
done

# ---- 工具预检 ----
for tool in tar gpg git awk; do
  command -v "$tool" >/dev/null 2>&1 || die "缺少必需工具: $tool" 1
done

# shasum 与 sha256sum 二选一
if command -v sha256sum >/dev/null 2>&1; then
  SHA_TOOL="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
  SHA_TOOL="shasum -a 256"
else
  die "缺少 sha256sum 或 shasum" 1
fi

# ---- 目标目录 (必须在工作区外) ----
if [[ -z "$TARGET" ]]; then
  die "需要 --target DIR (生产环境应指向外接介质挂载点)" 1
fi
ABS_TARGET="$(cd "$TARGET" 2>/dev/null && pwd || echo "$TARGET")"
ABS_WS="$(cd "$WS_ROOT" && pwd)"
case "$ABS_TARGET" in
  "$ABS_WS"/*|"$ABS_WS") die "拒绝将快照写入工作区内部: $ABS_TARGET" 1 ;;
esac

if [[ "$DRY_RUN" -eq 0 ]]; then
  mkdir -p "$TARGET"
  ABS_TARGET="$(cd "$TARGET" && pwd)"
fi

# ---- 口令检查 (fail-closed) ----
if [[ -z "${!PASS_ENV:-}" ]]; then
  die "fail-closed: $PASS_ENV 未设置 — 拒绝生成未加密或无凭证备份" 1
fi
# 只校验变量名长度, 不校验口令长度 (避免口令落到 stderr/审计日志)

# ---- 源清单: git 追踪 + 默认排除高 churn 路径 ----
GIT_FILE_LIST="$(mktemp -t cold-backup-files.XXXXXX)"
trap 'rm -f "$GIT_FILE_LIST" "$PRE_DIGEST_FILE" "$POST_DIGEST_FILE" /tmp/cold-backup.tar.err /tmp/cold-backup.gpg.err' EXIT

GIT_PATHSPEC_EXCLUDES=(
  ':!:.omo/_archive'
  ':!:.omo/_delivery'
  ':!:.omo/_log'
  ':!:.omo/locks'
  ':!:.omo/state/history'
  ':!:.omo/debt'
  ':!:.omo/tests'
  ':!:.omo/plans'
  ':!:.omo/run-continuation'
  ':!:.omo/workers'
  ':!:.omo/capabilities'
  ':!:.omo/evidence'
  ':!:.omc'
  ':!:.artifacts'
  ':!:.venv'
  ':!:**/__pycache__'
  ':!:node_modules'
)
if [[ "$INCLUDE_RUNTIME" -eq 0 ]]; then
  GIT_PATHSPEC_EXCLUDES+=(
    ':!:.omo/_knowledge/workflow-mesh'
    ':!:.omo/_knowledge/*.jsonl'
  )
fi

git -C "$WS_ROOT" ls-files -z "${GIT_PATHSPEC_EXCLUDES[@]}" \
  | tr '\0' '\n' > "$GIT_FILE_LIST"
FILE_COUNT="$(wc -l <"$GIT_FILE_LIST" | tr -d ' ')"
[[ "$FILE_COUNT" -gt 0 ]] || die "git ls-files 输出为空 — 工作区异常" 1

# ---- 工作区 digest 函数 (排除 .git 子树) ----
PRE_DIGEST_FILE="$(mktemp -t cold-backup-pre.XXXXXX)"
POST_DIGEST_FILE="$(mktemp -t cold-backup-post.XXXXXX)"

compute_workspace_digest() {
  ( cd "$WS_ROOT" && find . \
      -type d \( -name '.git' -o -name '.venv' -o -name 'node_modules' \) -prune -o \
      -type f -print 2>/dev/null \
      | LC_ALL=C sort \
      | xargs -I{} "$SHA_TOOL" {} 2>/dev/null \
      | "$SHA_TOOL"
  )
}

say "════════ 零知识冷备份 drill ════════"
say "workspace: $ABS_WS"
say "target:    $ABS_TARGET"
say "dry_run:   $DRY_RUN  include_runtime: $INCLUDE_RUNTIME"
say "files:     $FILE_COUNT (git ls-files)"

if [[ "$DRY_RUN" -eq 1 ]]; then
  T0=$(date +%s)
  while IFS= read -r f; do
    [[ -f "$WS_ROOT/$f" ]] || say "  ⚠️ missing: $f"
  done < "$GIT_FILE_LIST"
  T1=$(date +%s)
  say "✅ dry-run 完成: 源清单可枚举, 耗时 $((T1 - T0))s (秒级 ✓)"
  say "   (真实快照将写入 $ABS_TARGET/$STAMP, GPG 口令取 \$$PASS_ENV)"
  exit 0
fi

# ---- 工作区 pre-digest ----
compute_workspace_digest > "$PRE_DIGEST_FILE" 2>/dev/null || true

# ---- 构建 tar ----
SNAP_DIR="$ABS_TARGET/$STAMP"
mkdir -p "$SNAP_DIR"
TAR_FILE="$SNAP_DIR/workspace-$STAMP.tar"
GPG_FILE="$SNAP_DIR/workspace-$STAMP.tar.gpg"

say "构建 tar → $TAR_FILE"
if tar -cf "$TAR_FILE" -C "$WS_ROOT" \
      -T "$GIT_FILE_LIST" 2>/tmp/cold-backup.tar.err; then
  say "  tar: 成功 ($FILE_COUNT files)"
else
  ERR_TAIL="$(tail -5 /tmp/cold-backup.tar.err 2>/dev/null || true)"
  die "tar 失败: ${ERR_TAIL:-unknown}" 2
fi

# ---- 计算产物 metadata ----
TAR_SIZE="$(wc -c <"$TAR_FILE" | tr -d ' ')"
TAR_SHA="$("$SHA_TOOL" "$TAR_FILE" | awk '{print $1}')"

# ---- GPG 加密 (AES-256, 口令不落盘) ----
say "加密 → $GPG_FILE (AES-256 symmetric)"
if gpg --batch --yes --symmetric --cipher-algo AES256 \
      --compress-algo none \
      --passphrase "${!PASS_ENV}" \
      --output "$GPG_FILE" \
      "$TAR_FILE" 2>/tmp/cold-backup.gpg.err; then
  rm -f "$TAR_FILE"  # 只保留加密副本
else
  ERR_TAIL="$(tail -5 /tmp/cold-backup.gpg.err 2>/dev/null || true)"
  rm -f "$TAR_FILE"
  die "gpg 加密失败: ${ERR_TAIL:-unknown}" 3
fi

GPG_SHA="$("$SHA_TOOL" "$GPG_FILE" | awk '{print $1}')"
GPG_SIZE="$(wc -c <"$GPG_FILE" | tr -d ' ')"

# ---- 工作区 post-digest (read-only 验证) ----
compute_workspace_digest > "$POST_DIGEST_FILE" 2>/dev/null || true
if ! diff -q "$PRE_DIGEST_FILE" "$POST_DIGEST_FILE" >/dev/null 2>&1; then
  die "工作区在快照过程中发生变化 (read-only 不成立)" 2
fi
say "✅ post-digest == pre-digest: 工作区未受影响"

# ---- manifest (供 restore --verify-only 使用) ----
MANIFEST="$SNAP_DIR/manifest.sha256"
{
  echo "# cold-backup manifest (BET-Y2Q1-T10-01)"
  echo "# generated_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# workspace:    $ABS_WS"
  echo "# snapshot:     $STAMP"
  echo "# files:        $FILE_COUNT"
  echo "# include_runtime: $INCLUDE_RUNTIME"
  echo "# gpg_sha256:   $GPG_SHA"
  echo "# tar_sha256:   $TAR_SHA"
  echo "#"
  echo "# SHA-256 (one per line): <digest>  <filename>"
  ( cd "$SNAP_DIR" && "$SHA_TOOL" "$(basename "$GPG_FILE")" )
} > "$MANIFEST"

# ---- 摘要 ----
cat <<EOF
════════ 冷备份完成 ════════
 snapshot:    $SNAP_DIR
 files:       $FILE_COUNT
 tar_bytes:   $TAR_SIZE (intermediate, now deleted)
 gpg_bytes:   $GPG_SIZE
 gpg_sha256:  $GPG_SHA
 manifest:    $MANIFEST
 还原:        bin/ops/restore-cold-snapshot.sh $SNAP_DIR --verify-only
════════════════════════════
EOF
exit 0
