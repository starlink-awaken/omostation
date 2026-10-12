#!/bin/bash
# hot-tier-resilience.sh — 4.1T 掉线盘兜底/恢复工具箱 (BET-Y2Q4-T10-243)
#
# 设计文档: docs/superpowers/specs/2026-10-11-4tb-disk-resilience-v1.md
# 数据分层: P0 配置(git) / P1 稀有(Lex 副本) / P2 公开(清单重下) / P3 冷层 / P4 可丢
#
# 子命令:
#   sync-rare         稀有发布者 → Lex 增量同步 (限速, 卷预检); 成功后记 last-sync-rare.ok
#   manifest          刷新公开源重建清单 (Lex + 仓内双写); 先写临时文件, 清单为空则不覆盖旧的
#   snapshot-links    models-active 软链清单固化
#   verify            Lex 副本抽样校验 + 清单新鲜度; 抽样为 0、读不到、清单缺失/超期都判失败
#   weekly            周任务 = sync-rare → manifest → snapshot-links → verify; 结果记 last-weekly.status, 失败桌面通知
#   daily-report      日报 (昨日): 真实掉线 + keepalive 计数 + 周任务心跳 (超期则通知并补跑)
#   rebuild <mnt>     T3 盘死重建剧本 (稀有回灌 + 重下清单 + 软链重建)
#   selftest-launchd  在 launchd 里实测两种启动方式能否读写外接卷 (直启 /bin/bash vs 经终端 App 中转)
#   install-schedule  生成周任务启动器 + plist 到暂存目录并打印安装命令 (不执行: 排程为人工安装制)
#   probe <out> [ctx] (内部) selftest 在 launchd 里执行的探针
#
# 退出码: 0 成功 / 1 校验或同步失败 / 75 卷不在线 (EX_TEMPFAIL, 稍后重试) / 77 权限被拒 (EX_NOPERM) / 64 用法
#
# ── 为什么周任务要经终端 App 启动 (2026-10-12 在 launchd 里实测) ──────────────────────────
# launchd 直接拉起的 /bin/bash 对外接卷没有『可移动卷』TCC 授权: ls / find / 写入 一律 "Operation not permitted"
# (而 [ -d ] 与 stat 照常成功 ⇒ 只靠 [ -d ] 的守卫会放行, 随后 rsync 才失败)。排程在装上后从未跑过 (runs=0),
# 这个缺口在交互终端里手测永远看不到。经终端 App 中转 (launchd → open -a iTerm → 脚本) 时, 负责进程是已获授权的
# iTerm, 读写正常。给 /bin/bash 开完全磁盘访问权限也能解, 但范围过大, 不推荐。
# 用 selftest-launchd 验证; 用 install-schedule 生成启动器/plist; 日报里的周任务心跳是兜底 (见 daily-report)。
#
# 定时 (人工安装制, 不自动注册 — 沿用 cold-backup-drill 约定):
#   每周日 04:00 周任务 (经终端 App 启动器)    每日 23:50 daily-report (不碰外接卷, launchd 直启即可)
set -uo pipefail

