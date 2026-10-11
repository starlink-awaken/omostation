#!/bin/bash
# hot-tier-resilience.sh — 4.1T 掉线盘兜底/恢复工具箱 (BET-Y2Q4-T10-243)
#
# 设计文档: docs/superpowers/specs/2026-10-11-4tb-disk-resilience-v1.md
# 数据分层: P0 配置(git) / P1 稀有(Lex 副本) / P2 公开(清单重下) / P3 冷层 / P4 可丢
#
# 子命令:
#   sync-rare         稀有发布者 → Lex 增量同步 (限速, 掉线守卫)
#   manifest          刷新公开源重建清单 (Lex + 仓内双写)
#   snapshot-links    models-active 软链清单固化
#   verify            Lex 副本抽样校验 + 清单新鲜度
#   daily-report      keepalive 掉线日报 (昨日汇总)
#   rebuild <mnt>     T3 盘死重建剧本 (稀有回灌 + 重下清单 + 软链重建)
#
# 定时 (人工安装制, 不自动注册 — 沿用 cold-backup-drill 约定):
#   每周日 04:00 sync-rare + manifest + snapshot-links + verify
#   每日   23:50 daily-report
# launchd plist 模板:
#   <dict><key>Label</key><string>com.local.hot-tier-resilience</string>
#     <key>ProgramArguments</key><array>
#       <string>/Users/xiamingxing/Workspace/bin/ops/hot-tier-resilience.sh</string>
#       <string>sync-rare</string></array>
#     <key>StartCalendarInterval</key><dict>
#       <key>Weekday</key><integer>0</integer><key>Hour</key><integer>4</integer></dict>
#     <key>StandardOutPath</key><string>/Users/xiamingxing/.local/log/hot-tier-resilience.log</string>
#     <key>StandardErrorPath</key><string>/Users/xiamingxing/.local/log/hot-tier-resilience.log</string></dict>
set -uo pipefail

HOT="/Volumes/SHAREDMODEL/lmstudio"
COLD="/Volumes/MOVESPEED/cold-models"
LEX="/Volumes/Lex/cold-backup/sharemodel-hot-tier"
OMLX="$HOME/omlx"
WS="$HOME/Workspace"
KEEPALIVE_LOG="$HOME/Library/Logs/disk-keepalive.log"
KEEPALIVE_STATE="$HOME/Library/Logs/disk-keepalive.state"
KEEPALIVE_DAILY="$HOME/Library/Logs/disk-keepalive.daily"
LOGTS() { date '+%Y-%m-%d %H:%M:%S'; }

# 公开源 (可从 HF 重下, 不做数据备份; 增改时同步更新设计文档 P2 行)
PUBLIC_PUBLISHERS=(mlx-community lmstudio-community unsloth bartowski openbmb gpustack nativ-community)

die() { echo "[$(LOGTS)] ERROR: $*" >&2; exit 1; }

# T1 掉线守卫: 热层不在线或正在掉线周期内 → 退避退出 (exit 75 = TEMPFAIL, launchd 下轮再试)
guard_hot_online() {
    local fail_count=0
    [ -f "$KEEPALIVE_STATE" ] && fail_count=$(cat "$KEEPALIVE_STATE" 2>/dev/null || echo 0)
    [ -d "$HOT" ] || die "热层 $HOT 不在线 (exit 1)"
    [ "$fail_count" -ge 5 ] && die "掉线周期中 (state=$fail_count), 退避 (launchd 将重试)"
    echo "[$(LOGTS)] 守卫通过: 热层在线, 掉线计数=$fail_count"
}

# 稀有发布者 = HOT 下不在 PUBLIC_PUBLISHERS 的目录
rare_dirs() {
    local entry is_public=0
    for entry in "$HOT"/*/; do
        entry="${entry%"${entry##*[!/]}"}"   # 去尾斜杠
        entry="${entry##*/}"
        is_public=0
        for p in "${PUBLIC_PUBLISHERS[@]}"; do
            [ "$entry" = "$p" ] && { is_public=1; break; }
        done
        [ "$is_public" -eq 0 ] && printf '%s\n' "$entry"
    done
    return 0
}

cmd_sync_rare() {
    guard_hot_online
    mkdir -p "$LEX/rare-publishers"
    local d rc=0
    while IFS= read -r d; do
        [ -z "$d" ] && continue
        rsync -a --bwlimit=40000 "$HOT/$d" "$LEX/rare-publishers/" || { echo "[$(LOGTS)] WARN: $d 同步失败"; rc=1; }
    done < <(rare_dirs)
    echo "[$(LOGTS)] sync-rare 完成 rc=$rc"
    return $rc
}

cmd_manifest() {
    guard_hot_online
    local out="$WS/docs/generated/public-models-manifest.md"
    mkdir -p "$WS/docs/generated"
    {
        echo "# SHAREDMODEL 公开源模型重建清单"
        echo "# 生成: $(LOGTS) (hot-tier-resilience.sh manifest)"
        echo "# 公开源可从 HuggingFace/LM Studio 重下; 数据体量约 545G"
        echo
        for p in "${PUBLIC_PUBLISHERS[@]}"; do
            echo "## $p"
            ls "$HOT/$p" 2>/dev/null | sed 's/^/- /'
            echo
        done
    } > "$out"
    /bin/cp -f "$out" "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md"
    echo "[$(LOGTS)] manifest 双写完成: $out + Lex"
}

