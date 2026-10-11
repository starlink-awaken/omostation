---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: jarvis-seat
last-reviewed: '2026-10-11'
bet_id: BET-Y2Q4-T10-244
spec_version: 1.0.0
---

# 贾维斯感知面 Spec v1.0.0

## Goal
常驻 agent 工作的可感知化: observer 每日日报、SwiftBar 常驻/待办域、CI 失败自动提醒、双机 todo 同步。交付物主体在 local-ops 个人仓 (observer-daily.py / agent-live / todo 域 / todo-sync / capability-catalog.py), 本仓承载台账立项与治理登记。

## Done When
- observer 日报连续 7 天 cron 自动生成 (证据: .omo/_delivery/observability/daily/)
- SwiftBar agent-live + todo 域双机 bar-lint PASS
- CI FAIL → reminders 闭环实测 (受控演练 2026-10-11: 2 FAIL 检出写入, 已验证)
- todo-sync 双机一致且幂等 (2026-10-11 首跑验证)

## Verification
- `bash ~/.config/menubar/bar-lint.sh` 双机 PASS
- `python3 ~/local-ops/bin/observer-daily.py --no-workflow` exit 0
