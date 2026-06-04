# Workspace AI OS 全景路线图

> 从当前到终局: 个人→多人→多组织→蜂群智能
> 版本: v2.0 | 日期: 2026-05-25
> 基于: .omo/plans/workspace-ai-os-master-roadmap.md + Phase 1-6完成状态

---

## 当前位置

```
  过去 (Ph1-6)          现在          Phase 7 → Phase 10 → 终局
  [████████████████] ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▶
  66.80分            痛点:          目标: 蜂群智能
                     场景覆盖57/100  多人+多Agent集体智慧
                     成本不可见
                     治理半成品
```

---

## 全景路线图

```
Phase 7 (4周): 让工具跑起来
  ├─ 7.1 完整用户旅程 (D2: 57→85) 
  ├─ 7.2 成本可见 (D9: 0→60)
  └─ 7.3 熵增自动化 (D6: 50→80)

Phase 8 (6周): 多Agent真实协作
  ├─ 8.1 Hermes→Collab集成 (MCP调用TaskObject)
  ├─ 8.2 Memory/Skill标准化为MCP服务
  ├─ 8.3 Claude Desktop/Codex接入验证
  └─ 8.4 Agora降级模式 (A2A直连)

Phase 9 (8周): 多人多组织
  ├─ 9.1 IdentityEnvelope做实 (CA模型)
  ├─ 9.2 CapabilityGrant可执行
  ├─ 9.3 TaskObject跨组织可见性
  └─ 9.4 生态宪法 (最小互通协议)

Phase 10 (持续): 蜂群智能
  ├─ 10.1 递归架构 (个人→团队→组织同构)
  ├─ 10.2 进化闭环 (自动复盘+迭代)
  ├─ 10.3 跨域信任 (WoT信任网)
  └─ 10.4 集体智慧网络
```

---

## Phase 7: 让工具跑起来 🚀 (4周)

**核心问题**: 工具建好了但没人用——D2场景覆盖度只有57/100，缺的是"用户旅程"而非"功能"。

### Wave 7.1 — 完整用户旅程 (2周)

从用户视角补全5条核心链路的断点：

```
当前                    →  目标
┌─────────────────┐       ┌────────────────────────┐
│ L4 Self MCP工具有 │       │ 用户说话→Hermes感知→  │
│ 但Hermes没调它们  │       │ L4上下文自动注入→      │
│ L3 Collab工具有   │       │ 创建Task→Agent认领→   │
│ 但没有Agent认领   │       │ 执行→完成→共识标记→   │
│ Consensus工具有   │       │ 保鲜Cron跟踪 freshness │
│ 但没人新建过共识   │       └────────────────────────┘
└─────────────────┘
```

| Task | 描述 | 验证 |
|------|------|------|
| T099 | Hermes config接入self_inject.sh | 每天首次交互自动加载L4上下文 |
| T100 | Hermes集成TaskObject: 复杂任务自动创建+拆解 | "帮我审计一下"→自动创建Task→认领→完成 |
| T101 | 共识自然标记: Hermes完成任务后自动创建consensus | 完成即留下可信标记 |
| T102 | 保鲜Cron首份报告 | freshness_check.sh输出第一份熵增报告 |
| T103 | D2场景覆盖度重评 | 57→85 |

### Wave 7.2 — 成本可见 (1周)

**核心问题**: D9完全盲区——不知道每天花多少钱。

| Task | 描述 |
|------|------|
| T104 | agentmesh Model-Orchestrator中加token/成本计数器 |
| T105 | 新建`~/.kos/accounting/usage.db`记录每次调用 |
| T106 | `cost summary --today` CLI命令 |
| T107 | 日报cron: 每天推送token消耗到微信 |

### Wave 7.3 — 熵增自动化 (1周)

| Task | 描述 |
|------|------|
| T108 | 保鲜Cron输出结构化报告(json) |
| T109 | 报告自动写入KOS(consensus domain) |
| T110 | D6熵增评分更新: 50→80 |

**Phase 7 通过条件**: D2≥85, D9≥60, D6≥80, 健康总分≥75

---

## Phase 8: 多Agent真实协作 🤝 (6周)

**核心场景**: 你发一个任务，Hermes调研+Claude Desktop设计+Codex编码，各自认领、并行工作、共享成果。

### Wave 8.1 — Hermes集成Collab (2周)

```python
# 当前: Hermes单步推理
user: "写一个Mac监控面板"
→ Hermes自己调研→自己设计UI→自己编码

# 目标: Hermes多Agent编排
user: "写一个Mac监控面板"
→ Hermes创建TaskObject (collab.create_task)
  ├─ subtask: research → Hermes认领
  ├─ subtask: ui-design → 等待Claude Desktop认领
  └─ subtask: coding → 等待Codex认领
→ Hermes做完research → 更新Task → 事件通知
→ Claude Desktop感知→认领ui-design→完成
→ Codex感知→认领coding→完成
→ Hermes汇总→通知用户
```

### Wave 8.2 — Memory/Skill标准MCP化 (2周)

| Task | 描述 |
|------|------|
| T111 | Hermes memory → Memory MCP Service |
| T112 | Hermes skill → Skill MCP Service |
| T113 | 注册到Agora, 任何Agent可查 |

### Wave 8.3 — 外部Agent接入验证 (1周)

| Task | 描述 |
|------|------|
| T114 | Claude Desktop认领+完成一个UI设计subtask |
| T115 | Codex CLI认领+完成一个编码subtask |
| T116 | 三Agent协作E2E: Hermes+Claude+Codex同跑一个Task |

