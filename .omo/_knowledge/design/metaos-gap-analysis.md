---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# MetaOS Gap Analysis (v7.1.0) — Shell vs. Target Capability

> 日期: 2026-06-02 | Phase 17 (P17-W3-METAOS-GAP-ANALYSIS)
> Context: metaos v7.1.0 shell需要从D_Immunity(12,457行/53子器官)和D_Genesis(19,119行/56子器官)填入实现

## 总结

| 优先级 | 数量 | 描述 |
|:------:|:----:|------|
| P0 | 4 | 关键——器官注册、RBAC、身份协议、代谢DAG验证 |
| P1 | 7 | 重要——行为指纹、威胁升级、自愈、能力路由、密钥管理、死锁执行 |
| P2 | 5 | 锦上添花——资产追踪、自动进化、因果引擎、联邦愈合、RL引擎 |

**总计:** 16个差距

## 模块差距详情

### 1. core/gate.py — DecisionGate (P0)

- **当前:** 关键字匹配的红/黄/绿矩阵，JSON加载。无RBAC，无资源级权限。
- **目标:** 完整RBAC(Role→Resource→Action矩阵)，权限守卫+配额执行，防路径遍历审计日志。
- **差距:** 整个RBAC层缺失。D_Immunity有permission_guard.py(~400行)含PermissionGuard/PermissionContext/AuditEvent。

### 2. core/immune.py — ImmuneMonitor (P1)

- **当前:** 3级免疫(WARNING/FREEZE/MELTDOWN)，手动解除计数，有壳子但缺统计基线。
- **目标:** Welford在线基线+Z-score异常检测(3σ)，5级威胁(TL0-TL5)状态机，自动冻结/隔离/自愈。
- **差距:** 缺BehavioralFingerprintEngine(D_Immunity behavioral_fingerprint.py)，缺5级威胁升级状态机。

### 3. core/engine.py — SEngine (P0 for organ registry, P1 for self-healing)

- **当前:** 6步管线(gate→route→M→immune→write→confirm)，会话管理，优雅降级。良好但缺器官生命周期。
- **目标:** 起源引导+器官生命周期管理，正式身份验证协议，自愈执行循环。
- **差距:** 缺OrganIncubator(D_Genesis organ_incubator.py)，缺SelfHealingEngine，缺identity_verify.circuit。

### 4. core/router.py — Router (P1)

- **当前:** 薄JSON映射(task_type→model_id列表)，`apply_cost_optimization()`是no-op。
- **目标:** 基于CAP01-CAP07能力维度路由，成本感知模型选择，负载均衡。
- **差距:** 未使用types.py中已定义的CapabilityMap(7维度)。

### 5. layers/governance.py — MetaGovernance (P1)

- **当前:** 2层治理实现良好(K1-K4不可约规则，冷却期，影响扫描，回滚)。
- **目标:** Layer 3委员会审阅(群组场景)+ D_Immunity审计集成。
- **差距:** Layer 3已声明但未实现。缺devil_audit_gate.py集成。

### 6. layers/m_layer.py — MLayer (P1)

- **当前:** OllamaBackend + MockBackend，自动检测，能力推断。
- **目标:** 多后端(Ollama→OpenAI→Anthropic→Mock)，运行时故障转移，成本追踪。
- **差距:** OpenAI和Anthropic后端已声明(`[v7.0 Sprint 1 planning]`)但未实现。缺运行时健康故障转移。

### 7. deadlock_detector.py (P1)

- **当前:** DFS循环检测，超时检测(300s)，优先级解决方案，READONLY模式。
- **目标:** 与MetabolicLock集成预防性检测，主动终止+恢复。
- **差距:** READONLY模式不执行实际恢复。未集成metabolic_lock.py。

### 8. layers/d_layer.py (P2)

- **当前:** SQLite+文件存储，完整CRUD，事务安全。
- **目标:** 资产追踪链+验证/挑战计数，回滚快照，依赖追踪。
- **差距:** 资产追踪字段在schema中但未被SEngine调用。

### 9. layers/community.py (P2)

- **当前:** 提案/投票/冲突仲裁/委员会管理/涌现检测，已完整实现。
- **差距:** 仲裁人选择算法简单(取第一个非冲突委员)，可改进但非紧急。

### 10. l2_controller.py (P2)

- **当前:** PID控制器+滞后+防积分饱和+冷却门，READONLY模式。
- **差距:** 不执行实际控制。原型的良好实现。

## 建议填入顺序

### Wave 1 — P0关键 (P21 Week 1)
1. gate.py: 替换关键字匹配为PermissionGuard(RBAC+审计)
2. engine.py: 添加OrganIncubator生命周期
3. engine.py + deadlock_detector.py: 接入MetabolicLock.validate_dag()

### Wave 2 — P1重要 (P21 Week 1-2)
4. immune.py: 3级→5级威胁升级+行为指纹引擎
5. router.py: 基于CapabilityMap的能力路由
6. m_layer.py: 添加OpenAI/Anthropic后端

### Wave 3 — P1系统 (P21 Week 2-3)
7. engine.py: 集成SelfHealingEngine
8. gate.py + d_layer.py: 接入密钥保护
9. deadlock_detector.py: READONLY→主动模式

### Wave 4 — P2优化 (P21+或后续Phase)
10. 接入资产追踪字段
11. 归档D_Immunity/D_Genesis的P2器官
12. 改进仪表盘(或等P23 Hermes Console)

## 风险缓解

- **R1(D_Immunity重写破坏安全):** 保留D_Immunity SECURITY.md语义。PermissionGuard是受控替换。
- **R2(行为指纹遗漏触发):** WARMUP_SAMPLES=10的预热期间保留现有计数逻辑作为回退。
- **R3(自愈引入回归):** 先实现为READONLY模式(匹配L2Controller模式)，验证后再激活。
