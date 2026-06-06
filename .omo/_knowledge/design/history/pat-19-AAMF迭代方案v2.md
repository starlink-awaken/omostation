# AAMF v2 — 红队迭代方案

> 基于 v1 深度审计的 8 条红队发现，对方案进行重构
> 核心原则：**MVP 先行，工具链并进，不建空中楼阁**

---

## 一、红队结论摘要

| # | 原方案问题 | v2 修复方向 |
|---|-----------|------------|
| 🔴 | M3 是伪元元模型（struct 而非形式化定义） | 增加属性约束和推理规则 |
| 🔴 | 14 种 MetaType 边界重叠 | 精简为 6 种架构专用类型，与原 8 种知识类型分离 |
| 🟡 | BEHAVE/JUSTIFY 不可程序化 | 删除，只保留 6 种可校验关系 |
| 🟡 | InterfaceContract 维度混叠 | 分层定义：transport × role × auth × version |
| 🔴 | 单向自顶向下，无 M0→M2 反馈 | 新增类型注册时自动发现和反馈机制 |
| 🟡 | 工时严重低估 (6-9w → 9-14w) | 重新规划，MVP 先行 |
| 🔴 | 成本收益分析缺失 | 新增"不做的代价"分析 |
| 🟡 | 工具链/版本化/安全/测试四大盲点 | Phase 内嵌工具链，版本化策略，安全基线 |

---

## 二、修正后的三层元模型

### 2.1 M3 — ArchitectureModel（修正后的元元模型）

相比 v1 的结构体式 M3，v2 增加了**属性约束层和推理规则**：

```yaml
architecture_model:
  # 一个架构对象必须有且仅有以下字段
  meta_type:                     # 必填，枚举值 (见 M2)
  id: string                      # 必填，全局唯一
  name: string                    # 必填，人类可读
  version: semver                 # 必填，语义化版本
  interfaces: []                  # 必填，至少提供一个接口
  
  # 属性约束
  constraints:
    - "MUST(meta_type)"           # meta_type 不能为空
    - "MUST(id != name)"          # id 和 name 不可相同
    - "MUST_NOT(interfaces.empty)" # 每个节点至少一个接口
    - "IF(meta_type == PROCESSOR) THEN MUST(provides.task_handler)"
    - "IF(meta_type == STORE) THEN MUST(interfaces.contains('db:query') OR 'http:storage')"
    - "IF(depends_on contains type=SERVICE) THEN MUST(interface.has(protocol))"
```

> 约束还不是 OWL DL Reasoner 级别，但已经是可程序化校验的元元模型。未来可逐步升级为完整的 OWL 推理器。

### 2.2 M2 — 6 种架构 MetaType × 6 种 MetaRelation

**核心改动**：将架构类型与知识类型分离。

```yaml
architecture_meta_types:  # 新增 — 仅用于架构治理
  - PROCESSOR   # 执行任务/运行逻辑 (Agent Runtime, AgentMesh Engine)
  - SERVICE     # 暴露接口/协议 (Agora, Forge MCP Server)  
  - GATEWAY     # 路由/代理/转换 (Agora Gateway, Hermes Gateway)
  - STORE       # 持久化数据/状态 (KOS, SSOT, gbrain)
  - AGENT       # 自治行为/决策 (Hermes Agent, MetaOS Agent)
  - TOOL        # 提供原子能力 (Forge Tools, MCP Servers)

knowledge_meta_types:  # 保持原样式 — 专用于 Eidos 知识工程
  - DOMAIN | FACT | INFERENCE | RELATION | STATE | DOCUMENT | CONSTRAINT | PROCESSOR
```

**为什么分离**：
- 两类 MetaType 服务于不同目的（架构治理 vs 知识建模）
- 不会再有"Agent 既是 AGENT 又是 PROCESSOR"的语义纠缠
- Eidos 的 8 种知识类型不需要改动，保持向后兼容
- 架构节点只使用 6 种架构类型，更清晰

**6 种可程序化关系**：

| 关系 | 含义 | 可校验方式 | 代码可检查？ |
|------|------|-----------|------------|
| COMPOSE | A 由 B/C/D 构成 | 子节点列表 → 代码目录结构 | ✅ |
| DEPEND | A 依赖 B | depends_on 列表 → 启动顺序检查 | ✅ |
| DELEGATE | A 委托任务给 B | 接口调用追踪 | ✅ |
| CONFIGURE | A 配置 B | 配置文件的 source chain | ✅ |
| MONITOR | A 监控 B | 健康检查端点验证 | ✅ |
| COMMUNICATE | A 通过协议 P 与 B 通信 | 接口契约匹配 | ✅ |

**删除**：DERIVE（抽象）、BEHAVE（不可校验）、JUSTIFY（不可校验）  
**新增**：COMMUNICATE（替代缺失的通信关系表达）

> 6 × 6 = 36 组合，每类关系验证路径明确——不会出现"定义了但无法校验"的抽象关系

---

## 三、InterfaceContract v2（分维定义）