# 路径均可用环境变量覆盖 (默认值不变; 覆盖仅用于测试)
HOT="${HOT_TIER_HOT:-/Volumes/SHAREDMODEL/lmstudio}"
LEX="${HOT_TIER_LEX:-/Volumes/Lex/cold-backup/sharemodel-hot-tier}"
OMLX="${HOT_TIER_OMLX:-$HOME/omlx}"
WS="${HOT_TIER_WS:-$HOME/Workspace}"
SELF="${HOT_TIER_SELF:-$(cd "$(dirname "$0")" && pwd)/$(basename "$0")}"
KEEPALIVE_LOG="${KEEPALIVE_LOG:-$HOME/Library/Logs/disk-keepalive.log}"
KEEPALIVE_STATE="${KEEPALIVE_STATE:-$HOME/Library/Logs/disk-keepalive.state}"
KEEPALIVE_DAILY="${KEEPALIVE_DAILY:-$HOME/Library/Logs/disk-keepalive.daily}"
# 真实掉线记录: disk-keepalive v3 从统一日志采集 (设备从 USB 总线消失), 带"同刻消失的 SS 设备数"。
# 与 KEEPALIVE_LOG 里的"未挂载"探测计数是两回事 —— v3 之前后者在 launchd 下含大量 TCC 误报
KEEPALIVE_DROPS="${KEEPALIVE_DROPS:-$HOME/Library/Logs/disk-keepalive.drops}"
# 周任务心跳/补跑与排程相关 (状态文件放在家目录, 不在外接卷上 ⇒ launchd 直启的日报也读得到)
STATE_DIR="${HOT_TIER_STATE:-$HOME/.local/state/hot-tier-resilience}"
LOG_FILE="${HOT_TIER_LOG:-$HOME/.local/log/hot-tier-resilience.log}"
STALE_DAYS="${HOT_TIER_STALE_DAYS:-8}"
TERM_APP="${HOT_TIER_TERM_APP:-iTerm}"
LAUNCHER="${HOT_TIER_LAUNCHER:-$HOME/.local/libexec/hot-tier-weekly.command}"
STAGE_DIR="${HOT_TIER_STAGE:-$HOME/.local/share/hot-tier-resilience/staged}"
INSTALL_SELF="${HOT_TIER_INSTALL_SELF:-$HOME/Workspace/bin/ops/hot-tier-resilience.sh}"
OPEN_CMD="${HOT_TIER_OPEN_CMD:-/usr/bin/open}"
LAUNCHCTL="${HOT_TIER_LAUNCHCTL:-/bin/launchctl}"
LAUNCH_MODE="${HOT_TIER_LAUNCH_MODE:-terminal}"
LOGTS() { date '+%Y-%m-%d %H:%M:%S'; }

# 公开源 (可从 HF 重下, 不做数据备份; 增改时同步更新设计文档 P2 行)
PUBLIC_PUBLISHERS=(mlx-community lmstudio-community unsloth bartowski openbmb gpustack nativ-community)

die() { echo "[$(LOGTS)] ERROR: $*" >&2; exit 1; }

usage() { sed -n '2,/^set -uo/p' "$0" | sed '$d'; }

# ── 卷可用性: stat 不受 TCC 限制 (判"是否真挂载"), ls / 写入 才会被 TCC 拒 (判"能不能用") ──────

