#!/bin/bash
# omlxc 使用统计报表
# 用法: bash scripts/usage-stats.sh

DB="$HOME/.config/omlxc/state.db"

echo "=== omlxc 使用统计 ==="
echo ""

echo "--- 总体指标 ---"
sqlite3 "$DB" "SELECT
  '总推理请求: ' || COUNT(*) FROM request_metrics;
SELECT
  '成功请求: ' || SUM(success) || ' (' || ROUND(AVG(success)*100, 1) || '%)' FROM request_metrics;
SELECT
  '平均延迟: ' || ROUND(AVG(latency_ms), 0) || 'ms' FROM request_metrics WHERE success=1;
"
echo ""

echo "--- 最近 7 天请求趋势 ---"
sqlite3 "$DB" "SELECT
  DATE(observed_at) as day,
  COUNT(*) as requests,
  ROUND(AVG(latency_ms), 0) as avg_latency_ms
FROM request_metrics
WHERE observed_at > DATETIME('-7 days')
GROUP BY day
ORDER BY day;
"
echo ""

echo "--- 路由决策统计 (Top 10) ---"
sqlite3 "$DB" "SELECT
  selected_placement_id,
  COUNT(*) as times_selected
FROM route_audits
WHERE selected_placement_id IS NOT NULL
GROUP BY selected_placement_id
ORDER BY times_selected DESC
LIMIT 10;
"
echo ""

echo "--- Job 状态 ---"
sqlite3 "$DB" "SELECT
  kind,
  state,
  COUNT(*) as count
FROM jobs
GROUP BY kind, state
ORDER BY kind, state;
"
echo ""

echo "--- 库存高水位 ---"
sqlite3 "$DB" "SELECT * FROM inventory_high_water;"