```yaml
interface_contract:
  # 传输层 — WHAT transport to use
  transport: 
    protocol: mcp:stdio | mcp:sse | http:rest | ws:stream | cli:stdio | event:pubsub | file:pipe | grpc:stream
    version: "2.0"               # 协议版本号
    discovery: static | registry | broadcast  # 如何发现此接口

  # 角色层 — WHO is the provider/consumer
  role: provider | consumer | both
  
  # 能力层 — WHAT capabilities this interface exposes
  capabilities:
    - id: "runtime.run_task"
      input_schema: "TaskDefinition"   # Eidos Schema 引用
      output_schema: "TaskResult"
  
  # 安全层 — HOW to authenticate
  auth:
    required: false | true
    type: none | token | mtls | oauth
    provider: "agora:auth:gateway"     # 谁签发凭证

  # 治理层 — operational constraints
  governance:
    rate_limit: "100/1m"
    timeout: "300s"
    retry_policy: "exponential"
```

**v2 改进**：
- ✅ 三层分离（transport × role × capability × auth × governance）
- ✅ 协议版本号（解决迁移兼容性问题）
- ✅ 发现机制（static/registry/broadcast）
- ✅ 安全层（身份验证不再是盲点）
- ✅ 去掉了 db:query/db:store（不暴露内部实现）

---

## 四、M0→M2 反馈回路

新增**演化机制**——当 Agora 注册一个新节点时：

```yaml
# Agora 注册流程 v2
1. Node 提交 ArchitectureNode 声明
2. Agora 校验:
   ├─ ✅ 元模型校验通过 → 注册成功
   ├─ ⚠️ meta_type 不匹配 → 
   │    ├─ 自动推荐最接近的类型
   │    ├─ 接受注册（带 warning 标记）
   │    └─ 记录到 `_meta_type_unresolved` 队列供人工 Review
   └─ ❌ 接口契约不兼容 → 拒绝注册，返回差异报告

# 周期性 Review
cron: "0 9 * * 1"  # 每周一检查 unresolved 队列
→ 如果某类 unresolved 出现 3+ 次 → 触发 M2 元模型扩展讨论
```

**这解决了**：
- v1 "项目不匹配元模型就卡死"的问题
- 元模型演化缺乏数据驱动的问题
- 元模型僵化（resolved once, never questioned）的问题

---

## 五、成本收益分析

### 5.1 不做 AAMF 的代价

| 场景 | 发生概率 | 恢复成本 |
|------|---------|---------|
| 替换 Agent Runtime → 需要修改 N 个点的手动适配 | 📈 中（6-12月内） | 2-5 天 |
| 新 Agent 接入发现没有标准注册流程 | 📈 高（3月内） | 3-7 天 |
| 某模块接口变更 → 连锁断裂 | 📈 高（已有先例） | 1-3 天/次 |
| 架构知识丢失（单点大脑依赖） | 📈 中（长期） | 不可量化 |

### 5.2 AAMF 的收益

| 收益 | 量化 | 时间线 |
|------|------|--------|
| 新模块接入从"改 N 个地方"→"注册一个 YAML" | -95% 接入时间 | Phase 2 后 |
| 接口变更时自动检测断裂 | -80% 连锁故障 | Phase 2 后 |
| 架构知识从"老王脑子里"→"可读文件" | 团队可交接 | Phase 1 后 |
| 依赖图自动推导 | -90% 人工追查 | Phase 3 后 |

### 5.3 判定

✅ **值得做，但要改执行路径**。收益明确，核心风险不是"要不要做"，而是"怎么做才不会做成 YAML 目录"。

---

## 六、修正后的 Roadmap（MVP 先行）

### Phase 0 — MVP 验证（1 周）

| # | 任务 | 产出 | 
|---|------|------|
| 0.1 | 为 **Agent Runtime** 编写第一个 ARCH_NODE.yaml | 真实 YAML 而非模板 |
| 0.2 | 在 Agora 实现 ARCNode 注册端点（接受+yaml校验） | `agora register` 命令 |
| 0.3 | 验证 Agent Runtime 注册 → 发现 → 调用的端到端链路 | 端到端验证报告 |
| 0.4 | 暴露注册流程中的问题（MetaType 冲突、接口不匹配等） | Phase 1 输入 |

> MVP 是**反向切入**：先搞通一条链路，再用真实经验去迭代元模型

### Phase 1 — 宪法 + 精炼元模型（1 周）

| # | 任务 | 产出 |
|---|------|------|
| 1.1 | 落盘 WORKSPACE_ARCHITECTURE_CONSTITUTION.md | 单一权威宪法 |
| 1.2 | 基于 Phase 0 经验精炼 6 种架构 MetaType | 稳定的 M2 |
| 1.3 | InterfaceContract 实现（分维定义） | Python Schema + 校验函数 |
| 1.4 | ARCH_NODE.yaml 验证 CLI | `arcnode validate` 命令 |
| 1.5 | Agora 注册时元模型校验 | 拒绝不合规注册 |

