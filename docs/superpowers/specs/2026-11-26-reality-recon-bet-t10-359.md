---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-359
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-26
accepted: "2026-11-26 Principal 会话「继续吧，全部推进」+ AskUserQuestion 双裁定 (fullrefresh 恢复启用 / god-module 先登记 backlog)"
title: 现实对账第一批 —— resident 三条 sync-reality + fullrefresh 复活 + 双债登记
created: 2026-11-26
---

# BET-Y2Q4-T10-359: 现实对账第一批 (「全部推进」四线收口)

## 背景与问题

「全部推进」四线: T279 (blocked, unit-node-04 离线 15 天)、归档区 (孤本已
撤离, 大件删除被权限门禁拦截 → 转用户手工执行)、reality-check
预存债、god-module。本 BET 收口后两线的第一批。

1. **cron registry 三条 drift**: resident-launchd-sediment/monitor/heartbeat
   声明停在 pending/proposed, 本机 launchd 实装已久 (ADR-0396 常驻体系)。
2. **fullrefresh 声明/现实脱节**: 10-29 署名裁定「采纳官方 publisher driver
   /180s 形态」, 11-07 wave5 把 plist 改名 .disabled-wave5, launchd 域
   无此服务; 声明仍 enabled:true。plist 现哈希与 services.yaml
   content_digest 逐字节一致 (897f33b4) —— 内容从未漂移, 纯文件名停放。
3. **god-module 三红文件** 与 **services 全景三类残债** 均未立案。

## 方案 (含 owner 裁定)

1. **sync-reality 原子回写** (工具通道, 非手编): `scheduler-compile.py
   --sync-reality` 将三条 resident 的 reality/status 对齐实测
   (pending/proposed → installed/active)。dry-run 预览确认只动此三条,
   22 条 declared_only 不误伤 (多机维度保守正确)。
2. **fullrefresh 复活 (host 侧, owner 拍板「恢复启用」)**: plist 去后缀
   复名 → launchctl bootstrap → 验 RunAtLoad 即跑 + 日志复流 + 180s
   周期。声明零改动 (声明本就是署名裁定的正确形态, 修的是现实)。
3. **god-module 立债** (owner 拍板「先登记 backlog」): 三文件 + ollama.py
   缝簇候选 + 子模块PR双跳先例 + 质量优先不赶工。
4. **services 全景三类立债**: E2/E4/E5 计数入档 (sweep 时点读数), 注明
   执行时必须重新物化清单, 修复沿用 T353/T355 镜像先例。

## 验收标准

1. `scheduler-compile.py --probe-reality` mismatch_count 0 (修复后)。
2. `launchctl print gui/501/com.omostation.zhixing-projection-fullrefresh`
   state=running; 日志当日时间戳复流 (sync_step/checkout/publish 事件链)。
3. 两债条目存在且 debt.yaml seed_items 已登记 (debt-integrity 无孤儿红)。
4. 台账 607 bets + digest 绑定。

## 非目标

- E2/E4/E5 逐条修复 (全景 BET, 清单须重物化)。
- god-module 实际拆解 (backlog 已立, 新会话执行)。
- 归档区大件删除 (权限门禁, 用户手工 `!` 前缀执行递归强删)。
- T279 四腿 (节点物理开机)。

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | fullrefresh 恢复 vs 退役 | 恢复启用 | 10-29 署名裁定为在案最强权威; wave5 改名无在案决策记录; plist 与声明 digest 逐字节一致, 恢复零风险 |
| 2 | god-module 今日深度 | 先登记 backlog | 1400 行单类拆解是设计活; 长会话尾部赶工伤质量, 新会话满上下文执行第一刀 |
| 3 | resident 三条修法 | sync-reality 工具通道 | 工具自带原子回写 + dry-run 预览, 不手编 registry |
