#!/bin/bash
# shareddisk-cleanup.sh — SharedDisk 满盘应急清理脚本
# 用法: 确认 /Volumes/SharedDisk 挂载后执行本脚本
# 2026-07-31

set -euo pipefail

DISK="/Volumes/SharedDisk"
LOG="$HOME/Documents/@公共/_runtime/shareddisk-cleanup.log"

if [ ! -d "$DISK" ]; then
    echo "❌ $DISK 未挂载，无法清理" | tee -a "$LOG"
    exit 1
fi

echo "=== SharedDisk 清理开始 $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
df -h "$DISK" | tee -a "$LOG"

# 1. 清理 .DS_Store
find "$DISK" -name '.DS_Store' -type f -print -delete 2>/dev/null | tee -a "$LOG" || true

# 2. 清理超过 30 天的临时/日志文件（路径根据实际结构调整）
for d in "$DISK/06_Downloads" "$DISK/07_Backup" "$DISK/logs"; do
    if [ -d "$d" ]; then
        echo "扫描旧文件: $d" | tee -a "$LOG"
        find "$d" -type f -mtime +30 -print 2>/dev/null | tee -a "$LOG" || true
        # 默认只打印，不自动删除；确认安全后取消下行注释
        # find "$d" -type f -mtime +30 -delete 2>/dev/null || true
    fi
done

# 3. 大文件清单（>1GB）
echo "--- 大于 1GB 的文件 ---" | tee -a "$LOG"
find "$DISK" -type f -size +1G -exec ls -lh {} \; 2>/dev/null | tee -a "$LOG" || true

echo "=== 清理结束 $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
df -h "$DISK" | tee -a "$LOG"