cmd_snapshot_links() {
    [ -d "$OMLX/models-active" ] || die "软链农场 $OMLX/models-active 不存在"
    local out="$OMLX/conf/models-active.manifest"
    mkdir -p "$OMLX/conf"
    {
        echo "# models-active 软链农场清单 (snapshot-links $(LOGTS))"
        echo "# 格式: <相对路径> -> <目标>; 相对链原样保留"
        find "$OMLX/models-active" -type l | sort | while IFS= read -r l; do
            echo "${l#"$OMLX/models-active"/} -> $(readlink "$l")"
        done
    } > "$out"
    echo "[$(LOGTS)] 软链清单固化: $out ($(grep -c ' -> ' "$out") 链)"
}

cmd_verify() {
    local sampled=0 failed=0
    while IFS= read -r d; do
        [ -z "$d" ] && continue
        # 每发布者抽 1 个模型: 热层 vs Lex 同名文件 size+抽查 hash
        local m
        m=$(ls "$HOT/$d" 2>/dev/null | head -1)
        [ -z "$m" ] && continue
        sampled=$((sampled + 1))
        if ! diff <(cd "$HOT/$d/$m" && find . -type f -exec stat -f "%z %N" {} \; | sort) \
                 <(cd "$LEX/rare-publishers/$d/$m" 2>/dev/null && find . -type f -exec stat -f "%z %N" {} \; | sort) >/dev/null 2>&1; then
            echo "[$(LOGTS)] MISMATCH: $d/$m"
            failed=$((failed + 1))
        fi
    done < <(rare_dirs)
    echo "[$(LOGTS)] verify: 抽样 $sampled 个模型, 不一致 $failed"
    # 清单新鲜度
    local age
    age=$(( ($(date +%s) - $(stat -f %m "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md" 2>/dev/null || echo 0)) / 86400 ))
    echo "[$(LOGTS)] 清单年龄: ${age}d (RPO 承诺 ≤7d)"
    [ "$failed" -eq 0 ] || exit 1
}

cmd_daily_report() {
    local yesterday
    yesterday=$(date -v-1d '+%Y-%m-%d')
    local total remount needs
    total=$(grep -c "^\[$yesterday" "$KEEPALIVE_LOG" 2>/dev/null || echo 0)
    remount=$(grep "^\[$yesterday" "$KEEPALIVE_LOG" 2>/dev/null | grep -c "REMOUNT OK" || true)
    needs=$(grep "^\[$yesterday" "$KEEPALIVE_LOG" 2>/dev/null | grep -c "NEEDS_ATTENTION" || true)
    {
        echo "[$(LOGTS)] $yesterday 掉线日报: 异常事件行=$total REMOUNT_OK=$remount NEEDS_ATTENTION=$needs"
    } >> "$KEEPALIVE_DAILY"
    echo "[$(LOGTS)] 日报已追加 $KEEPALIVE_DAILY"
}

cmd_rebuild() {
    local mnt="${1:-}"
    [ -n "$mnt" ] && [ -d "$mnt" ] || die "用法: rebuild <新卷挂载点> (如 /Volumes/SHAREDMODEL)"
    echo "=== T3 重建剧本 ($(LOGTS)) — 目标 $mnt ==="
    echo "[1/5] 建目录结构"
    mkdir -p "$mnt/lmstudio" || die "无法创建 $mnt/lmstudio"
    echo "[2/5] P1 稀有资产回灌 (~225G, 限速 40MB/s, 可 Ctrl-C 后续跑)"
    rsync -a --bwlimit=40000 "$LEX/rare-publishers/" "$mnt/lmstudio/"
    echo "[3/5] P0 软链农场重建 (按 manifest)"
    local manifest="$OMLX/conf/models-active.manifest"
    [ -f "$manifest" ] || die "缺 $manifest — 从 git/冷备恢复 conf 后重试"
    grep ' -> ' "$manifest" | grep -v '^#' | while IFS= read -r line; do
        local rel="${line%% ->*}"; rel="${rel%% }"
        local target="${line#*-> }"
        mkdir -p "$OMLX/models-active/$(dirname "$rel")"
        ln -sfn "${target/\/Volumes\/SHAREDMODEL/$mnt}" "$OMLX/models-active/$rel"
    done
    echo "[4/5] P2 公开源重下清单 (~545G, 后台自行执行, 不阻塞):"
    /bin/cat "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md" 2>/dev/null | head -30
    echo "[5/5] 冒烟: ~/omlx/bin/omlx list && omlx serve embed-bge-m3"
    echo "=== 重建剧本执行完毕 ==="
}

case "${1:-}" in
    sync-rare)      cmd_sync_rare ;;
    manifest)       cmd_manifest ;;
    snapshot-links) cmd_snapshot_links ;;
    verify)         cmd_verify ;;
    daily-report)   cmd_daily_report ;;
    rebuild)        shift; cmd_rebuild "$@" ;;
    *) sed -n '2,30p' "$0"; exit 64 ;;
esac