# 路径若在 /Volumes/<卷> 下, 要求该卷真的挂着: 挂载点与 /Volumes 本身设备号不同
# (卷掉线后残留的空目录与 /Volumes 同设备)。非 /Volumes 路径 (如测试用临时目录) 视为在线
vol_mounted() {
    case "$1" in /Volumes/*) ;; *) return 0 ;; esac
    local root
    root="/Volumes/$(printf '%s' "${1#/Volumes/}" | cut -d/ -f1)"
    [ -d "$root" ] && [ "$(stat -f %d "$root" 2>/dev/null)" != "$(stat -f %d /Volumes 2>/dev/null)" ]
}

# 目标目录可能尚未创建 (如首次同步): 往上找最近的已存在祖先
nearest_dir() {
    local q="$1"
    while [ ! -d "$q" ] && [ "$q" != "/" ]; do q=$(dirname "$q"); done
    printf '%s' "$q"
}

# 0 可读 / 75 不在线或读失败 / 77 权限被拒。stderr 说明原因
vol_check() {
    local p="$1" label="$2" err
    if ! vol_mounted "$p"; then echo "[$(LOGTS)] $label 未挂载: $p" >&2; return 75; fi
    [ -d "$p" ] || { echo "[$(LOGTS)] $label 不在线: $p 不存在" >&2; return 75; }
    # shellcheck disable=SC2012
    if ! err=$(/bin/ls "$p" 2>&1 >/dev/null); then
        case "$err" in
            *"Operation not permitted"*|*"Permission denied"*)
                echo "[$(LOGTS)] $label 权限被拒: $p — 若在 launchd 下运行, 是启动方式缺『可移动卷』TCC 授权 (见 selftest-launchd)" >&2
                return 77 ;;
            *) echo "[$(LOGTS)] $label 不可读: $err" >&2; return 75 ;;
        esac
    fi
    return 0
}

# 在目录里建删一个探针文件: 0 可写 / 75 其它失败 / 77 权限被拒
vol_writable() {
    local f err
    f="$1/.hot-tier-probe.$$"
    if err=$( { : > "$f"; } 2>&1 ); then rm -f "$f"; return 0; fi
    case "$err" in *"Operation not permitted"*|*"Permission denied"*) return 77 ;; *) return 75 ;; esac
}

# 桌面通知: 同一 key 6 小时内最多一次; 失败不影响主流程。HOT_TIER_NO_NOTIFY=1 关闭 (测试用)
notify() {
    [ "${HOT_TIER_NO_NOTIFY:-0}" = 1 ] && return 0
    local stamp now mt msg
    stamp="$STATE_DIR/notified.$1"
    mkdir -p "$STATE_DIR" 2>/dev/null || return 0
    now=$(date +%s); mt=$(stat -f %m "$stamp" 2>/dev/null || echo 0)
    [ $((now - mt)) -lt 21600 ] && return 0
    : > "$stamp"
    msg="${2//\"/}"; msg="${msg//\\/}"   # AppleScript 字符串里不能有未转义的引号/反斜杠
    osascript -e "display notification \"$msg\" with title \"hot-tier-resilience\"" >/dev/null 2>&1 || true
}

# 状态戳: <epoch> <说明>; 日报的心跳读它
stamp_ok() { mkdir -p "$STATE_DIR" && printf '%s %s\n' "$(date +%s)" "${2:-}" > "$STATE_DIR/$1.ok"; }

# T1 掉线守卫: 热层不在线 / 无权限 / 正在掉线周期内 → 退避退出 (75 = TEMPFAIL, 77 = NOPERM)
guard_hot_online() {
    local fail_count=0 rc=0
    [ -f "$KEEPALIVE_STATE" ] && fail_count=$(cat "$KEEPALIVE_STATE" 2>/dev/null || echo 0)
    vol_check "$HOT" 热层 || { rc=$?; exit "$rc"; }
    if [ "$fail_count" -ge 5 ]; then
        echo "[$(LOGTS)] 掉线周期中 (state=$fail_count), 退避 (稍后重试)" >&2
        exit 75
    fi
    echo "[$(LOGTS)] 守卫通过: 热层在线, 掉线计数=$fail_count"
}

# 备份盘守卫: Lex 真挂着, 且最近的已存在祖先目录可写
guard_lex_writable() {
    local d rc=0
    vol_mounted "$LEX" || { echo "[$(LOGTS)] Lex 未挂载: $LEX" >&2; exit 75; }
    d=$(nearest_dir "$LEX")
    vol_writable "$d" || { rc=$?; echo "[$(LOGTS)] Lex 不可写 (rc=$rc): $d" >&2; exit "$rc"; }
}

# 稀有发布者 = HOT 下不在 PUBLIC_PUBLISHERS 的目录
rare_dirs() {
    local entry is_public=0
    for entry in "$HOT"/*/; do
        entry="${entry%"${entry##*[!/]}"}"   # 去尾斜杠
        entry="${entry##*/}"
        [ -d "$HOT/$entry" ] || continue      # 读不到热层时 glob 不展开, 字面量 "*" 会被当成发布者
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
    guard_lex_writable
    mkdir -p "$LEX/rare-publishers" || die "无法创建 $LEX/rare-publishers"
    local d rc=0 n=0
    while IFS= read -r d; do
        [ -z "$d" ] && continue
        n=$((n + 1))
        rsync -a --bwlimit=40000 "$HOT/$d" "$LEX/rare-publishers/" || { echo "[$(LOGTS)] WARN: $d 同步失败"; rc=1; }
    done < <(rare_dirs)
    # 一个稀有发布者目录都没有 = 热层读空了 (而不是"没有要同步的"), 不能记成功
    [ "$n" -gt 0 ] || { echo "[$(LOGTS)] ERROR: 热层下没有任何稀有发布者目录, 不记成功" >&2; return 1; }
    echo "[$(LOGTS)] sync-rare 完成 rc=$rc 目录数=$n"
    [ "$rc" -eq 0 ] && stamp_ok last-sync-rare "dirs=$n"
    return $rc
}

cmd_manifest() {
    guard_hot_online
    guard_lex_writable
    local out="$WS/docs/generated/public-models-manifest.md" tmp entries p
    tmp=$(mktemp "${TMPDIR:-/tmp}/hot-tier-manifest.XXXXXX") || die "mktemp 失败"
    {
        echo "# SHAREDMODEL 公开源模型重建清单"
        echo "# 生成: $(LOGTS) (hot-tier-resilience.sh manifest)"
        echo "# 公开源可从 HuggingFace/LM Studio 重下; 数据体量约 545G"
        echo
        for p in "${PUBLIC_PUBLISHERS[@]}"; do
            echo "## $p"
            /bin/ls "$HOT/$p" 2>/dev/null | sed 's/^/- /'
            echo
        done
    } > "$tmp"
    # 读不到热层时 ls 静默失败, 会得到只有标题的空清单; 先校验再覆盖, 否则会把 Lex 上好的旧清单冲掉
    entries=$(grep -c '^- ' "$tmp" || true)
    if [ "${entries:-0}" -lt 1 ]; then rm -f "$tmp"; die "清单为空 (热层不可读或公开源目录缺失), 保留旧清单不覆盖"; fi
    mkdir -p "$WS/docs/generated"
    /bin/cp -f "$tmp" "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md" && /bin/cp -f "$tmp" "$out" || { rm -f "$tmp"; die "清单写入失败"; }
    rm -f "$tmp"
    stamp_ok last-manifest "entries=$entries"
    echo "[$(LOGTS)] manifest 双写完成: $out + Lex (${entries} 条)"
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

# 一个模型目录的文件清单 (大小 + 相对路径, 排序); 目录读不到时输出为空
dir_listing() { (cd "$1" 2>/dev/null && find . -type f -exec stat -f "%z %N" {} \; | sort); }

cmd_verify() {
    guard_hot_online
    vol_check "$LEX" Lex副本 || exit $?
    local sampled=0 failed=0 d m rel a b
    while IFS= read -r d; do
        [ -z "$d" ] && continue
        # 每发布者抽 1 个模型: 热层 vs Lex 同名文件 size+抽查 hash
        m=$(/bin/ls "$HOT/$d" 2>/dev/null | head -1)
        [ -z "$m" ] && continue
        # 直接放在 lmstudio/ 下的平铺模型目录 (如 Qwen3-Embedding-…) 里第一个条目是文件而不是模型目录:
        # 此时目录本身就是模型, 比对整个目录。否则两边的 cd 都失败、输出都为空、diff 判"一致",
        # 这类目录就被静默地当成已校验 (2026-10-11 实测: "cd: …/added_tokens.json: Not a directory")
        if [ -d "$HOT/$d/$m" ]; then rel="$d/$m"; else rel="$d"; fi
        sampled=$((sampled + 1))
        a=$(dir_listing "$HOT/$rel")
        b=$(dir_listing "$LEX/rare-publishers/$rel")
        # 热层这一侧读不到任何文件时, 两边都为空也会"一致" —— 同一类静默假通过, 必须单独判失败
        if [ -z "$a" ]; then
            echo "[$(LOGTS)] UNREADABLE: 热层 $rel 读不到任何文件"
            failed=$((failed + 1))
        elif [ "$a" != "$b" ]; then
            echo "[$(LOGTS)] MISMATCH: $rel"
            failed=$((failed + 1))
        fi
    done < <(rare_dirs)
    echo "[$(LOGTS)] verify: 抽样 $sampled 个模型, 不一致 $failed"
    # 抽样为 0 不是"没有不一致", 是"什么都没校验" (launchd 下读不到卷时曾在此处 exit 0)
    if [ "$sampled" -eq 0 ]; then
        echo "[$(LOGTS)] ERROR: 抽样为 0, 没有校验任何东西, 不能当作通过" >&2
        failed=$((failed + 1))
    fi
    # 清单新鲜度
    local mt age
    mt=$(stat -f %m "$LEX/PUBLIC-MODELS-REBUILD-MANIFEST.md" 2>/dev/null || echo 0)
    age=$(( ($(date +%s) - mt) / 86400 ))
    if [ "$mt" -eq 0 ]; then
        echo "[$(LOGTS)] ERROR: Lex 上没有重建清单" >&2
        failed=$((failed + 1))
    elif [ "$age" -gt 7 ]; then
        echo "[$(LOGTS)] ERROR: 清单年龄 ${age}d 超过 RPO 承诺 7d" >&2
        failed=$((failed + 1))
    else
        echo "[$(LOGTS)] 清单年龄: ${age}d (RPO 承诺 ≤7d)"
    fi
    [ "$failed" -eq 0 ] || exit 1
    stamp_ok last-verify "sampled=$sampled"
}

# 周任务: 步骤顺序固定, 遇到第一个失败就停; 无论成败都记 last-weekly.status (STATE STEP RC EPOCH)
cmd_weekly() {
    local step rc=0
    mkdir -p "$STATE_DIR" || die "无法创建状态目录 $STATE_DIR"
    printf 'RUNNING - 0 %s\n' "$(date +%s)" > "$STATE_DIR/last-weekly.status"
    for step in sync-rare manifest snapshot-links verify; do
        echo "[$(LOGTS)] weekly >>> $step"
        bash "$SELF" "$step"; rc=$?
        if [ "$rc" -ne 0 ]; then
            printf 'FAIL %s %s %s\n' "$step" "$rc" "$(date +%s)" > "$STATE_DIR/last-weekly.status"
            notify weekly-fail "周同步在 $step 失败 (rc=$rc): 详见 $LOG_FILE"
            echo "[$(LOGTS)] weekly 失败于 $step rc=$rc"
            return "$rc"
        fi
    done
    printf 'OK - 0 %s\n' "$(date +%s)" > "$STATE_DIR/last-weekly.status"
    stamp_ok last-weekly "4 步全部通过"
    echo "[$(LOGTS)] weekly 全部完成"
}

# last-weekly.status (STATE STEP RC EPOCH) → 人话, 如 "FAIL sync-rare rc=77 @ 2026-10-18 04:00:03"
fmt_status() {
    local st step rc ts
    read -r st step rc ts <<< "${1:-}"
    case "${ts:-}" in ''|*[!0-9]*) printf '%s' "${1:-无记录}"; return 0 ;; esac
    if [ "$st" = FAIL ]; then printf '%s %s rc=%s @ %s' "$st" "$step" "$rc" "$(date -r "$ts" '+%F %T')"
    else printf '%s @ %s' "$st" "$(date -r "$ts" '+%F %T')"; fi
}

# 周任务心跳: 距上次整链成功的天数, 从未成功打印 -1。只读状态目录, 不碰外接卷
weekly_age_days() {
    local f="$STATE_DIR/last-weekly.ok" ts
    [ -f "$f" ] || { echo -1; return 0; }
    ts=$(awk '{print $1}' "$f" 2>/dev/null)
    case "$ts" in ''|*[!0-9]*) echo -1; return 0 ;; esac
    echo $(( ($(date +%s) - ts) / 86400 ))
}

