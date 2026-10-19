#!/bin/bash
# disk-keepalive.sh — 外接SSD(SharedModel/SharedWork)保活 + 分级自愈
#
# 安全设计: 守护目标以 APFS Volume UUID 锚定(设备号会漂移, UUID 不会),
# 挂载前仍校验解析出的 whole disk 为 External, 双保险防歧义到系统卷
# (v1 2026-09-05 踩坑: 按卷名 unmount 差点碰到 disk3s5 Data 卷;
#  v2 2026-10-10: v1 硬编码 disk4 已漂移 —— disk4 现为 Model 盘, SHARED* 实际在
#  disk10, 36 次 REMOUNT FAILED + 63 次 NEEDS_ATTENTION 全为噪音。按 UUID 重锚定;
#  v3 2026-10-11: v2 的"未挂载"判定本身是误报。它用 ls 读卷内容来判断挂载, 而 launchd 下的
#  /bin/bash 没有"可移动卷"(kTCCServiceSystemPolicyRemovableVolumes)授权, ls 被拒, 于是
#  每个周期都判成未挂载并"重挂"一次。此前日志里的 未挂载/REMOUNT/NEEDS_ATTENTION 大量是这个
#  误报, 不代表真实掉线。证据: StorageKit 在重挂时记录 Mounted: Yes; rsync 从卷上连读两小时
#  无中断; 卷上 .keepalive 标记只在终端手动跑时才被更新。
#  v3 改为: 挂载状态问 DiskArbitration(diskutil info), 不读卷内容; 保活写入降为尽力而为(被拒
#  不计异常); 真实掉线另从统一日志采集到 disk-keepalive.drops, 并附同一瞬间消失的 SS 设备数:
#  >1 说明该口下不止盘一个设备同时消失(hub 链路级), =1 说明只有盘自己消失;
#  v3.1 同日: 增加维护模式开关 disk-keepalive.maintenance, 人为拔线/卸载期间暂停检测, 2 小时自动失效;
#  v3.2 同日: 真实掉线采集的回看窗口改为随距上次采集的间隔自适应 —— 维护窗口期间采集被整体跳过,
#  v3.1 的固定 90 分钟窗口在恢复后会漏记空档里的掉线)
set -uo pipefail

# 日志目录可用 KEEPALIVE_LOGDIR 覆盖(仅用于测试, launchd 下不设置)
LOGDIR="${KEEPALIVE_LOGDIR:-$HOME/Library/Logs}"
LOG="$LOGDIR/disk-keepalive.log"
STATE="$LOGDIR/disk-keepalive.state"
NEEDS_ATTENTION="$LOGDIR/disk-keepalive.NEEDS_ATTENTION"
NOTIFIED_AT="$LOGDIR/disk-keepalive.notified"
DROPS="$LOGDIR/disk-keepalive.drops"                 # 真实掉线记录(追加, 按秒去重)
DROPS_STAMP="$LOGDIR/disk-keepalive.drops.stamp"     # 上次采集的 epoch 秒
WRITE_NOTE_STAMP="$LOGDIR/disk-keepalive.writenote"  # 写入被拒的提示日期(每天最多提示一次)
V3_MARK="$LOGDIR/disk-keepalive.v3"
TS="$(date '+%Y-%m-%d %H:%M:%S')"
ESCALATE_AFTER=10
# macOS 桌面通知节流: 距上次成功通知至少 3600 秒, 恢复不重置该时间戳
NOTIFY_INTERVAL_S=3600
# 真实掉线采集: 统一日志只留约一天, 所以约每小时采一次并去重落盘
DROPS_EVERY_S=3300
DROPS_WINDOW_FIRST="20h"
DROPS_WINDOW="90m"
DISK_MATCH="DK5A1"   # 4T 扩展坞在系统日志里的名称片段(icdd 会记录 USB 设备的移除/出现)

# 守护清单: 挂载点目录名=APFS Volume UUID (来源: diskutil info <卷> | "Volume UUID")
WATCH=(
    "SharedModel=7B762734-0E1B-4E2B-92EA-D32641384578"
    "SharedWork=ABEDBB21-FAA6-46A0-BC83-1722B3CB7A3B"
)

FAIL_COUNT=0
[ -f "$STATE" ] && FAIL_COUNT=$(cat "$STATE" 2>/dev/null || echo 0)

log() { echo "[$TS] $1" >> "$LOG"; }

# 维护模式: 人为拔线/卸载盘期间暂停检测与重挂(否则 3 分钟内会被自动挂回, 拔线还会被记成真实掉线)。
# 标记文件由维护者创建、结束后删除; 超过 2 小时自动失效, 防止忘记删除而长期关闭监控。
MAINT="$LOGDIR/disk-keepalive.maintenance"
if [ -f "$MAINT" ]; then
    if [ -n "$(find "$MAINT" -mmin +120 2>/dev/null)" ]; then
        rm -f "$MAINT"
        log "MAINT: 维护标记已超过 2 小时, 自动失效, 恢复监控"
    else
        log "MAINT: 维护模式($(head -c 80 "$MAINT" 2>/dev/null | tr '\n' ' ')), 本轮跳过检测与重挂"
        exit 0
    fi
