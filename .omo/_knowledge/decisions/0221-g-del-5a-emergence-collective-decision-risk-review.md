---
status: ACCEPTED
lifecycle: decision
owner: 架构师
last-reviewed: 2026-07-18
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0220-swarm-coordination-discipline-m1-gate.md
  - docs/STRATEGY-INDEX.md
  - BET-8c7c
supersedes: []
---

# ADR-0221: G-DEL.5a 涌现检测与集体决策 · L3 专项风险评审

> **性质**：风险评审 ADR（决策/约束），**不**交付涌现检测运行时或集体决策引擎。  
> **门禁**：G-DEL.5 实现启动前必须本 ADR 为 `ACCEPTED` 且人工 kill-switch 设计可验证。

## Context and Problem Statement

兑现期 BET-8c7c（涌现 + 集体决策）标为 **⚠L3**：涌现行为不可完全预测，可能放大错误决策、资源消耗或越权写。  
若在 M1 冲突窗未满 / 无硬限制 / 无人工可干预时直接实现运行时，会把「不可控协作」叠在「主仓并发纪律尚未完全复判」之上——违反 ADR-0210 愿景验收纪律。

本 ADR 只回答：

1. 涌现 **允许的硬范围** 是什么？  
2. **人工干预 / kill-switch** 如何设计才算有效？  
3. 残余风险与 residual 接受条件？

## Decision Drivers

- **D1 · L3 先评审后实现**：STRATEGY-INDEX 明确 ⚠ 启动前专项评审。  
- **D2 · 与 M1 解耦**：评审与设计可在 `window_open` 期间完成；**实现**必须等 M1 pass。  
- **D3 · 可关闭优先于可涌现**：任何涌现路径必须默认有人类可瞬时切断的开关。  
- **D4 · 范围硬限制**：禁止开放式「自我改写治理规则 / 无界 spawn」。

## Considered Options

- **A · 不做评审直接实现**：快，但 L3 失控风险不可接受。  
- **B · 评审 + 硬限制 + kill-switch 设计（选定）**：实现前锁定边界。  
- **C · 永久禁止涌现**：与战略 Bet 冲突；可作 residual 若 B 无法落地。

## Decision Outcome

**选定 B。** G-DEL.5 实现必须遵守以下约束。

### 1. 涌现范围硬限制（Hard Scope Limits）

| # | 限制 | 说明 |
|---|------|------|
| S1 | **只读涌现默认** | 检测/打分可自动；**写路径**（改代码、改 SSOT、merge、spawn 子 agent）默认关闭 |
| S2 | **白名单动作** | 集体决策可建议的动作集固定：`recommend_assign` / `recommend_block` / `recommend_risk_gate`；禁止 `force_merge` / `disable_hooks` / `rewrite_adr` |
| S3 | **无界 spawn 禁止** | 单轮集体决策最多 N 个子 agent（默认 **N=3**）；禁止递归涌现链深度 > 1 |
| S4 | **资源封顶** | 单次涌现会话：墙钟 ≤ 15min、token/cost 预算可配置且默认保守 |
| S5 | **不改治理元规则** | 涌现不得修改 GaC rules、branch protection、write-owners、swarm-coordination registry |
| S6 | **作用域** | 仅允许在显式 `emergence_enabled=true` 的 goal/run 上运行；默认 false |

### 2. 人工干预 / Kill-Switch 设计

| 控件 | 机制 | 验收 |
|------|------|------|
| **K1 全局开关** | env `ECOS_EMERGENCE_ENABLED=0\|1`（默认 0）+ goals 字段 `emergence.enabled` | 设 0 后新会话拒绝启动涌现 |
| **K2 会话熔断** | 运行中文件/信号 `.omo/_delivery/emergence/KILL` 或 API `emergence.abort` | 存在 KILL 文件 1s 内停止新动作 |
| **K3 写路径闸** | 所有写动作二次确认：人类 ACK 或 `SWARM_ESCAPE_ID` **不**适用涌现写（明确拒绝用 escape 绕过） | 无 ACK 时写动作 exit non-zero |
| **K4 审计** | 每次涌现回合 append-only 到 `.omo/_delivery/emergence/events.jsonl` | 可回放「谁建议了什么」 |
| **K5 回滚提示** | 若有经批准的写，必须记录 reverse 指针（PR / commit） | 复盘可定位 |

**有效性定义（实现期测）**：在开启涌现的集成测试中，触发 K2 后 **不得** 再产生新的写 side-effect；K1=0 时入口直接拒绝。

### 3. 集体决策语义（建议层）

- 输出仅为 **建议**（recommendation），默认不自动执行。  
- 执行路径必须回到 G-DEL.2a 协议的 `assign` / 人类批准。  
- 准确率 KPI（>80%）仅在 **标注集 + 离线评估** 上度量；禁止用「代码存在」代替。

### 4. Residual Risks（接受条件）

| 风险 | 残余 | 接受条件 |
|------|------|----------|
| 建议质量差误导 orchestrator | 中 | 人工确认写路径；准确率门禁 >80% 才升默认建议权重 |
| 绕过 kill-switch（直接调底层 API） | 中 | 写面仍受 write-owners / claim / branch protection 约束 |
| 延迟到 M1 后才实现导致进度焦虑 | 低 | 本 ADR + G-DEL.2a 图纸已降低空转 |
| 误将评审当实现完成 | 低 | closeout 禁止用本 ADR 顶替 G-DEL.5 runtime 验收 |

## Consequences

### Positive

- G-DEL.5 实现有明确「能做 / 不能做」清单。  
- Pre-M1 可完成评审不浪费日历时间。  
- 与 ADR-0220 四闸门正交：涌现不得成为 escape hatch。

### Negative / Follow-ups

- 实现期需额外工程：K1–K5、审计日志、评估集。  
- N=3 / 深度 1 可能限制「真涌现」想象力——有意为之。

## Out of Scope（本 ADR 明确不交付）

- 涌现检测模型/服务代码  
- 集体决策自动执行引擎  
- 多机状态同步（G-DEL.3）  
- Agent 注册中心（G-DEL.1）

## Compliance Check for Future PRs

实现 PR 必须在描述中勾选：

- [ ] 遵守 S1–S6  
- [ ] K1–K5 可测  
- [ ] M1 `m1_verdict=pass` 已记录  
- [ ] 无修改治理元规则路径  

## References

- BET-8c7c · docs/STRATEGY-INDEX.md  
- ADR-0210 不过不进  
- ADR-0220 swarm 纪律  
- G-DEL.2a `docs/G-DEL-2a-role-framework-contract.md`（`risk_gate` 消息）