# 补跑: 只在两个卷都挂着 (stat 判断, 不受 TCC 影响)、启动器存在、且 20 小时内没尝试过时,
# 经终端 App 拉起启动器。launchd 直启的日报自己读不了外接卷, 所以只能"叫醒"有授权的那条路
weekly_catchup() {
    [ "${HOT_TIER_AUTO_CATCHUP:-1}" = 1 ] || return 0
    if ! { vol_mounted "$HOT" && vol_mounted "$LEX"; }; then
        echo "[$(LOGTS)] 补跑跳过: 热层或 Lex 未挂载"; return 0
    fi
    if [ ! -x "$LAUNCHER" ]; then
        echo "[$(LOGTS)] 补跑跳过: 启动器 $LAUNCHER 不存在 (先 install-schedule 并按提示安装)"; return 0
    fi
    local last=0
    [ -f "$STATE_DIR/last-weekly.status" ] && last=$(awk '{print $4}' "$STATE_DIR/last-weekly.status")
    case "$last" in ''|*[!0-9]*) last=0 ;; esac
    if [ $(( $(date +%s) - last )) -lt 72000 ]; then
        echo "[$(LOGTS)] 补跑跳过: 20 小时内已尝试过"; return 0
    fi
    echo "[$(LOGTS)] 补跑周任务: $OPEN_CMD -g -j -a $TERM_APP $LAUNCHER"
    "$OPEN_CMD" -g -j -a "$TERM_APP" "$LAUNCHER" || echo "[$(LOGTS)] 补跑启动失败 rc=$?"
}