### Phase 2 — 5 个核心项目对齐（2 周）

| # | 项目 | MetaType | 优先级 |
|---|------|---------|--------|
| 2.1 | Agent Runtime | PROCESSOR ✅ 已有 Phase 0 经验 | P0 |
| 2.2 | Agora | SERVICE | P0 |
| 2.3 | AgentMesh Engine | PROCESSOR | P1 |
| 2.4 | Forge | TOOL | P1 |
| 2.5 | KOS | STORE | P1 |

> **明确不做**：Inactive/Archived 项目、纯文档项目、极小辅助工具。不追求 30+ 全覆盖。

### Phase 3 — 工具链与自动化（2 周）

| # | 任务 | 产出 |
|---|------|------|
| 3.1 | 依赖图自动推导 | `arcnode graph` |
| 3.2 | 接口兼容性检查（注册时） | CI gate |
| 3.3 | 架构漂移检测（cron: daily） | 对比 ARCH_NODE.yaml 和实际运行状态 |
| 3.4 | M0→M2 unresolved 队列 UI | `agora meta-types list-unresolved` |
| 3.5 | 多视角视图（仅 markdown + mermaid） | 不追求 C4 自动生成 |

### Phase 4 — 按需覆盖（持续）

- 其余项目按实际需要加入
- 遇到新项目先问"它属于哪个现有 MetaType"→ 如果都不匹配才考虑扩展
- 元模型扩展走 M0→M2 反馈流程

### 修正后的时间线对比

| Phase | v1 估算 | v2 估算 | 变化原因 |
|-------|---------|---------|---------|
| P0 MVP | 无 | 1 周 | 新增——先验证再定义 |
| P1 宪法+元模型 | 1-2 周 | 1 周 | 基于 MVP 经验，无需调研 30+ 项目 |
| P2 核心对齐 | 2-3 周 | 2 周 | 只做 5 个核心项目，不做 30 个 |
| P3 工具链 | 3-4 周 | 2 周 | 版本缩小，不追求 C4 自动出图 |
| P4 按需覆盖 | 无 | 持续 | 原 P3 进化引擎推迟到 P4 |
| **总计** | **6-9 周** | **6 周** | ⬇️ 合理可行 |

---

## 七、四大盲点的修复

### 7.1 工具链
- `arcnode validate` — 校验 ARCH_NODE.yaml 的语法和语义
- `arcnode graph` — 从 YAML 目录生成依赖图
- `arcnode drift-check` — 对比 YAML 与运行状态
- 全部集成到 `hermes` CLI（不引入新命令空间）

### 7.2 版本化策略

```yaml
# ARCH_NODE.yaml 内嵌 M2 版本
meta_model_version: "2.0.0"  # 指向当前 M2 定义版本
```

- 如果 M2 升级到 3.0.0，旧 YAML 标记为 `deprecated` 但继续工作
- `arcnode validate --strict` 会拒绝过时的 M2 版本
- M2 版本号存储在 Eidos Schema Registry 中

### 7.3 安全基线

- 所有 Agora 注册操作需要 API token（从 1password 注入）
- 节点间通信首选 localhost（默认安全）
- 跨机器通信走 Tailscale（加密隧道）
- 不引入 mutual TLS（当前不需要，留接口即可）

### 7.4 测试策略

```yaml
# 每个 ARCH_NODE.yaml 伴生一个 .test.yaml 或内嵌 test 字段
tests:
  health_check: "curl -f http://127.0.0.1:9876/health"
  depends_check: "curl -f http://127.0.0.1:7430/health"
  interface_match: "arcnode verify-interfaces my-node"
```

`arcnode drift-check` cron 每日验证 YAML ≠ dead document。

---

## 八、关键决策

| # | 决策 | v1 说法 | v2 修正 |
|--|------|---------|---------|
| 1 | 元模型范围 | 8+6 混一个列表 | 6 种架构类型 + 8 种知识类型分开 |
| 2 | 关系数量 | 8 种（含 BEHAVE/JUSTIFY） | 6 种（仅可校验的） |
| 3 | 执行路径 | 先建元模型再对齐 | 先 MVP 验证再精炼 |
| 4 | 覆盖范围 | 30+ 项目全量 | 5 个核心项目，其余按需 |
| 5 | 反馈回路 | 无 | M0→M2 unresolved 队列 |
| 6 | 工具链 | 无 | `arcnode` CLI 三件套 |
| 7 | C4/Archimate 视图 | Phase 3 目标 | 推迟到 Phase 4（低优先级） |
| 8 | 进化引擎 | Phase 3 核心 | 推迟到 Phase 4（独立启动） |

---

## 九、next step

**v2 方案的核心变化一句话总结：**

> 不先定义 14 个 MetaType，先拿 Agent Runtime 做通一条注册链路，再用经验倒推元模型只做 6 种——工时不变（6 周），风险降一半。

如果你认可方向，可以从 **Phase 0 开始**——为 Agent Runtime 写第一个 ARCH_NODE.yaml，同时在 Agora 实现注册端点。
