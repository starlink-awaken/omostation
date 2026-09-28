---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-28
type: ssot
id: ADR-0460
related: ADR-0456, ADR-0249, ADR-0453
---


# ADR-0460 — 决策吞吐机制：每周批量决策会 + 默认否决权

- **Status**: ACCEPTED（2026-09-28 principal 会话内批准「同意」，针对"每周批量决策会 + 默认否决权"机制的明确表态）
- **Date**: 2026-09-28
- **Related**: ADR-0456（治理降档）、ADR-0249（预算）、ADR-0453（鸿沟定性）、BRIEF 决策收件箱

## 背景与问题

1. BRIEF 自诊断"人类决策是当前系统瓶颈"；2026-09-27/28 会话实证：单会话内
   principal 决策等待点 ≥5 处（纪要位置/基线数字/KOS 权威源/降档批准/工作簿批注），
   决策散落在行动包、周报、债务文件各处，无单一视图。
2. 并发 agent 数 10+，每个会话独立向 principal 拉决策——决策带宽是全系统最稀缺资源。
3. 本会话验证了两个有效模式：**判定工作簿**（agent 预填建议，principal 批注式决策，
   成本从每条数分钟降到数秒）与**会话内即时批准自动留痕**（"同意，go" → decision_ref）。

## 决策（principal 2026-09-28 批准）

1. **每周批量决策会**：principal 每周一次批量处理决策收件箱（BRIEF 待决卡片一屏）。
   节奏由 principal 自定（建议每周首个工作会话）；会期外 agent 不催办。
2. **默认否决权（default-with-veto）**：低风险决策项由 agent 预填建议并标注
   「默认按建议执行」；批量决策会上 principal 逐条 **否决或确认**；会期后 7 天内
   未否决的默认项**按建议执行**（决策留痕自动生成 decision_ref）。
3. **单一视图**：所有等待 principal 的决策统一进 BRIEF「待决策收件箱」，
   每卡带建议与默认行为；不再散落各交付物内。
4. **决策留痕自动化**：会话内口头批准（如"同意"/"签发"/"go"）由执行 agent 转写为
   decision_ref + 回执（先例：ADR-0456 批准、T4-02 签发回执）。

## 适用边界（硬边界，不因本 ADR 松动）

- **human_gate: true 的 BET**、**破坏性操作**、**隐私敏感内容处理**、
  **ADR 强制生效**：不适用默认否决权，仍须 principal 显式批准；
- 债务 gate_level=gate 的项不进默认通道；
- D1-D6 纪律、三轴证据、A2A 锁等既有门禁全部不变；
- 默认执行的每项仍产生完整证据链（事后可审计、可回滚）。

## 首批默认项（本 ADR 附带生效）

| 项 | 默认 | 来源 |
|---|---|---|
| DEBT-20260927-KOS-HOME-DUAL-AUTHORITY | 建议 (a) data/kos 为权威源，~/.kos 降级导出物 | T3-03 实证 |
| DEBT-20260927-RUN-REGISTRY-RACE | 建议 run 文件按会话分目录（方案 a） | 本会话覆写实证 |
| TOOL-GRAPHQL-FLAKY 收尾 | 建议 clone-lifecycle 实战 shadow 后关单 | T10-08 交付 |
| 3 条 AGENTS.md pitfall 增补 | 已执行（#4510） | 复盘固化 |

## 风险与回滚

- 默认执行的项若事后被 principal 否决：按各交付物的 rollback 路径回退（均为可回滚项）；
- 7 天超时若过短/过长，批量决策会第一次月度回顾时调整；
- 回滚 = 本 ADR 改 SUPERSEDED，已执行项逐一评估（均留有完整证据链）。

## 效果度量（下季度回顾）

- 决策收件箱积压 ≤3 张（常态）；
- principal 决策耗时 ≤30 分钟/周；
- 默认执行项的事后否决率 ≤20%（过高 = 建议质量差，需回炉 agent 判定环节）。
