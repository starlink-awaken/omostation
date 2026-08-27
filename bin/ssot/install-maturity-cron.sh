#!/usr/bin/env bash
# 安装成熟度运维 cron 任务
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CRON_TAG="# omostation-maturity-ops"

case "${1:-}" in
  --install)
    echo "Installing maturity ops cron jobs..."
    (crontab -l 2>/dev/null; echo "*/2 * * * * cd $WORKSPACE && python3 bin/ssot/signal-poller.py --once >> .omo/logs/signal-poller.log 2>&1 $CRON_TAG") | sort -u | crontab -
    (crontab -l 2>/dev/null; echo "*/30 * * * * cd $WORKSPACE && python3 bin/gac/remediation-engine.py --execute --strategy docs_stale >> .omo/logs/remediation.log 2>&1 $CRON_TAG") | sort -u | crontab -
    (crontab -l 2>/dev/null; echo "0 * * * * cd $WORKSPACE && python3 bin/gac/anti-corrosion-check.py >> .omo/logs/anti-corrosion.log 2>&1 $CRON_TAG") | sort -u | crontab -
    (crontab -l 2>/dev/null; echo "0 0 * * * cd $WORKSPACE && python3 bin/gac/unified-health-score.py >> .omo/logs/uhs.log 2>&1 $CRON_TAG") | sort -u | crontab -
    (crontab -l 2>/dev/null; echo "0 9 * * 1 cd $WORKSPACE && python3 bin/ssot/north-star-weekly.py >> .omo/logs/north-star-weekly.log 2>&1 $CRON_TAG") | sort -u | crontab -
    echo "Cron jobs installed. Use --status to verify."
    ;;
  --remove)
    echo "Removing maturity ops cron jobs..."
    crontab -l 2>/dev/null | grep -v "$CRON_TAG" | crontab -
    echo "Cron jobs removed."
    ;;
  --status)
    echo "Current maturity ops cron jobs:"
    crontab -l 2>/dev/null | grep "$CRON_TAG" || echo "  (none installed)"
    ;;
  *)
    echo "Usage: $0 [--install|--remove|--status]"
    exit 1
    ;;
esac