fi

# 卷是否已挂载: 问 DiskArbitration, 不读卷内容。
# (launchd 下读外接卷会被 TCC 拒绝, 见头注 v3; 查不到 UUID 即物理层不可见, 同样返回"未挂载")
vol_mounted() {
    local m
    m=$(diskutil info "$1" 2>/dev/null | awk -F': *' '/^ *Mounted:/{print $2; exit}')
    [ "$m" = "Yes" ]
}

# 保活写入: 尽力而为。launchd 下的 bash 无"可移动卷"授权时会被拒(EPERM), 这不是掉线,
# 不计入异常; 每天最多提示一次。授权后自动恢复, 无需改脚本
keepalive_write() {
    local vol="$1" err today
    if err=$( { echo "keepalive $TS" > "/Volumes/$vol/.keepalive"; } 2>&1 ); then
        return 0
    fi
    today="$(date '+%Y-%m-%d')"
    if [ "$(cat "$WRITE_NOTE_STAMP" 2>/dev/null)" != "$today" ]; then
        log "NOTE: $vol 保活写入被拒(${err##*: }), 多半是 launchd 下 bash 无『可移动卷』授权(TCC); 卷本身已确认挂载, 不计入异常"
        echo "$today" > "$WRITE_NOTE_STAMP"
    fi
    return 1
}

# 安全挂载: 按 UUID 解析设备, 确认 External 才动手; UUID 查不到即物理层不可见
safe_mount() {
    local uuid="$1" info dev_id location whole_disk
    info=$(diskutil info "$uuid" 2>/dev/null) || { log "REMOUNT SKIP: 查不到 UUID $uuid 的设备(物理层不可见), 不动手"; return 1; }
    dev_id=$(echo "$info" | awk -F': *' '/Device Identifier/{print $2}')
    location=$(echo "$info" | awk -F': *' '/Device Location/{print $2}')
    whole_disk=$(echo "$dev_id" | grep -oE '^disk[0-9]+')
    if [ -z "$whole_disk" ] || [ "$location" != "External" ]; then
        log "REMOUNT SKIP: UUID $uuid 解析到 ${dev_id:-未知}(location=$location), 非 External, 拒绝动手(防止歧义碰到系统卷)"
        return 1
    fi
    diskutil mount "$uuid" >> "$LOG" 2>&1
}

# 真实掉线采集: 设备从 USB 总线消失 = icdd 记 [Removed]。同一瞬间 bluetoothd 会逐个记
# "SS 设备从根端口移除", 数 ±2 秒内有几条: >1 为 hub 链路级, =1 为只有盘自己。
# 参数: $1=回溯窗口  $2=1 则只记录不弹通知(首次回溯)
collect_drops() {
    local win="$1" quiet="$2" icdd bt d t ts n new=0 last=""
    icdd="$(mktemp -t kadrops)"; bt="$(mktemp -t kabt)"
    /usr/bin/log show --last "$win" --style compact \
        --predicate "process == \"icdd\" AND eventMessage CONTAINS \"$DISK_MATCH\" AND eventMessage CONTAINS \"Removed\"" 2>/dev/null \
        | awk '/\[Removed\]/{print $1" "substr($2,1,8)}' | sort -u > "$icdd"
    if [ -s "$icdd" ]; then
        /usr/bin/log show --last "$win" --style compact \
            --predicate 'process == "bluetoothd" AND eventMessage CONTAINS "removed from the root hub port"' 2>/dev/null \
            | awk '/removed from the root hub port/{print $1" "substr($2,1,8)}' > "$bt"
        while read -r d t; do
            ts="$d $t"
            grep -qF "$ts " "$DROPS" 2>/dev/null && continue
            n=$(awk -v d="$d" -v t="$t" 'function s(x,a){split(x,a,":");return a[1]*3600+a[2]*60+a[3]} $1==d{x=s($2)-s(t); if(x>=-2&&x<=2)c++} END{print c+0}' "$bt")
            echo "$ts REAL_DROP $DISK_MATCH ss_removed=$n" >> "$DROPS"
            new=$((new + 1)); last="$ts, 同刻消失的 SS 设备 $n 个"
        done < "$icdd"
    fi
    rm -f "$icdd" "$bt"
    if [ "$new" -gt 0 ]; then
        log "REAL_DROP: 新记录 $new 次真实掉线, 最近一次 $last (全部记录: $DROPS)"
        if [ "$quiet" != "1" ]; then
            osascript -e "display notification \"4T 盘真实掉线 ${new} 次, 最近: ${last}\" with title \"disk-keepalive: 真实掉线\"" 2>/dev/null
        fi
    fi
}

