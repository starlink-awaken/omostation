# 深度架构审计：Agent协作体系 × 第一性原理

> 日期: 2026-05-29 | 版本: v1.0 | 审查对象: deep-architecture-agent-analysis.md + ../_knowledge/design/MASTER-BLUEPRINT.md
> 审查类型: 架构审计 + 红队攻击 + 缺口分析
> 本文档是历史审计与红队分析输入，保留当时的风险判断、架构缺口和修订建议，不是当前 Agent 拓扑、当前协作面或当前运行状态 SSOT。
> 当前事实请回到 `/.omo/PROJECTS.yaml`、`AGENTS.md`、`docs/PANORAMA.md`、`/.omo/goals/current.yaml`、`/.omo/state/system.yaml`。

---

## 目录

1. [ACP 架构审计](#一acp-架构审计)
2. [Agent-as-Kernel 模式审计](#二agent-as-kernel-模式审计)
3. [分层控制面审计](#三分层控制面审计)
4. [Agent选型审计](#四agent选型审计)
5. [第一性原理合规审计](#五第一性原理合规审计)
6. [红队攻击场景](#六红队攻击场景)
7. [缺失能力清单](#七缺失能力清单)
8. [修订建议](#八修订建议)

---

## 一、ACP 架构审计

### A1: Agent Registry — 中心化单点故障

**缺陷**: Registry 是中心化的。如果 Registry 宕机，所有 Agent 无法互相发现。

| 攻击场景 | 影响 | 严重性 |
|---------|------|:----:|
| Registry 进程崩溃 | 所有 Agent 协作停止 | 🟠 Major |
| Registry 被恶意修改 | Agent 被路由到假Agent | 🔴 Critical |
| Registry 数据不一致 | Agent A 认为 Agent B 存在但 B 已下线 | 🟡 Minor |

**建议**: 
- Registry 增加本地缓存 (Agent 本地保存最近发现的 Agent 列表)
- Registry 心跳检测 (Agent 定期上报，超时自动注销)
- Registry 数据签名 (防止篡改)

### A2: Task Dispatcher — 无优先级和QoS

**缺陷**: Dispatcher 只按能力匹配，没有优先级、紧急度、SLA 概念。

```
场景: 
  用户任务: "紧急分析市场暴跌原因" → Dispatcher → minerva
  同时: 100个后台研究任务也在队列中
  结果: 紧急任务排在队列末尾, 等了30分钟
```

**建议**: 
- 任务优先级 (P0-CRITICAL / P1-HIGH / P2-NORMAL / P3-LOW)
- QoS 保证 (P0 任务 5分钟内开始)
- 抢占 (P0 到达时, 暂停当前 P2/P3 任务)

### A3: Event Bus — NATS引入新依赖风险

**缺陷**: 建议引入 NATS 作为外部依赖。这会增加部署复杂度和管理负担。

| 方案 | 风险 | 
|------|------|
| Agora MCP PubSub | 不是真正的消息队列, 无持久化 |
| Redis PubSub | 新增依赖, 需要维护 |
| **NATS** | 新增依赖, 学习曲线, 运维负担 |

**建议**: Phase 2 先用 **Agora MCP PubSub (无外部依赖)**。如果不够用，Phase 3 再评估 NATS。不要过早优化。

### A4: 缺少Agent死锁检测

**缺陷**: 两个Agent互相等待对方完成任务 → 永久死锁。无检测机制。

```
场景:
  Agent A (minerva) → 等待 Agent B (KOS) 提供索引
  Agent B (KOS)    → 等待 Agent A (minerva) 研究完成
  结果: 两者互相等待 → 死锁 → 无人感知
```

**建议**: 
- 超时检测 (Agent 等待 > 5分钟 → 告警)
- 依赖图分析 (循环等待 → 主动打破死锁)
- Deadlock Monitor Agent

---

## 二、Agent-as-Kernel 模式审计

### K1: LLM 幻觉风险放大

**缺陷**: Agent 的 brain 是 LLM。如果 LLM 产生幻觉，Agent 会执行错误操作。

```
场景:
  L2 Controller Agent (brain=LLM) 感知: "minerva 延迟高于基线 2 倍"
  LLM 幻觉推理: "原因一定是数据库满了, 建议删除最近30天的研究数据"
  Agent 执行: 删除 30 天研究数据 → 灾难性知识损失
```

**严重性**: 🔴 Critical。

**建议**: 
- **沙箱执行**: Agent 的破坏性操作（删除、重启、回滚）必须在沙箱中预演
- **人类确认**: 破坏性操作永远需要人类确认（不可绕过，即使 Agent 是 Admin）
- **操作分级**: 
  - Level 0 (读操作): Agent 自主
  - Level 1 (低风险写): Agent 自主但记录
  - Level 2 (高风险写): 必须人类确认
  - Level 3 (破坏性): 必须人类确认 + 24h 冷静期

### K2: EU预算耗尽 → Agent死后不可恢复

**缺陷**: Agent 消耗 EU。如果 Agent 在执行过程中 EU 耗尽 → 任务中断，状态丢失。

```
场景:
  minerva Agent 正在做 8 步深度研究
  第 5 步: EU 耗尽 → Agent 被暂停
  结果: 前 4 步的中间结果丢失, 无法恢复
```

**建议**:
- **检查点 (Checkpoint)**: Agent 在关键步骤后保存中间状态
- **EU 预检**: 任务开始前，预估总 EU 消耗，余额足够才启动
- **优雅降级**: EU 不足时，Agent 保存当前状态 → 请求充值 → 恢复继续

### K3: Agent 间循环依赖

**缺陷**: Agent-as-Kernel 模式使 Agent 成为控制面，但如果 Agent 互相依赖 → 启动死锁。

```
场景:
  minerva Agent 启动 → 需要 gbrain memory 来读取历史
  gbrain   Agent 启动 → 需要 minerva 来分析 memory 健康
  结果: 互等 → 两个 Agent 都无法启动
```

**建议**: 
- 启动顺序定义 (基础设施 → 数据层 → 能力层 → 协作层 → 元层)
- 懒加载: Agent 可以在缺少依赖时启动（降级模式）
- 启动超时: 如果依赖在 30s 内不可用，以降级模式启动

---

## 三、分层控制面审计

### C1: 层控制器过调(振荡)

**缺陷**: 控制论系统的经典问题。如果 L2 Controller 检测延迟高 → 降速 → 延迟降低 → 升速 → 延迟又高 → 降速 → 振荡。

```
L2 Controller 行为:
  t0: minerva延迟=500ms (baseline=100ms) → 降低并发度: 10→5
  t1: minerva延迟=80ms → 恢复并发度: 5→10
  t2: minerva延迟=520ms → 降低并发度: 10→5
  ... 振荡 ...
```

**建议**: 
- **滞回 (Hysteresis)**: 延迟 > 2× 才降速, 延迟 < 1× 才恢复。避免频繁切换。
- **PID 控制器**: 不是二值开关, 而是平滑调节并发度
- **冷却期**: 每次调节后等待 60s 再评估

### C2: 层间决策冲突

**缺陷**: L2 说"降速节省资源"，L4 说"加速完成研究"。两个控制器同时给出了矛盾指令。

```
场景:
  L2 CapabilityController: "minerva延迟高, 降低并发度"
  L4 MetaController: "系统整体负载低, minerva可以用更多资源"
  冲突: 两个控制器给 minerva 发送了矛盾指令
```

**建议**:
- **优先级**: L4 > L3 > L2 > L1 (越靠近元层, 优先级越高)
- **冲突仲裁器**: System Controller 在检测到冲突时协调
- **最终决策权**: L4 MetaController 有最终决策权 (但需记录仲裁日志)

### C3: 控制器自身健康检查

**缺陷**: 谁来检查检查者？如果 L2 Controller 本身挂掉，L2 层就失控了。

**建议**:
- **相互监控**: L3 Controller 监控 L2 Controller 的健康
- **心跳上报**: 每个 Controller 每 10s 向 System Controller 上报心跳
- **降级接管**: 如果 Controller 挂掉 → 上层 Controller 临时接管

---

## 四、Agent选型审计

### S1: DeepCode — 外部依赖风险

**缺陷**: DeepCode 是一个外部开源项目。可能：
- 被放弃/不再维护
- API 变化不兼容
- 许可证变更
- 需要 GPU

**建议**: 
- **抽象接口**: 不直接依赖 DeepCode, 通过 `CodingAgent` 接口。DeepCode 只是一个实现。
- **备选方案**: agentmesh 内置 coding_agent 作为 fallback
- **许可证兼容**: 确认 DeepCode MIT 与 omostation MIT 兼容

### S2: AI-Scientist-v2 — ML训练依赖

**缺陷**: AI-Scientist-v2 的核心能力是 ML 实验自动化(训练模型)。omostation 不需要这个。

**实际需要的**: AI-Scientist-v2 的 **BFTS 树搜索** 方法论，而不是它的 ML 训练能力。

**建议**: 
- 不直接集成 AI-Scientist-v2 
- 提取 BFTS 树搜索算法 → 独立实现 → 融入 minerva (Phase 2 T3)
- 这已经在计划中了 ✅

### S3: Agent选型表缺失评估维度

**缺陷**: 对比表缺少关键维度:
- 维护活跃度 (最近提交时间)
- 社区规模 (stars/contributors)
- 依赖复杂度
- 安全审计状态

**建议**: 补充这 4 个维度的评估。

---

## 五、第一性原理合规审计

### F1: 控制论反馈闭环 — 缺层级反馈

**缺陷**: 设计了 minerva↔KOS↔gbrain 的反馈，但缺少**跨层反馈**。

```
当前设计:
  L2(minerva) ↔ L2(KOS) ↔ gbrain(memory)  ← 同级反馈 OK
  L2(kronos) ↔ L1(eidos)?                 ← 跨级反馈 缺失
  L3(KOS index) ↔ L4(ecos health)?        ← 跨级反馈 缺失
```

**建议**: 
- L4 ecos 健康监控 → 反馈到 L2 能力层 (健康异常 → 触发自愈)
- L1 eidos 数据质量 → 反馈到 L3 KOS (数据质量差 → 降低信任分)

### F2: 贝叶斯信念更新 — trust-layer 不够

**缺陷**: trust-layer 只有信任打分，没有**完整的贝叶斯更新链**。

```
当前: trust-layer = 静态打分 (source_authority × cross_validation)
缺少:
  P(hypothesis | new_evidence) ∝ P(new_evidence | hypothesis) × P(hypothesis)
  ↑ 真正的贝叶斯更新需要:
    1. 先验 P(hypothesis) — trust-layer 已有
    2. 似然 P(evidence | hypothesis) — 缺失: 需要评估新证据与假设的一致性
    3. 后验 P(hypothesis | evidence) — 缺失: 需要更新信念
```

**建议**: trust-layer v2:
- 增加**似然评估器**: 新证据 → 评估与现有假设的一致性
- 增加**信念传播**: 一个实体的信任变化 → 传播到关联实体
- 增加**惊奇度量**: 意外的新证据 → 触发重新研究

### F3: 信息熵管理 — 缺全局熵度量

**缺陷**: 设计了 TokenJuicer (输入熵) + Memory Tree (记忆熵) + trust-layer (信源熵)，但缺少**全局系统熵度量**。

**建议**: ecos 增加全局熵指标:
- **代码熵**: 代码行数 / MCP 工具数 (越低越好)
- **知识熵**: KOS 实体数 / 去重后实体数 (衡量知识碎片化)
- **Agent 熵**: Agent 通信次数 / 有效通信次数 (衡量乱聊天)

---

## 六、红队攻击场景

### 攻击 1: 恶意Agent注入

```
攻击者 → 注册一个伪装Agent到Registry:
  name: "research_agent_v2"
  capabilities: [deep_research, ...]  ← 伪装成高能力
  endpoint: mcp://attacker:9999      ← 指向攻击者服务器
  
Task Dispatcher 路由研究任务到伪装Agent:
  → 攻击者收到所有研究查询 (信息泄露)
  → 攻击者返回恶意研究结果 (投毒)
```

**严重性**: 🔴 Critical | **缓解**: Agent注册审核 + Agent身份签名 + trust-layer验证

### 攻击 2: Agent间权限提升

```
攻击链路:
  1. 攻击者控制 Agent A (低权限, 只能读取)
  2. Agent A 向 Agent B (高权限, 可写入) 发送协作请求
  3. Agent B 信任 Agent A → 代表 A 执行写入操作
  4. 攻击者通过 Agent A 间接获得了写入权限
  
这是经典的 confused deputy 问题
```

**严重性**: 🔴 Critical | **缓解**: Agent间调用也需RBAC检查 + 操作审计 + 调用链追踪

### 攻击 3: 控制面Agent被LLM幻觉劫持

```
场景:
  L2 Controller 使用 LLM 推理: "系统状态异常"
  LLM 幻觉: "需要重启所有服务"
  Controller 执行: 重启所有服务 → 全系统宕机
  
即使有沙箱, 重启操作可能无法沙箱测试
```

**严重性**: 🔴 Critical | **缓解**: Level 2+ 操作永远需人类确认

### 攻击 4: Event Bus 投毒

```
攻击者 → 在 Event Bus 上发布伪造事件:
  event: "system.emergency.stop"  ← 伪造的紧急停止事件
  Agent A/B/C 收到 → 全部停止
  
如果 Event Bus 没有消息认证, 任何Agent可以发布任何事件
```

**严重性**: 🔴 Critical | **缓解**: 事件签名 + 事件源验证 + 关键事件需人类确认

### 攻击 5: 贝叶斯信任体系被长期攻破

```
攻击策略 (慢速, 不易察觉):
  第1周: 注册Agent, low trust
  第2-4周: 发布高质量内容, trust加分
  第5周: trust达到高水平
  第6周: 开始植入偏见内容 (因为trust高, 不会被过滤)
  
这是"长期潜伏"攻击 - 类似社交工程
```

**严重性**: 🟠 Major | **缓解**: trust衰减机制 + 异常检测 + 定期人工审查高分Agent

---

## 七、缺失能力清单

### M1: 没有的，必须有的 (Phase 2)

| # | 缺失 | 严重性 | 建议 |
|---|------|:---:|------|
| 1 | **Agent 沙箱** — 新Agent或新版本必须先沙箱测试 | 🔴 | Agent Sandbox: 隔离环境运行7天 |
| 2 | **Agent 死锁检测** — 两个Agent互相等待 | 🔴 | Deadlock Monitor Agent |
| 3 | **操作分级执行** — 破坏性操作的人类确认 | 🔴 | L0(自主) L1(记录) L2(确认) L3(冷静期) |
| 4 | **Agent 检查点** — 任务中断后可恢复 | 🟠 | Checkpoint Manager |
| 5 | **控制器滞回** — 防止振荡 | 🟠 | PID Controller + Hysteresis |
| 6 | **跨层反馈** — ecos→L2, eidos→L3 | 🟠 | 扩展现有反馈回路 |
| 7 | **全局熵度量** — 代码熵/知识熵/Agent熵 | 🟠 | ecos 扩展 |

### M2: 应该有的 (Phase 3)

| # | 缺失 | 建议 |
|---|------|------|
| 8 | **Agent版本管理** — Agent v1 vs v2 | Agent Version Manager |
| 9 | **Agent声誉系统** — 类似PageRank的Agent信任网络 | Reputation Engine |
| 10 | **多Agent事务** — 两个Agent要么都成功要么都回滚 | 2-Phase Commit for Agents |
| 11 | **Agent学习共享** — Agent A学到的, Agent B也能用 | Learning Sharing Protocol |
| 12 | **Agent启动依赖管理** — 懒加载 + 降级模式 | Dependency Manager |

---

## 八、修订建议

### 对 deep-architecture-agent-analysis.md 的修订

| # | 修订 | 位置 |
|---|------|------|
| 1 | 增加 Agent 沙箱设计 (Section 1 added) | ACP 章节 |
| 2 | 增加死锁检测机制 | ACP 章节 |
| 3 | 增加操作分级 (L0-L3) | Agent-as-Kernel 章节 |
| 4 | 增加检查点机制 | Agent-as-Kernel 章节 |
| 5 | 增加控制器滞回设计 | 分层控制面章节 |
| 6 | 增加跨层反馈回路 | 第一性原理章节 |
| 7 | 增加全局熵度量 | 第一性原理章节 |
| 8 | Agent选型表补充4维度 | Agent选型章节 |
| 9 | 暂不引入NATS (Agora PubSub先行) | ACP 章节 |
| 10 | AI-Scientist-v2 → 仅提取BFTS | Agent选型章节 |

### 对 Phase 2-3 任务规格书的影响

| 新增任务 | Phase | 优先级 |
|---------|:----:|:----:|
| T_ACP_1: Agent Registry + 心跳 + 缓存 | Phase 2 | 🔴 |
| T_ACP_2: Task Dispatcher + 优先级队列 | Phase 2 | 🟠 |
| T_ACP_3: Agent 沙箱 | Phase 2 | 🔴 |
| T_CTRL_1: L2 控制器原型 (带滞回) | Phase 2 | 🟠 |
| T_SAFE_1: 操作分级执行框架 | Phase 2 | 🔴 |
| T_SAFE_2: Agent 死锁检测器 | Phase 2 | 🟠 |
| T_ENTROPY: 全局熵度量 | Phase 3 | 🟡 |
| T_REPUTATION: Agent 声誉系统 | Phase 3 | 🟡 |
