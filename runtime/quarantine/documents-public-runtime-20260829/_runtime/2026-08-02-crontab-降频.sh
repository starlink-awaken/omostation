#!/bin/bash
# ============================================================
# 2026-08-02 crontab 降频：signals-rotate 每日 → 每周一
# 用法: bash ~/Documents/_inbox/2026-08-02-crontab-降频.sh
# 作用: ①备份 crontab ②signals-rotate 改每周一 ③同步源文件 ④验证
# 安全: sed 仅命中 signals-rotate 行，其余条目（OPC/卫健委/治理等）原样保留
# ============================================================
set -e

SRC=~/Documents/@驾驶舱/_runtime/cron/l4-governance-crontab
BK=~/crontab-backup-$(date +%Y%m%d).txt

echo "======================================"
echo "[1/4] 备份当前 crontab"
echo "======================================"
crontab -l > "$BK"
echo "  ✅ 已备份 → $BK"
echo "  （恢复命令: crontab $BK）"

echo ""
echo "======================================"
echo "[2/4] 修改已安装 crontab（仅 signals-rotate 行）"
echo "======================================"
crontab -l | sed '/signals-rotate.py/s|^10 6 \* \* \*|10 6 * * 1|' | crontab -
echo "  ✅ crontab 已更新"

echo ""
echo "======================================"
echo "[3/4] 同步源文件 l4-governance-crontab"
echo "======================================"
sed -i '' '/signals-rotate.py/s|^10 6 \* \* \*|10 6 * * 1|' "$SRC"
echo "  ✅ 源文件已同步"

echo ""
echo "======================================"
echo "[4/4] 验证"
echo "======================================"
echo "--- 已安装 crontab 中的 signals-rotate ---"
crontab -l | grep signals-rotate
echo "--- 源文件中的 signals-rotate ---"
grep signals-rotate "$SRC"
echo ""
echo "✅ 完成：signals-rotate 已从每日降频为每周一 6:10"
echo "   其余治理脚本（domain-sync/bridge-refresh/session-brief/async-audit/watch-dispatch）保持每日，不受影响。"
