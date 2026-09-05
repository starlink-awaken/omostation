---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q3-T10-116
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T10-116 Cockpit Spine 审阅工作台 V2 与一键外发网关设计

## 1. 目标

在 Spine 现有 draft/sign 面上补齐审阅工作台闭环：左右分栏实时 Diff、
一键确认署名并经外发网关（API/SMTP 队列）真实外发、外发成功后原子
写入个人价值起搏台账。

## 2. In scope

1. `projects/cockpit/src/cockpit/commands/spine.py`（增量）：
   - `cockpit spine review`：终端左右分栏 Diff 视图（初稿 vs 当前编辑态，
     rich columns 双栏高亮），支持行级微调指令。
   - `cockpit spine send --channel api|smtp --to <addr>`：一键确认署名并
     外发——经外发网关队列（本地 spool 目录，原子写入 + 状态机
     queued/sent/failed），成功后原子写价值起搏台账（value pacing ledger）。
2. `projects/cockpit-ui/src/components/SpineReviewModal.tsx`（新文件）：
   Web 控制台审阅弹窗（左右分栏 Diff 展示 + 确认按钮），对接同一命令面。
3. 测试：review 渲染结构、send 队列状态机原子性、外发失败不写台账。

## 3. Out of scope

- 不接真实致远 OA API 凭据/SMTP 服务器（网关以 spool 队列 + 可插拔
  sender 接口交付，真实凭证属部署配置）。
- 不改 T10-105 已交付的 sign/distill/replay 路径。
- Web UI 的完整领域重组属 T8-19（已 done），本 bet 只交付单个组件。

## 4. 验收（对齐 ledger done_when）

1. `cockpit spine review` 左右分栏高亮展示初稿与编辑态实时 Diff。
2. `spine send` 一键确认署名并入外发队列（状态机完整）。
3. 外发成功后价值台账原子写入（失败回滚断言）。
4. 单测全部通过。