### Wave 8.4 — Agora降级模式 (1周)

| Task | 描述 |
|------|------|
| T117 | Agora不可用时Agent之间A2A直连 |
| T118 | 降级模式混沌测试(停Agora→检查Agent能否继续) |

**Phase 8 通过条件**: 三Agent协作场景跑通、E2E测试全绿

---

## Phase 9: 多人多组织 🏢 (8周)

**核心场景**: 你和另一个团队协作做一个项目——跨组织创建Task、共享能力、审计追踪。

### Wave 9.1 — IdentityEnvelope 做实 (2周)

```yaml
# 从"概念文档"到"可验证实体"
identity_envelope:
  subject_id: "user:老王"
  issuer: "ca:agora.starlink.local"
  proof_ref: "did:key:z6Mk..."
  tenant: "starlink-core"
  expires_at: "2026-12-31"
```

| Task | 描述 |
|------|------|
| T119 | IdentityEnvelope Schema定稿(Eidos) |
| T120 | Agora签发第一版身份凭证(CA模式) |
| T121 | Hermes携带身份凭证调用MCP |

### Wave 9.2 — CapabilityGrant 可执行 (2周)

```yaml
capability_grant:
  subject: "org:partner"
  capability: "minerva.research"
  resource_scope: "project:joint-research"
  constraints: { max_cost_usd: 10, expire_at: "2026-12-31" }
  issued_by: "ca:agora.starlink.local"
  revoked_at: null
```

| Task | 描述 |
|------|------|
| T122 | CapabilityGrant Schema定稿 |
| T123 | Agora授权门禁: 无grant的调用拒绝 |
| T124 | grant签发/吊销CLI |

### Wave 9.3 — TaskObject跨组织 (2周)

| Task | 描述 |
|------|------|
| T125 | TaskObject visibility_scope: team/org/public |
| T126 | 跨组织Task: 创建→外部Agent认领→完成 |
| T127 | 跨组织Resource Accounting: 成本归属 |

### Wave 9.4 — 生态宪法 (2周)

| Task | 描述 |
|------|------|
| T128 | 生态宪法文档: 最小互通协议 |
| T129 | 节点类型定义: Full/Light/External/Human |
| T130 | 异构节点接入Adapter模板 |

**Phase 9 通过条件**: 跨组织Task创建→认领→完成链路跑通

---

## Phase 10: 蜂群智能 🐝 (持续)

**终极愿景**: "多人+多Agent集体智慧网络"

### Wave 10.1 — 递归架构实现

将4+1+3架构实例化到不同层级:

```
个人(当前) → 团队 → 组织 → 生态
每个层级都有的:
  L4: 该层级的"自我" (个人身份/团队使命/组织愿景)
  L3: 该层级的协作 (个人Task/团队项目/组织OKR)
  L2: 该层级的能力 (个人工具/团队共享能力)
  L1: 该层级的契约 (个人Schema/团队规范/组织标准)
```

| Task | 描述 |
|------|------|
| T131 | 团队级Agora实例化: 独立服务注册+路由 |
| T132 | 组织级Identity: 多租户签发者 |
| T133 | 生态级AgentCard: 跨域Agent发现 |

### Wave 10.2 — 进化闭环

| Task | 描述 |
|------|------|
| T134 | 自动复盘: 每Phase结束自动生成进化建议 |
| T135 | 进化建议→skill patch/memory update自动落地 |
| T136 | 健康评分自动门禁: 低于阈值自动冻结新功能 |

### Wave 10.3 — 跨域信任网

| Task | 描述 |
|------|------|
| T137 | WoT信任模型: 组织间互相承认身份 |
| T138 | 信任传递链: A信任B, B信任C → A信任C |
| T139 | 分布式CapabilityGrant: 跨Agora实例授权 |

### Wave 10.4 — 集体智慧网络

```
用户             ┌──────────────┐
  │              │ 共同知识库    │
  ├─ 老王 ──────→│ (KOS联邦)    │←────── 合作者B
  │              │              │
  ├─ Agent集群 ─→│ 蜂群决策      │←────── 合作者C
  │              │ 集体复盘      │
  └─────────────→│ 共享进化      │
                 └──────────────┘
```

---

## 健康评分演进路线

```
Phase   D1愿景  D2场景  D5架构  总分   关键里程碑
──────  ──────  ──────  ──────  ─────  ─────────────────
当前     85     57      71      66.80  架构骨架完成
Ph7      90     85      75      75+    用户旅程跑通
Ph8      90     90      85      80+    多Agent协作
Ph9      95     90      90      85+    跨组织协作
Ph10     100    100     100     90+    蜂群智能
```

---

## 决策路径图

```
当前状态: 架构骨架完成(66.80分)
  │
  ├──→ Phase 7: 让工具跑起来 (4周)
  │     如果成功 → D2≥85, 健康≥75
  │     如果不成功 → 回到Wave 7.1重做用户旅程
  │
  ├──→ Phase 8: 多Agent协作 (6周)
  │     如果成功 → 三Agent协作跑通
  │     如果不成功 → 降级: 先只做Hermes+Collab集成
  │
  ├──→ Phase 9: 多人多组织 (8周)
  │     如果成功 → 跨组织链路跑通
  │     如果不成功 → 暂缓跨组织，先强化单人体验
  │
  └──→ Phase 10: 蜂群智能 (持续)
        是前三个Phase的自然收敛，不需"启动" 
```

---

> 维护: atlas + sisyphus
> 下一刷新: Phase 7完成时