cmd_daily_report() {
    local day="${1:-$(date -v-1d '+%Y-%m-%d')}"
    local total unmounted remount needs maint drops_n drops_detail note="" age hb status stale=0
    # grep -c 0 命中时自己会打印 0 且退出 1; 别再接 `|| echo 0`, 否则变量是 "0\n0" 把日报行折断
    total=$(grep -c "^\[$day" "$KEEPALIVE_LOG" 2>/dev/null || true)
    unmounted=$(grep "^\[$day" "$KEEPALIVE_LOG" 2>/dev/null | grep -c "未挂载" || true)
    remount=$(grep "^\[$day" "$KEEPALIVE_LOG" 2>/dev/null | grep -c "REMOUNT OK" || true)
    needs=$(grep "^\[$day" "$KEEPALIVE_LOG" 2>/dev/null | grep -c "NEEDS_ATTENTION" || true)
    maint=$(grep "^\[$day" "$KEEPALIVE_LOG" 2>/dev/null | grep -c "MAINT:" || true)
    # 真实掉线 = 设备从 USB 总线消失 (disk-keepalive v3 从统一日志采集), 附"同刻消失的 SS 设备数":
    # >1 为整条 hub 链路一起掉, =1 为只有盘自己
    drops_n=$(grep -c "^$day .*REAL_DROP" "$KEEPALIVE_DROPS" 2>/dev/null || true)
    drops_detail=$(grep "^$day .*REAL_DROP" "$KEEPALIVE_DROPS" 2>/dev/null | sed -E 's/.*ss_removed=([0-9]+).*/\1/' | paste -sd, - || true)
    # v3 (2026-10-11 16:07) 之前, keepalive 在 launchd 下因缺『可移动卷』TCC 授权把每个周期都判成"未挂载"
    [[ "$day" < "2026-10-12" ]] && note=" [2026-10-11 16:07 前的 keepalive 计数含 TCC 误报, 以真实掉线为准]"
    echo "[$(LOGTS)] $day 掉线日报: 真实掉线=${drops_n:-0}${drops_detail:+ (同刻消失SS设备数: $drops_detail)} | keepalive 日志行=${total:-0} 未挂载探测=${unmounted:-0} REMOUNT_OK=${remount:-0} NEEDS_ATTENTION=${needs:-0} MAINT=${maint:-0}$note" >> "$KEEPALIVE_DAILY"
    # 周任务心跳: 周任务本身在终端 App 里跑、可能根本没起来 (装上后从未跑过的排程曾无人知晓), 由日报兜底发现
    age=$(weekly_age_days)
    status=$(fmt_status "$(cat "$STATE_DIR/last-weekly.status" 2>/dev/null)")
    if [ "$age" -lt 0 ]; then hb="从未整链成功"; stale=1
    elif [ "$age" -gt "$STALE_DAYS" ]; then hb="上次整链成功 ${age}d 前 (超过 ${STALE_DAYS}d)"; stale=1
    else hb="上次整链成功 ${age}d 前"; fi
    echo "[$(LOGTS)] $day 周任务心跳: $hb | 最近一次: $status" >> "$KEEPALIVE_DAILY"
    echo "[$(LOGTS)] 日报已追加 $KEEPALIVE_DAILY"
    if [ "$stale" -eq 1 ]; then
        notify weekly-stale "周同步心跳异常: $hb"
        weekly_catchup
    fi
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

# ── launchd 实测与排程生成 ────────────────────────────────────────────────────────────

# (内部) 在 launchd 里被 selftest 拉起: 把热层可读性与 Lex 可写性写进 <out>
cmd_probe() {
    local out="${1:?用法: probe <out> [ctx]}" ctx="${2:-manual}" hot=0 wr=0
    vol_check "$HOT" 热层 >/dev/null 2>&1 || hot=$?
    vol_mounted "$LEX" || wr=75
    [ "$wr" -eq 0 ] && { vol_writable "$(nearest_dir "$LEX")" || wr=$?; }
    printf 'PROBE ctx=%s hot=%s lex_write=%s time=%s\n' "$ctx" "$hot" "$wr" "$(LOGTS)" >> "$out"
}

xml_escape() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

# probe 输出行是否表示"热层可读且 Lex 可写"
probe_ok() { case "$1" in *" hot=0 lex_write=0 "*) return 0 ;; *) return 1 ;; esac; }

