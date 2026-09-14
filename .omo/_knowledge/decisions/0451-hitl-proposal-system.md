---
id: ADR-0451
status: accepted
lifecycle: contract
owner: xiamingxing
last-reviewed: 2026-09-04
type: ssot
---

# ADR-0451: HITL Proposal System — file-based approval gate for harness stage_execute

## 背景

- omostation 现行 harness 8 阶段 DAG (ADR-0444) 在 `stage_execute` 直接执行 BET 定义的 action,无人类审批节点。
- L2/L0 风险 BET (118 个, `human_gate: true`) 缺执行前的人工 gate,违反 "D5 子模块 / T10 maturity / 治理专项" 类高风险操作的"先审后行"原则。
- T1-04 同期已暴露 portfolio v2 mutation 必须 human 触发,沿用 in-band claim / 决策 inbox 等机制,语义不清且状态机不一致。
- 现有 cockpit decide 决策收件箱覆盖 scene / journey / intent 三角,未触及"harness 触发的 human gate 请求"。

## 决策

引入 **HITL Proposal System** (BET-Y1Q4-HITL-01, PR #3077):在 harness `stage_execute` 后插入 human gate,生成 file-based approval proposal,principal 通过 `cockpit decide approve/reject` 完成审批。降级路径:proposal 24h TTL 过期自动降级为 direct execution (circuit breaker)。

## 理由

1. **明确状态机**:file-based YAML proposal 替代 in-band claim,审批意图独立于 agent workflow run,审计追溯完备。
2. **最小侵入**:`bin/hitl-proposal.py` 单文件 (~340 LOC, 7 子命令),不引入数据库,不重写 harness DAG。
3. **circular breaker 完备**:24h TTL + 系统 actor 自动 expire,避免 proposal 永远 pending 阻塞 agent。
4. **actor 自动捕获**:`git config user.name/email` 默认填入 `response_actor`,审计字段无需 principal 手输。
5. **Cockpit 集成最小**:`cockpit decide` 路由 `hitl-*` ID 直转 `bin/hitl-proposal.py`,无新 UI。
6. **GaC 配额守恒**:新增脚本走 `script-registry` 登记 + `script_baseline` bump(576→577),符合 add 1 = delete 1 + baseline 增量规则。

## 反例(已评估并拒绝)

### 备选 A: 改造 agent-workflow.py 加 human_gate 字段

- 缺点:agent-workflow 与 harness 状态机耦合,加新 gate 需扩 schema / state machine / UI 三处;BDSK 3 层反弹。
- 拒绝原因:agent-workflow 是通用 runtime,不专属 L2/L0 风险 BET。

### 备选 B: 用现有 cockpit 决策收件箱(scene/journey/intent)承载

- 缺点:scene/journey 抽象针对"业务场景",语义与 harness 触发的"执行审批"错位;若强行套用,intent schema 膨胀。
- 拒绝原因:污染现有抽象,审计字段不匹配。

### 备选 C: 用 PR review 流程(CI bot 留 issue)

- 缺点:异步,阻塞 agent;PR 数量爆炸(每 L2 BET 一 PR);无法 24h TTL 自动降级。
- 拒绝原因:PR 流程是为 human-driven code change 设计,不适配 agent-driven execution。

## 架构定位

```
harness stage_execute
   ↓ appetite check
   ↓ [NEW] human_gate check (bin/hitl-proposal.py check)
   ↓ [NEW] if required: bin/hitl-proposal.py create → .omo/_knowledge/hitl-proposals/<id>.yaml
   ↓
   ↓ principal: bin/cockpit decide list / approve / reject <id>
   ↓
   ↓ bin/hitl-proposal.py update_status (fcntl.flock atomic)
   ↓
   ↓ [FUTURE v1.1] harness blocks on proposal resolution (wait_for_decision)
   ↓
   ↓ execute continues
```

## 失败模式与降级

| 失败模式 | 降级路径 |
|----------|----------|
| `check_human_gate_needed` 异常 (yaml 解析 / ledger 缺失) | direct execution (no HITL) |
| `create_proposal` 失败 (disk full / perm denied) | direct execution,stderr 警告 |
| proposal 24h TTL 过期 | 系统 actor 自动 `expire`,agent 继续 (circuit breaker) |
| `fcntl.flock` 失败 (跨主机 / NFS) | 退化为 read-modify-write (已有 in-process 锁兜底) |
| cockpit decide 找不到 `hitl-*` ID (submodule 未 bump) | subprocess 退到 `bin/hitl-proposal.py`,standalone 模式 |
| principal 长时间不审批 | TTL 触发自动降级,agent 不死锁 |

## 集成现状

| 组件 | 状态 | 依赖 |
|------|------|------|
| `bin/hitl-proposal.py` (单文件 7 subcommands) | ✅ 落地 | 无 |
| `bin/harness stage_execute` HITL gate | ✅ 落地(subprocess 调用) | `bin/hitl-proposal.py` |
| `tests/test_hitl_proposal.py` (8 tests) | ✅ PASS | 无 |
| `cockpit decide list/approve/reject` HITL 路由 | ⏳ 等 PR #129 merge | `projects/cockpit` 子模块 |
| harness 阻塞等审批 (v1.1) | ⏳ spec 已写 (`2026-09-04-hitl-proposal-system-v1.1-design.md`) | `bin/hitl-proposal.py` 已有 `wait_for_decision` 函数 |

## 后续 BET

- **BET-Y1Q4-HITL-02** (v1.1): harness `stage_execute` 真正阻塞 poll proposal resolution,Slack/邮件通知,跨主机分布式锁
- **BET-Y1Q4-HITL-03** (候选): 把 118 个 L2/L0 human_gate BET 真正启用审批,跑通端到端

## 关联

- BET-Y1Q4-HITL-01 (closeout retro: `.omo/_knowledge/retros/BET-Y1Q4-HITL-01.md`)
- Spec v1.0: `docs/superpowers/specs/2026-09-04-hitl-proposal-system-design.md`
- Spec v1.1: `docs/superpowers/specs/2026-09-04-hitl-proposal-system-v1.1-design.md`
- PR #3077 (omostation) / PR #129 (omostation-cockpit)
- Patterns: P97 / P98 / P99 (本次迭代教训沉淀)
- ADR-0444 (harness self-evolving) — 8 阶段 DAG 入口
- ADR-0199 (unified BOS, cockpit, cognitive workflow) — cockpit 集成位置
- ADR-0396 (resident agent system) — 可拓展为 resident heartbeat 触发审批
