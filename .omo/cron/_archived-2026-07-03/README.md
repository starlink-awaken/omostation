# 归档裁决 (2026-07-03 异步任务治理)

实证: 五份 crontab 源文件从未安装运行 (零 /tmp 日志·零 _delivery 产物·零 agent 日志)。
职能接管关系:
- gac-crontab (drift/validate/healthcheck/gc) → pre-commit gac-local-gate 每次提交实跑
- governance-crontab (x1-x4/debt/dashboard) → cron-service: health-scan/watchdog/dashboard-refresh
- governance-dashboard-crontab → cron-service OMO Dashboard auto-refresh (every 30m);
  另注: 其引用的 bin/gov-trend-report.py 已更名 governance-trend-report.py, 文件已死链
- governance-agent-crontab → 从未运行, 无接管方, 如需恢复经 async-tasks.yaml 登记后装
- x2-freshness-crontab → compass_radar freshness 维度 (每次健康分计算)
保留的活源: opc-closeout-crontab (8/9 已装; opc_p1_memtheta_filter 未装待裁决) · l4-governance-crontab (Documents 侧)
