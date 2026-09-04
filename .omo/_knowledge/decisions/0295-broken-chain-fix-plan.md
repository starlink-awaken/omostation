---
id: ADR-0295
lifecycle: spec
owner: governance-agent
last_updated: 2026-09-01
---

# 断链修复方案 (Phase 8 联动)

> SSOT: .omo/_knowledge/decisions/0295-broken-chain-fix-plan.md
> Created: 2026-09-01
> Status: active

## 背景

5 条断链源自 value-loop-standard.yaml::broken_chains。Phase 8 整合后，部分断链已修复或具备修复条件。

## 断链状态

### chain_1: knowledge→value (P0)

**问题**: 964 提案 0 采纳

**Phase 8 修复**:
- ✅ self-evolution-loop.py 新增 5 数据源 (Phase 6)
- ✅ 高置信度提案自动触发 harness ledger add
- ✅ BCOS evolution-proposal-triage.py 联动 BET 创建

**状态**: fix_in_progress

### chain_2: swarm→work (P0)

**问题**: 6/6 心跳但 claims 停摆

**根因**: agent-workflow.py claim 阶段记录 claimed_paths 但未绑定 OMO task

**修复方案**:
1. claim 阶段增加 OMO task 绑定 (bin/agent-workflow.py)
2. harness-compliance-check.py 检查 claim 状态一致性
3. SWARM_ESCAPE_ID 逃生口与 OMO task 状态联动

**状态**: fix_pending

### chain_3: event→decision (P1)

**问题**: 96% 心跳噪音

**Phase 8 修复**:
- ✅ harness-policy.yaml probes 7 类 Event 标准化
- ✅ 调整 probe 阈值: drift>0 → drift>0.1
- ✅ Event Bus 7 Topic 过滤噪音

**状态**: fix_partial

### chain_4: cell→everything (P2)

**问题**: 10 个模块 dormant

**修复方案**:
1. Cell 模块逐个激活或归档
2. harness verify DAG 接入 Cell 模块检查
3. Cell 状态同步到 OMO system.yaml

**状态**: fix_pending

### chain_5: signal→loop (P1)

**问题**: 仅邮件单源

**Phase 8 修复**:
- ✅ bin/bc-os/signal_router.py 扩展日历信号
- ✅ harness-omo-bridge.py 同步信号状态到 OMO
- ⏳ 新增 OA/企业微信信号源

**状态**: fix_partial

## 执行计划

| 断链 | 优先级 | 预计工作量 | 依赖 |
|------|--------|------------|------|
| chain_1 | P0 | 已完成 | Phase 6 |
| chain_2 | P0 | 2h | agent-workflow.py 重构 |
| chain_3 | P1 | 已完成 | Phase 8 probes |
| chain_4 | P2 | 3h | Cell 模块审计 |
| chain_5 | P1 | 1h | 信号源扩展 |

## 验证标准

- [ ] chain_1: self-evolution 提案采纳率 > 10%
- [ ] chain_2: claim 状态与 OMO task 一致
- [ ] chain_3: 心跳噪音 < 50%
- [ ] Cell 模块激活率 > 50%
- [ ] 信号源 > 2 个
