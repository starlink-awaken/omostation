---
schema_version: specification/v1
spec_version: 1.0.0
title: Digital-brain pipeline supervisor (resident execute)
bet_id: BET-Y1Q4-T2-05
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-02
last-reviewed: 2026-09-02
type: ssot
last_updated: 2026-09-03
---

# Digital-brain pipeline supervisor (T2-05)

## Intent

全管线（雷达→总线→嵌入→渲染）注册为 Resident Agent execute 角色常驻：
定时通道（每日 07:30 全链晨报）+ 文件监听通道（~/Inbox/ocr-inbound/ 新扫描件
→OCR→嵌入→待办卡片）。单站失败降级续跑 + 告警进 convergence-pulse health。

## Architecture (KISS)

```
projects/omo/src/omo/pipeline_supervisor.py（supervisor 本体，纯编排层）
├─ MorningChain (定时通道, launchd 07:30 触发 --tick-morning)
│   1. radar   : python3 bin/bc-os/policy_radar.py --generate-morning-brief
│   2. bus     : brief items → PriorityEventBus 事件流记录 (jsonl 追加)
│   3. embed   : 晨报条目 encode 入 .omo/state/pipeline-vectors.jsonl
│                (Mac mini embed node 远程优先, 失败降级本地 omlxc)
│   4. render  : brief md → cockpit render docx (GB/T 版, 失败不阻塞)
│   每站 try/except → station_states{ok|degraded:reason}, 全链不中断
├─ WatchInbound (文件监听, --watch)
│   ~/Inbox/ocr-inbound/ 新图 → agora ocr extract → 嵌入 →
│   .omo/state/im-triage/pipeline-*.json 卡片 → cockpit im-triage 渲染
├─ state 面板 (--status): 读 .omo/state/pipeline-supervisor-state.json
└─ 告警: degraded/failed → state.json alerts[] → convergence-pulse
   collect_health 第四源 (pipeline_supervisor)

resident-routes.yaml: PipelineTick 事件路由 (execute 角色, safe: false —
  外发类动作必须人工在场? 不 — 本站产物全部落盘不外发, safe: true)
launchd: com.omostation.pipeline-morning (日历 07:30, RunAtLoad false)
```

## Station contracts (done_when 映射)

1. resident-routes 注册 + resident status 可查 → routes PipelineTick 条目
2. 定时通道连续 3 天真实晨报 → state.json morning_runs[] 逐日记录（真实闸门, 跨天观察）
3. 文件监听真实扫描件全链 → inbound_runs[] 记录 OCR/嵌入/卡片产物路径
4. 单站 kill 降级续跑 → station_states 断言 + health 告警可见

## Degradation (circuit_breaker)

单站失败标记 degraded 续跑下游可行站（radar 挂则晨报用缓存；embed 远程挂
降级本地；render 挂保 brief md）。全链告警写 state alerts + pulse health。

## Verify (BET contract)

- make resident-status → supervisor 路由可见
- make gac-local-gate → exit 0