# v3 边界标记: 只写一次, 提醒后来的读者别拿旧日志里的未挂载/REMOUNT 当真实掉线统计
if [ ! -f "$V3_MARK" ]; then
    log "NOTE: v3 起改用 diskutil 判定挂载状态; 此前日志里的 未挂载/REMOUNT/NEEDS_ATTENTION 大量是误报(见脚本头注), 勿据此统计掉线"
    echo "$TS" > "$V3_MARK"
fi

ALL_OK=1

for ENTRY in "${WATCH[@]}"; do
    VOL="${ENTRY%%=*}"
    UUID="${ENTRY#*=}"
    if vol_mounted "$UUID"; then
        keepalive_write "$VOL" || true
    else
        log "$VOL 未挂载, 尝试按 UUID 安全重挂载"
        ALL_OK=0   # 反复掉线自愈也算异常, 让计数器暴露物理层不稳
        if safe_mount "$UUID"; then
            log "REMOUNT OK: $VOL 已自动挂回"
        fi
    fi
done

if [ "$ALL_OK" = "1" ]; then
    echo 0 > "$STATE"
    rm -f "$NEEDS_ATTENTION"
else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "$FAIL_COUNT" > "$STATE"
    if [ "$FAIL_COUNT" -ge "$ESCALATE_AFTER" ]; then
        log "NEEDS_ATTENTION: 守护卷已连续 $FAIL_COUNT 次探测到未挂载(约 $((FAIL_COUNT * 3)) 分钟), 已尝试自动重挂, 需要人工检查线材/接口/供电/卷健康"
        echo "守护卷连续 $FAIL_COUNT 次探测到未挂载, 自 $TS 起需要人工介入" > "$NEEDS_ATTENTION"
        # 2026-10-11: 掉线 9 小时无人知晓(keepalive 全程自愈但只写日志)。升级为
        # macOS 桌面通知(通知中心), 两次成功通知至少间隔一小时。
        LAST_NOTIFIED=0
        [ -f "$NOTIFIED_AT" ] && LAST_NOTIFIED=$(cat "$NOTIFIED_AT" 2>/dev/null || echo 0)
        # 旧版本保存轮次数；将其视作很早的 epoch, 不伪造一次当前成功。
        case "$LAST_NOTIFIED" in ''|*[!0-9]*) LAST_NOTIFIED=0 ;; esac
        NOTIFY_NOW=$(date +%s)
        if [ $((NOTIFY_NOW - LAST_NOTIFIED)) -ge "$NOTIFY_INTERVAL_S" ] || [ "$LAST_NOTIFIED" -eq 0 ]; then
            if osascript -e "display notification \"外接盘连续 ${FAIL_COUNT} 次探测到卷未挂载(约 $((FAIL_COUNT * 3)) 分钟), 已尝试自动重挂, 请检查线材/接口\" with title \"disk-keepalive 需要关注\" sound name \"Basso\"" 2>/dev/null; then
                date +%s > "$NOTIFIED_AT"
            else
                log "NOTIFY FAILED: macOS 通知命令失败, 保留成功时间戳以便下轮重试"
            fi
        fi
    else
        log "ALERT: 守护卷异常(连续第 $FAIL_COUNT 次, 未达 $ESCALATE_AFTER 次升级阈值)"
    fi
fi

# 真实掉线采集放在最后: log show 可能耗时十几秒, 不能拖慢上面的重挂
NOW=$(date +%s)
LAST_RUN=$(cat "$DROPS_STAMP" 2>/dev/null || echo 0)
LAST_RUN=${LAST_RUN//[!0-9]/}; : "${LAST_RUN:=0}"
if [ $((NOW - LAST_RUN)) -ge "$DROPS_EVERY_S" ]; then
    if [ "$LAST_RUN" -eq 0 ]; then
        collect_drops "$DROPS_WINDOW_FIRST" 1
    else
        # 回看窗口随"距上次采集的间隔"自适应 (+30 分钟余量, 下限 DROPS_WINDOW、上限 DROPS_WINDOW_FIRST):
        # 维护窗口 / 睡眠 / launchd 故障造成的空档不能成为盲区 (v3.1 固定 90 分钟, 维护 2 小时后会漏记空档里的掉线)
        win_min=$(( (NOW - LAST_RUN) / 60 + 30 ))
        [ "$win_min" -lt "${DROPS_WINDOW%m}" ] && win_min="${DROPS_WINDOW%m}"
        [ "$win_min" -gt $(( ${DROPS_WINDOW_FIRST%h} * 60 )) ] && win_min=$(( ${DROPS_WINDOW_FIRST%h} * 60 ))
        collect_drops "${win_min}m" 0
    fi
    echo "$NOW" > "$DROPS_STAMP"
fi

if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 5000 ]; then
    tail -2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