# plist 骨架: <label> <out_log> <program arg…>; 调用方追加其它键后自己闭合 </dict></plist>
plist_head() {
    local label="$1" log="$2" a; shift 2
    printf '<?xml version="1.0" encoding="UTF-8"?>\n'
    printf '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    printf '<plist version="1.0"><dict>\n  <key>Label</key><string>%s</string>\n  <key>ProgramArguments</key><array>\n' "$(xml_escape "$label")"
    for a in "$@"; do printf '    <string>%s</string>\n' "$(xml_escape "$a")"; done
    printf '  </array>\n  <key>StandardOutPath</key><string>%s</string>\n  <key>StandardErrorPath</key><string>%s</string>\n' "$(xml_escape "$log")" "$(xml_escape "$log")"
}

ST_LABELS=""; ST_WORK=""; ST_UID=""
selftest_cleanup() {
    local l
    for l in $ST_LABELS; do "$LAUNCHCTL" bootout "gui/$ST_UID/$l" >/dev/null 2>&1; done
    [ -n "$ST_WORK" ] && rm -rf "$ST_WORK"
    return 0
}

# 在 launchd 用户域里用一次性任务实测: 直启 /bin/bash 与经终端 App 中转, 各自能否读热层、写 Lex
cmd_selftest_launchd() {
    local mode label out plist launcher waited timeout="${HOT_TIER_SELFTEST_TIMEOUT:-60}" line res_direct="" res_term=""
    ST_UID=$(id -u)
    ST_WORK=$(mktemp -d "${TMPDIR:-/tmp}/hot-tier-selftest.XXXXXX") || die "mktemp 失败"
    trap selftest_cleanup EXIT INT TERM
    for mode in direct terminal; do
        label="com.local.hot-tier-selftest-$mode-$$"
        out="$ST_WORK/$mode.out"; plist="$ST_WORK/$mode.plist"
        if [ "$mode" = direct ]; then
            { plist_head "$label" "$ST_WORK/$mode.log" /bin/bash "$SELF" probe "$out" direct
              printf '  <key>RunAtLoad</key><true/>\n</dict></plist>\n'; } > "$plist"
        else
            launcher="$ST_WORK/probe-launcher.command"
            printf '#!/bin/bash\nexec /bin/bash "%s" probe "%s" terminal\n' "$SELF" "$out" > "$launcher"; chmod 755 "$launcher"
            { plist_head "$label" "$ST_WORK/$mode.log" "$OPEN_CMD" -g -j -a "$TERM_APP" "$launcher"
              printf '  <key>RunAtLoad</key><true/>\n</dict></plist>\n'; } > "$plist"
        fi
        plutil -lint "$plist" >/dev/null 2>&1 || die "生成的 plist 不合法: $plist"
        ST_LABELS="$ST_LABELS $label"
        "$LAUNCHCTL" bootstrap "gui/$ST_UID" "$plist" || die "launchctl bootstrap 失败 ($mode)"
        waited=0
        while ! grep -q '^PROBE' "$out" 2>/dev/null && [ "$waited" -lt "$timeout" ]; do sleep 1; waited=$((waited + 1)); done
        line=$(grep '^PROBE' "$out" 2>/dev/null | head -1)
        "$LAUNCHCTL" bootout "gui/$ST_UID/$label" >/dev/null 2>&1
        if [ -z "$line" ]; then line="PROBE ctx=$mode 无输出 (等待 ${timeout}s 超时; 看 $ST_WORK/$mode.log)"; fi
        if [ "$mode" = direct ]; then res_direct="$line"; else res_term="$line"; fi
    done
    echo "== selftest-launchd ($(LOGTS)) 热层=$HOT  Lex=$LEX"
    echo "  直启 /bin/bash : $res_direct"
    echo "  经 $TERM_APP 中转: $res_term"
    local chosen="$res_term"
    [ "$LAUNCH_MODE" = direct ] && chosen="$res_direct"
    if probe_ok "$chosen"; then
        echo "结论: 配置的启动方式 ($LAUNCH_MODE) 可读热层、可写 Lex —— 通过"
        if [ "$LAUNCH_MODE" = terminal ] && ! probe_ok "$res_direct"; then
            echo "      (直启失败是预期: launchd 直拉的 /bin/bash 缺『可移动卷』TCC 授权, 所以周任务必须经终端 App)"
        fi
        return 0
    fi
    echo "结论: 配置的启动方式 ($LAUNCH_MODE) 未通过" >&2
    if [ "$LAUNCH_MODE" = terminal ]; then
        echo "      终端 App「$TERM_APP」可能没有『可移动卷』授权: 在它里面手动访问一次外接卷并点允许, 或改 HOT_TIER_TERM_APP" >&2
    fi
    return 1
}

