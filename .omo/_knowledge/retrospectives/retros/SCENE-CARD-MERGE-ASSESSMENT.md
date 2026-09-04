---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: Scene Card 变体合并评估
type: retro
---
# Scene Card 变体合并评估

> 创建: 2026-08-08 | 工具: tool-usage-audit + 人工代码审查
> 范围: bin/ssot/scene-card-* 9个变体 (~2547行)

---

## 1. 现状

| 工具 | 行数 | 功能 | 引用方 | 状态 |
|------|------|------|--------|------|
| scene-card-intake.py | 237 | 场景卡字段验证+规范化 | gen-tools-index, current-state-coherence | **KEEP** |
| scene-card-lifecycle.py | 308 | check/activate生命周期 | gen-tools-index, current-state-coherence | **KEEP** |
| scene-card-candidates.py | 229 | 候选发现 | 仅元工具 | **MERGE→intake** |
| scene-card-intake-pipeline.py | 378 | 邮件/文件/消息→结构化摄入 | 仅元工具 | **MERGE→intake** |
| scene-card-review.py | 230 | 每周复盘统计 | 仅元工具 | **MERGE→lifecycle** |
| scene-card-approval-flow.py | 314 | HITL审批流 | 仅元工具 | **MERGE→lifecycle** |
| scene-card-connector.py | 322 | IMAP/OA输入接入 | 仅元工具 | **RETIRE→iris** |
| scene-card-decision-inbox.py | 325 | 决策收件箱 | 仅元工具 | **RETIRE→intake-pipeline重叠** |
| scene-card-task-bridge.py | 204 | Scene→OMO Task桥接 | 仅元工具 | **RETIRE→journey-state-store** |

## 2. 决策

### 2.1 保留 (2个核心)
- **scene-card-intake**: 场景卡入口验证，不可替代
- **scene-card-lifecycle**: 生命周期状态机，make scene-card-check依赖

### 2.2 合并 (4个→2个)
- candidates + intake-pipeline → **合并入intake** (都是摄入管道的一部分)
- review + approval-flow → **合并入lifecycle** (都是生命周期管理)

### 2.3 退役 (3个)
- connector → iris connectors已覆盖真实输入(apple_mail/netease/seeyon_oa)
- decision-inbox → intake-pipeline功能重叠
- task-bridge → journey-state-store已覆盖任务追踪

## 3. 合并后效果

| 指标 | 合并前 | 合并后 | 节省 |
|------|--------|--------|------|
| 文件数 | 9 | 3 | -67% |
| 总行数 | ~2547 | ~1466(估) | ~43% |
| 入口清晰度 | 9个命令 | 3个命令 | +70% |

## 4. 风险与约束

1. **无调用方风险低**: 所有7个非核心变体均无Makefile/CI/业务脚本引用
2. **合并顺序**: 先文档标记→再合并测试→最后删除
3. **保留git历史**: 合并后原文件内容在git历史中可查

## 5. 执行计划 (Y1结束前)

- [ ] 标记技术债: debt.yaml登记7个变体合并/退役
- [ ] 合并candidates+intake-pipeline→intake
- [ ] 合并review+approval-flow→lifecycle
- [ ] 退役connector/decision-inbox/task-bridge (保留文件但标记deprecated)
- [ ] 更新Makefile target
- [ ] 验证make scene-card-check仍通过

---

**结论**: 9→3，减67%文件数，降43%代码量。风险低(零业务引用)。标记技术债，Y1结束前执行。
