---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-21
---
# A8 OMO 外部事务生命周期 — 现状复核报告 (BET-Y1Q4-T10-151 第一阶段)

## 目标

根据 BET-Y1Q4-T10-151 circuit_breaker 原则, 完成 ADR/archive/mutation-surfaces/ingress delivery 五处路径搜索, 确认真实状态: 事务链已存在但未被发现, 或确认缺失需新增实现。

## 期望事务链

```
reserve → bind → readback → start → ACK/fence → release/retire
```

## 路径搜索结果

### 1. ADR (Architecture Decision Records)

```
grep -r "reserve.*bind\|external_transaction\|fence.*release" .omo/_knowledge/decisions/
```

| ADR | 是否相关 | 备注 |
|-----|----------|------|
| `0396-pdp-binding-context.md` | ❌ | PDP binding, 非事务状态机 |
| `0401-claims-authority-bridge.md` | ⚠️ | bind/release 概念重叠, 但限于 claim-authority 范围 |
| `0448-claimable-truth-recovery.md` | ⚠️ | truth recovery 而非外部事务 |
| `0451-hitl-proposal-system.md` | ❌ | HITL proposal, 非 A8 事务 |

**结论**: 无 ADR 显式定义 A8 外部事务状态机。

### 2. Archive (`.omo/_archive/`)

```
find .omo/_archive -name "*transaction*" -o -name "*external*" -o -name "*a8*" 2>&1
```

| 文件 | 相关 |
|------|------|
| `2026-09-a4-scheduler-consolidation/` | ⚠️ Scheduler consolidation 而非外部事务 |
| `closeout-2026H1/` | ❌ |

**结论**: 无 A8 归档交付物。

### 3. mutation-surfaces

```
grep -r "omo.mutation\|MutationSurface" projects/omo/src/ 2>&1
```

| 文件 | 内容 | 是否相关 |
|------|------|----------|
| `mutation_surfaces.py` | omo mutation surface registry | ❌ 用于 mutation-only |
| `binding_digest.py` | claimable 绑定摘要 | ⚠️ 部分相关 |
| `state_plane_assets.py` | 资源 plane 元数据 | ❌ |

**结论**: 无 A8 事务状态机。

### 4. ingress delivery

```
grep -r "reserve.*bind\|ack.*fence" projects/cockpit/src/cockpit/ingress/ projects/omo/src/omo/resident/ 2>&1
```

| 文件 | 是否相关 |
|------|----------|
| `projects/cockpit/src/cockpit/handlers/scene_lifecycle.py` | ⚠️ 场景 lifecycle 而非外部事务 |
| `projects/omo/src/omo/resident/decision_bridge.py` | ❌ |
| `projects/omo/src/omo/resident/cell_pool.py` | ❌ |

**结论**: 无 A8 reserve/bind/readback 序列。

### 5. omo.resident 全量

```
grep -rn "class.*StateMachine\|def reserve\|def bind\|def readback\|def fence\|def retire" projects/omo/src/omo/resident/
```

| 实现 | 类型 | 相关 |
|------|------|------|
| `class CellPool` | 资源池 | ❌ |
| `class SceneLifecycleCruiser` | 场景巡航 (T7-05) | ❌ lifecycle 而非事务 |
| `class TaskQueue` (T10-125) | 任务队列 | ⚠️ 部分相关, 但内部事务 |
| `class DecisionBridge` | 决策桥 | ❌ |

**结论**: 无完整 A8 外部事务状态机。

## 权威现状报告

| 期望阶段 | 是否实现 | 实现位置 | 评级 |
|----------|---------|-----------|------|
| reserve | ❌ | 无 | 缺失 |
| bind | ⚠️ 部分 | `binding_digest.py` (claimable) | 半成品 |
| readback | ❌ | 无 | 缺失 |
| start | ❌ | 无 | 缺失 |
| ACK/fence | ⚠️ 部分 | `binding_digest.py` (claimable) | 半成品 |
| release/retire | ⚠️ 部分 | `T10-125 task_queue.complete/fail` | 内部事务而非外部 |

## 结论

A8 外部事务状态机 (reserve/bind/readback/start/ACK/fence/release/retire) **未完整实现**。

仅有零星片段 (`claimable` 系 / `task_queue` 内部) 触及 reserve/ACK/release 子集, 但未形成七段串联状态机。

## 决策建议

根据 circuit_breaker "若发现已存在则停止重复实现, 转为补充证据登记" — 不存在, 故应继续第二阶段: 产出 reserve→bind→readback→start→ACK/fence→release/retire 七段状态机的最小实现与测试。

## 证据登记

| 文件 | 内容 |
|------|------|
| `.omo/_knowledge/decisions/index.md` | 本报告入口 |
| `.omo/_delivery/external-transaction-status-2026-09-14.md` | 五处路径搜索详细结果 |
| `.omo/_knowledge/retros/BET-Y1Q4-T10-151.md` | retro 4 段 |

## 实施建议 (下阶段)

七段状态机最小实现 ~150 LOC:
1. `bin/ops/a8-transaction.sh reserve <txn_id>` — 占位 + 持久化到 ledger
2. `bin/ops/a8-transaction.sh bind <txn_id> <resource>` — claimable digest 写入
3. `bin/ops/a8-transaction.sh readback <txn_id>` — 验证 + 状态打印
4. `bin/ops/a8-transaction.sh start <txn_id>` — ACK gate
5. `bin/ops/a8-transaction.sh fence <txn_id> <reason>` — 隔离/暂停
6. `bin/ops/a8-transaction.sh release <txn_id>` — 释放到下一阶段
7. `bin/ops/a8-transaction.sh retire <txn_id>` — 归档到 ledger

实现复杂度: 1 sprint (与 appetite 一致)。
EOF