# 生成启动器与 plist 到暂存目录并打印安装命令。不执行 launchctl: 排程为人工安装制 (BET non_goals)
cmd_install_schedule() {
    local plist_label=com.local.hot-tier-resilience staged_plist staged_launcher
    mkdir -p "$STAGE_DIR" || die "无法创建暂存目录 $STAGE_DIR"
    staged_launcher="$STAGE_DIR/hot-tier-weekly.command"
    staged_plist="$STAGE_DIR/$plist_label.plist"
    {
        echo '#!/bin/bash'
        echo '# 由 hot-tier-resilience.sh install-schedule 生成。周任务启动器: launchd → open -a 终端 App → 本脚本。'
        echo '# 为什么不让 launchd 直接跑脚本: 见 hot-tier-resilience.sh 头部「为什么周任务要经终端 App 启动」。'
        printf 'mkdir -p "%s"\n' "$(dirname "$LOG_FILE")"
        printf '/bin/bash "%s" weekly >> "%s" 2>&1\n' "$INSTALL_SELF" "$LOG_FILE"
        echo 'exit $?'
    } > "$staged_launcher"
    chmod 755 "$staged_launcher"
    if [ "$LAUNCH_MODE" = direct ]; then
        plist_head "$plist_label" "$LOG_FILE" /bin/bash "$INSTALL_SELF" weekly > "$staged_plist"
    else
        plist_head "$plist_label" "$LOG_FILE" "$OPEN_CMD" -g -j -a "$TERM_APP" "$LAUNCHER" > "$staged_plist"
    fi
    printf '  <key>StartCalendarInterval</key><dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>4</integer><key>Minute</key><integer>0</integer></dict>\n</dict></plist>\n' >> "$staged_plist"
    plutil -lint "$staged_plist" >/dev/null 2>&1 || die "生成的 plist 不合法: $staged_plist"
    echo "已生成 (未安装):"
    echo "  启动器: $staged_launcher"
    echo "  plist : $staged_plist"
    if [ -f "$HOME/Library/LaunchAgents/$plist_label.plist" ]; then
        echo "与当前已装 plist 的差异:"
        diff -u "$HOME/Library/LaunchAgents/$plist_label.plist" "$staged_plist" | sed 's/^/    /' || true
    fi
    echo "确认无误后手动安装 (顺序不能换: 先放启动器, 再换 plist):"
    echo "  install -d \"$(dirname "$LAUNCHER")\" && install -m 755 \"$staged_launcher\" \"$LAUNCHER\""
    echo "  cp \"$staged_plist\" \"$HOME/Library/LaunchAgents/$plist_label.plist\""
    echo "  launchctl bootout gui/\$(id -u)/$plist_label 2>/dev/null; launchctl bootstrap gui/\$(id -u) \"$HOME/Library/LaunchAgents/$plist_label.plist\""
    echo "  bash \"$INSTALL_SELF\" selftest-launchd   # 装好后实测一遍"
}

case "${1:-}" in
    sync-rare)         cmd_sync_rare ;;
    manifest)          cmd_manifest ;;
    snapshot-links)    cmd_snapshot_links ;;
    verify)            cmd_verify ;;
    weekly)            cmd_weekly ;;
    daily-report)      shift; cmd_daily_report "$@" ;;   # 可选参数: YYYY-MM-DD (默认昨天), 用于补报
    rebuild)           shift; cmd_rebuild "$@" ;;
    selftest-launchd)  cmd_selftest_launchd ;;
    install-schedule)  cmd_install_schedule ;;
    probe)             shift; cmd_probe "$@" ;;
    *) usage; exit 64 ;;
esac
