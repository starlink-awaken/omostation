# Phase 2 Full Execution Go/No-Go Standard

> 日期: 2026-05-30 | 版本: v1.2 | 状态: active
> 关联: `goals/current.yaml`, `state/system.yaml`, `post-phase1-governance-and-phase2-entry.md`
> 用途: 定义 Phase 2 limited_go → full execution 的切换条件

---

## 1. 当前状态

```yaml
phase2_mode: full_execution
completed_gates:
  M2.0: ✅ done  # 治理收敛 + Phase 1 关闭
  M2.1: ✅ done  # KOS 诊断 + 修复计划 + 代码修复
  M2.2: ✅ done  # 操作分级定义 + Agent Registry 设计
remaining_blocks: []
phase1_status: reconciled_closed
health_score: 82.0
```

## 2. Full Execution Go 条件

从 `limited_go` 切换到 `full execution` 必须满足以下 **全部** 条件：

| 条件 | 门禁 | 验收证据 | 当前状态 |
|------|------|----------|:--------:|
| G0 | KOS baseline 修复已执行并验证 | 10 known docs 10/10 可检索 | ✅ **已通过** — approved L2 full reindex 完成，baseline=7327 docs，known-doc check 10/10 |
| G1 | Operation levels 在至少 1 个 MCP tool 中实现拒绝路径 | L2 无确认被拒的测试日志 | ✅ **已通过** — KOS MCP `run_indexer(incremental=false)` 未确认时返回 L2 denied；确认后进入显式路径 |
| G2 | Agent registry heartbeat 最小原型运行 | registry 宕机时缓存降级可验证 | ✅ **已通过** — `ServiceRegistry.register_heartbeat`、`stale_heartbeats`、`save/load_cache_snapshot` 已测试 |
| G3 | 所有 governance 状态源一致 | `phase1_status` 三个文件一致 ✅ | ✅ 已对齐 |
| G4 | `.omo/tasks/` SSOT 无漂移 | active/blocked/done 与 state 一致 | ✅ 已对齐 |
| G5 | 健康评分 ≥80 | `state/system.yaml: health_score` | ✅ 82.0 |
| G6 | sensitive capability gate 生效 | Apple/WeChat/Family OS/SMB/media/high-autonomy 仍未 active | ✅ 已阻断 |

### Full Execution = Go 结论

```
总条件 7 项:  ✅ 7/7   ❌ 0/7

当前建议: ✅ GO — Phase 2 可进入 full_execution
→ 可初始化 M2.3 首批任务 YAML 并放入 `active/`
→ sensitive capabilities 仍保持 blocked，直到 Safe Mesh 代码实现完成
```

---

## 3. Full Execution 的含义

如果 `full_execution` 批准，以下能力从 `candidate` 升级为 `active`：

| 里程碑 | 任务范围 | 来源 |
|--------|----------|------|
| M2.3 | SSOT 7 域最小注册（schema/authority/校验/追溯） | `phase2-task-specs-v2.md` C5 |
| M2.4 | 真实知识闭环（用户问题→KOS→minerva→保存→审计） | `phase2-task-specs-v2.md` |
| M2.5 | 扩展能力评审（模型花园/KEMS/Apple 连接器优先级） | `phase2-task-specs-v2.md` |
| C1-C5 | 全部 5 个 Critical 缺口修复（含 KOS health monitor） | `phase2-task-specs-v2.md` |
| M1/M4 | 模型花园 + KEMS 运行时 | `phase2-task-specs-v2.md` |
| T1-T3 | TokenJuicer / 信任图谱 / BFTS 树搜索 | `phase2-task-specs-v2.md` |

### Full Execution 仍禁止的事项

即使 `full_execution` 批准，以下 sensitive capabilities 仍保持 `blocked` 直到 Safe Mesh 代码实现完成：

- Apple 连接器（数据隔离策略未就绪）
- WeChat 连接器（同上）
- Family OS 调度（Agent identity 未编码）
- SMB / media 索引（RBAC 未编码）
- 高自主自愈（仅 KOS MCP 已有最小 L2 拒绝路径，跨系统 Safe Mesh 尚未完成）
- 破坏性备份/恢复（无 dry-run 门禁）

---

## 4. Full_execution 下的执行口径

进入 full execution 后，以下工作可继续推进，但仍必须通过 `.omo/tasks/active/*.yaml` 认领和审计：

