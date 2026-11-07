#!/usr/bin/env bash
# 安装成熟度运维 cron 任务
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CRON_TAG="# omostation-maturity-ops"

# 作业表: "schedule|command" (tag 渲染时统一追加; 命令里不含竖线)。
JOBS=(
  "*/2 * * * *|cd $WORKSPACE && python3 bin/ssot/signal-poller.py --once >> .omo/logs/signal-poller.log 2>&1"
  "*/30 * * * *|cd $WORKSPACE && python3 bin/gac/remediation-engine.py --execute --strategy docs_stale >> .omo/logs/remediation.log 2>&1"
  "0 * * * *|cd $WORKSPACE && python3 bin/gac/anti-corrosion-check.py >> .omo/logs/anti-corrosion.log 2>&1"
  "0 0 * * *|cd $WORKSPACE && python3 bin/gac/unified-health-score.py >> .omo/logs/uhs.log 2>&1"
  "0 9 * * 1|cd $WORKSPACE && python3 bin/ssot/north-star-weekly.py >> .omo/logs/north-star-weekly.log 2>&1"
)

# 保留非本工具的行 (原序), 追加班表行 —— 一次渲染, 不做全表重排。
render() {
  crontab -l 2>/dev/null | grep -v "$CRON_TAG" || true
  local job
  for job in "${JOBS[@]}"; do
    echo "${job%%|*} ${job#*|} $CRON_TAG"
  done
}

# 保序去重 (替代原来的 sort -u: 那个会把用户整份 crontab 按字母重排)。
dedupe_preserve_order() {
  awk '!seen[$0]++'
}

case "${1:-}" in
  --install)
    echo "Installing maturity ops cron jobs..."
    # 一次写盘: 原实现每加一行就 `sort -u | crontab -` 全表重写一遍 (5 行 = 5 次,
    # 且每次都把整份 crontab 按字母重排)。
    render | dedupe_preserve_order | crontab -
    echo "Cron jobs installed. Use --status to verify."
    ;;
  --dry-run)
    echo "Would install (not writing):"
    render | dedupe_preserve_order
    ;;
  --remove)
    echo "Removing maturity ops cron jobs..."
    crontab -l 2>/dev/null | grep -v "$CRON_TAG" | crontab - || true
    echo "Cron jobs removed."
    ;;
  --status)
    echo "Current maturity ops cron jobs:"
    crontab -l 2>/dev/null | grep "$CRON_TAG" || echo "  (none installed)"
    ;;
  *)
    echo "Usage: $0 [--install|--dry-run|--remove|--status]"
    exit 1
    ;;
esac