| 领域 | 理由 | 操作级别 |
|------|------|:--------:|
| KOS health monitor / baseline drift check | 基线已建立，后续监控相对 7327 docs | L1-L2 |
| Operation levels 扩展实现 | 已有 KOS MCP 最小拒绝路径，需扩到更多工具 | L0-L2 |
| Agent registry runtime 扩展 | heartbeat/cache 原型已验证，可接入路由 | L0-L1 |
| SSOT 7 域 schema 设计 | 纯设计文档，不写代码 | L0 |
| 测试框架补全 | L0 只读 | L0 |

---

## 5. 建议：本轮不全量初始化 M2.3-M2.5

### 反对本轮初始化的理由

1. **KOS 修复未执行** — M2.3 SSOT 域注册依赖于 KOS 索引的健康基线作为数据源验证。KOS 未修复前注册的 schema 可能在 reindex 后丢失。
2. **Operation levels 未编码** — M2.4 真实知识闭环需要 L2 写入门禁（保存操作）。安全网不存在前启动闭环引入风险。
3. **任务 SSOT 一致性** — 当前 `active/` 为空指示 gate 阶段完成。如果立即写入 M2.3-M2.5 任务，会混淆 gate 边界。

### 推荐方案

```
当前:  full_execution, M2.FULL-GO 前置门禁 7/7 通过
       ↓
Step 1: 初始化 M2.3 首批任务 YAML
       ↓
Step 2: 继续保持 L2/L3 confirmation gate
       ↓
Step 3: 按 `.omo/tasks/active/*.yaml` 执行，避免绕过任务 SSOT
       ↓
Step 4: 每个里程碑完成后重新评估 Go/No-Go 和 rollback 条件
```

如果用户希望加速，最小折中方案：

**优先创建 M2.3 SSOT schema 设计任务**（纯文档，L0），再逐步推进真实知识闭环。

---

## 6. Go/No-Go 判定矩阵

```text
                           Go 条件全部满足?
                           ├─ YES → Full execution authorized
                           │        M2.3-M2.5 全部进入 active
                           │        敏感连接器仍 blocked
                           │
                           └─ NO  → 停留在 limited_go
                                    KOS repair + op levels 编码
                                    部分 M2.3 设计可先行（纯文档）
                                    敏感连接器仍 blocked

当前判定: ✅ GO → 进入 full_execution（sensitive capabilities 仍 blocked）
```

---

## 7. Rollback / 回滚策略

### 7.1 回滚触发条件

以下任一条件触发时，必须从 `full execution` 回滚到 `limited_go` 或更低：

| 条件 | 阈值 | 回滚目标 |
|------|------|:--------:|
| KOS 文档数再降 >50% | 相对 reindex 后的 baseline | limited_go，暂停 SSOT 注册 |
| Operation levels 拒绝路径失效 | L2/L3 未确认操作被执行 | limited_go，禁止写操作 |
| Agent registry 不可用 >30min | 全局路由中断 | safe_mode，只读 |
| 健康评分 <70 | `state/system.yaml: health_score` | limited_go，暂停新任务 |
| 审计发现未授权数据写入 | 任何 L2+ 操作无审计记录 | 回滚到 M2.0，治理重审 |

### 7.2 回滚步骤

```text
Step 1: 检测异常
  aggregator/CI 持续监控 health_score 和审计日志
  ↓
Step 2: 判定回滚等级
  ├─ minor（单项指标波动 <20%）: 告警，不自动回滚
  ├─ major（单项指标降 >20%）: 暂停相关里程碑，通知 human
  └─ critical（全系统指标降 >30% 或安全事件）: 立即回滚
  ↓
Step 3: 执行回滚
  ├─ 代码回滚: git revert 或 checkout 到上一个 stable tag
  ├─ 数据回滚: 从 backup 恢复 KOS index / Agora registry snapshot
  └─ 任务回滚: 将 active/ 中受影响任务移回 candidate，
               更新 state/system.yaml phase_status = limited_go
  ↓
Step 4: 复盘
  写入复盘报告到 .omo/summaries/，更新 failure_injection 测试场景
```

### 7.3 回滚验证

每次回滚后必须验证：

- `state/system.yaml` 的 phase_status 已更新 ✅
- `active/` 中受影响任务已移出 ✅
- `blocked/` 中记录了 blocker 和 next_check_at ✅
- 关键服务健康检查通过（SharedBrain / Agora / KOS） ✅
- 审计日志记录了回滚事件 ✅

### 7.4 回滚终止条件

回滚完成后，以下条件满足时可重新进入 `limited_go`：

- 回滚根因已被诊断并修复
- 系统健康评分恢复到回滚前水平
- 人工验收通过
- 无残留 blocking issue

```
