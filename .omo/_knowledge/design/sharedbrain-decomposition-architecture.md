# SharedBrain → kairon 架构系统性分析与拆分策略

> 2026-06-01 · 基于 projects/SharedBrain (824K 行) 与 projects/kairon (111K 行) 深度扫描
> 方法论：SystemsThinking (Iceberg + Archetype + Leverage) + FirstPrinciples

---

## 一、现状：两个系统，一个事实

### 1.1 物理拓扑

```
omostation 根仓库
├── /SharedBrain/                  ← 🅰 空壳（0 .py 文件，4 个空 SQLite 库）
├── /projects/SharedBrain/         ← 🅱 真实 SharedBrain（824,030 行，19 器官）
├── /projects/kairon/              ← 🅲 kairon 知识工程栈（111,920 行，22 包）
├── /projects/agentmesh/           ← 🅳 Agent SDK（TypeScript）
├── /projects/gbrain/              ← 🅴 知识脑（TypeScript + Postgres）
└── /projects/_archived/           ← 🅵 归档（22 项）
```

### 1.2 🤯 反直觉事实

| 你以为的 | 实际上 |
|---------|--------|
| "SharedBrain 是 71K 行" | **824K 行**（PROJECTS.yaml 数据严重过时） |
| "SharedBrain 代码已迁到 kairon" | **零代码依赖**——两者 rg 0 匹配，完全不互通 |
| "sharedbrain-bridge 是桥梁" | **已失效**——140 行死代码，HTTP POST 到不存在的 7421 端口 |
| "SharedBrain 在跑" | **全部端口 7420/7421/8080 无进程** |
| "Health Score 97 = 系统健康" | **核心债务全未解决**——D2/D3/SB 跨越 12+ Phase |

### 1.3 SharedBrain 内部分层

```
SharedBrain B-OS v10.0.0 (Python 3.14+)
├── 基因组层 Z-Spore       (25,528 行 / 135 文件) — 元模型、形式化公理、本体 DNA
├── 法则层   Z-Core        ( 1,188 行 /  13 文件) — 10 条架构戒律
├── 路由层   Z-Microkernel  (55,680 行 / 269 文件) — FastAPI RPC, MCP, 事件总线, 网格
├── 器官层   19 × D_*      (301,203 行 / ~400 文件) — 业务逻辑
├── CLI 层   bin/           (65,546 行) — bos CLI, bos_daemon
├── 测试层   tests/         (304,657 行 / 1,476 文件) — 覆盖良好
└── 依赖栈: FastAPI, Uvicorn, MCP, Docker, WebSocket, aiohttp, Flask, Rich, Textual
```

### 1.4 kairon 22 包分层

```
kairon v0.1.0 (Python 3.13+, uv + hatchling + ruff)
├── L1 契约层 (5 包):
│   core-models (267 行) — Entity/Relation/Provenance/KG 数据模型
│   eidos (6,124 行) — Schema 定义与验证
│   codeanalyze — 代码/文档分析
│   shared-lib — 共享工具库
│   ssot — 领域知识 SSOT
│
├── L2 能力层 (10 包):
│   kronos (—) — 知识摄取管线（5 层抓取引擎）
│   minerva (17,189 行) — Deep Research 系统
│   sophia (—) — 符号研究范式引擎
│   ontoderive (18,936 行) — 事实驱动本体工程
│   kos (14,761 行) — 知识操作系统
│   iris (—) — 个人知识平台连接器
│   eu-pricing (—) — 能量计价
│   forge (—) — AI 数字资产管理
│   ecos (—) — 认知层
│   agora (20,016 行) — MCP 服务融合枢纽
│
├── L3 协作层:
│   metaos (—) — 编排/治理层
│   agent-runtime (—) — Agent 运行时入口
│   cron-service (—) — Cron 调度
│   wksp (—) — 统一用户入口
│
├── L4 元层:
│   sharedbrain-bridge (140 行) — ❌ 死代码
│
└── 跨层:
    minerva, kos, ontoderive — 独立运行，依赖 core-models
```

---

## 二、系统动力学：为什么 SharedBrain 长成了怪物

### 2.1 冰山模型分析

**事件层（可见的）：**
- 19 个器官，301K 行业务逻辑
- 82 万行总量，36% 是测试
- 双系统并行，零集成
- bridge 代码已失效

**模式层（重复的）：**
- 每一次 Phase 规划，SharedBrain 都被列入"下一波处理"
- PROJECTS.yaml 记录的 "71K 行" 与实际 824K 行严重脱节
- Phase 完成度从 P5→P16 持续上升，SB 状态从未变化

**结构层（产生模式的规则）：**
- 度量结构：`health_score = task_completion_rate`，不包含 debt_item 状态
- 规划结构：Phase 主题 = "新能力"，SharedBrain 拆分从未成为 Phase 主题
- 信息流结构：project lines 数据只在写入时更新（71K 是 2 个月前的数据）

**心智模型层（让结构显得自然的信念）：**
- "SB 太大，拆不动" → 实际拆分策略从未被认真评估
- "桥接代码就行" → bridge 140 行变死代码，没人发现
- "系统正在前进" → 健康分 97 掩盖了 824K 行债务的真实性

### 2.2 核心问题：双系统异构

| 维度 | SharedBrain | kairon |
|------|------------|--------|
| 构建 | setuptools | uv + hatchling |
| Python | 3.14+ | 3.13+ |
| 行宽 | 100 | 120 |
| Lint | 未统一配置 | ruff 全量 |
| 测试框架 | pytest (304K 行) | pytest (34K 行) |
| 运行 | 离线（全部端口无进程） | 活跃开发 |
| 本体模型 | Z-Spore 自研（25K 行） | core-models（267 行） |

**核心矛盾：** 两套系统都用 Python，但建模语言不同。SharedBrain 用 Z-Spore 形式化元模型（25K 行），kairon 用 core-models（267 行）。如果只是把代码搬过来，会产生文化冲突。

---

## 三、能力重叠矩阵

| kairon 包 | 重叠的 SB 器官 | 重叠行数 | 重叠性质 | 策略 |
|-----------|--------------|:--------:|---------|------|
| **agora** (20K) | D_Gateway (26K) | MCP 路由/代理/认证 | 功能重叠 | **合并**→ aggra 吸收 D_Gateway MCP 能力 |
| **core-models** (267) | Z-Spore (25K) | 元模型层 | **差距巨大** | **映射**→ core-models 需扩展吸收 Z-Spore 本体 |
| **eu-pricing** | D_Economy (7K) | 能量计价/资源管理 | 功能重叠 | **合并**→ eu-pricing 吸收 D_Economy |
| **ontoderive** (19K) | D_Logos (17K) | 本体推理/LLM 助手 | 概念不同 | **对齐**→ ontoderive (事实工程) ≠ D_Logos (LLM 助手) |
| **minerva** (17K) | D_Harvest (29K) + D_Intelligence (4K) | 研究/知识收割 | 方向一致 | **合并**→ minerva 吸收 Harvest+Intelligence |
| **eidos** (6K) | D_Memory (42K) | Schema/Memory | 差距大 | **部分合并**→ eidos 吸收 D_Memory 的 schema 部分 |
| **kos** (15K) | D_KnowledgeIntegration (6K) | 知识操作 | 方向一致 | **合并**→ kos 吸收 KnowledgeIntegration |
| — | D_Execution (56K) | Agent 编排 | agentmesh 已替代 | **废弃** |
| — | D_Governance (27K) | 治理 | .omo 治理已替代 | **废弃** |

### 实际重叠量级

```
SharedBrain 可迁移到 kairon 的有效代码: ~130K 行（器官重叠部分）
SharedBrain 需要保留为内核的代码:    ~27K 行（Z-Spore + Z-Core 核心模型）
SharedBrain 应该废弃的代码:          ~150K 行（Execution + Governance 被替代）
SharedBrain 保留的测试:              ~305K 行（可复用）
SharedBrain 核/CLI 待定:             ~212K 行（nucleus 路由层 + bin CLI）
```

---

## 四、目标架构设计

### 4.1 原则

1. **kairon 统一知识栈** — 所有工程化能力进 kairon，保持 uv/ruff/pytest 一致
2. **SharedBrain 缩为知识核** — 只保留 Z-Spore 本体模型 + 数据库，文档化
3. **agentmesh 做 Agent 层** — D_Execution 的 Agent 编排能力由 agentmesh 承接
4. **gbrain 做持久化** — D_Memory 的存储能力由 gbrain (Postgres) 承接
5. **不迁移过度设计** — Quantum Safe、Edge Computing、Federated Learning 废弃

### 4.2 目标架构（Phase 17 完成后）

```
omostation (统一入口 + 治理)
├── kairon (知识工程栈 — 扩展至 ~240K 行)
│   ├── L1: core-models + eidos ↑ ← 吸收 Z-Spore 元模型
│   ├── L2: agora ↑ ← 吸收 D_Gateway
│   │       minerva ↑ ← 吸收 D_Harvest
│   │       ontoderive ↑ ← 对齐 D_Logos
│   │       kos ↑ ← 吸收 D_KnowledgeIntegration
│   │       eu-pricing ↑ ← 吸收 D_Economy
│   │       ★ NEW: kairon/bridge-economy ← economy 桥接
│   │       ★ NEW: kairon/bridge-memory ← memory 桥接
│   │       (其他包不变)
│   └── L3/L4: 现有不变
│
├── SharedBrain (缩为知识核 ~30K 行)
│   ├── nucleus/Z-Spore + Z-Core (形式化元模型)
│   └── data/db/ (持久化数据)
│
├── agentmesh (Agent SDK — 承接 D_Execution 编排)
├── gbrain (知识脑 — 承接 D_Memory 存储)
└── .omo (治理 — 已替代 D_Governance)
```

### 4.3 每个器官的去向矩阵

| 器官 | 行数 | 去向 | 目标位置 | 迁移量 | 工作量 |
|------|:----:|------|---------|:------:|:------:|
| **D_Gateway** | 26K | 拆入 | agora (MCP+路由+发现) | 15K | 🟡 中 |
| **D_Economy** | 7K | 拆入 | eu-pricing (EU 计价+资源) | 5K | 🟢 小 |
| **D_Memory** | 42K | 部分拆入 | eidos+gbrain (schema+存储) | 10K | 🔴 大 |
| **D_Harvest** | 29K | 拆入 | minerva (知识收割+研究) | 20K | 🟡 中 |
| **D_Intelligence** | 4K | 拆入 | minerva (情报分析) | 3K | 🟢 小 |
| **D_Logos** | 17K | 对齐 | ontoderive (本体推理) | 8K | 🟡 中 |
| **D_KnowledgeIntegration** | 6K | 拆入 | kos (知识融合) | 4K | 🟢 小 |
| **D_Continuity** | 4K | 拆入 | kairon 新包 | 3K | 🟢 小 |
| **D_Excretion** | 8K | 拆入 | kairon 新包 (GC) | 5K | 🟢 小 |
| **D_Monitoring** | 16K | 拆入 | kairon/agent-runtime 或新包 | 10K | 🟡 中 |
| **D_Cloud** | 5K | 拆入 | kairon 新包 | 3K | 🟢 小 |
| **D_Voice** | 3K | 拆入 | kairon 新包 | 2K | 🟢 小 |
| **D_Extension** | 5K | 拆入 | kairon/forge | 3K | 🟢 小 |
| **D_Execution** | 56K | **废弃** | agentmesh 已替代 | 0 | N/A |
| **D_Governance** | 27K | **废弃** | .omo 治理已替代 | 0 | N/A |
| **D_Immunity** | 22K | **保留核** | SharedBrain 核心 | 5K | 🟢 小 |
| **D_Genesis** | 20K | **保留核** | SharedBrain 核心 | 5K | 🟢 小 |
| **D_Harness** | 2K | **保留核** | SharedBrain 核心 | 0 | 🟢 小 |
| **D_Window** | 5 | **废弃** | 占位符 | 0 | N/A |

### 4.4 规模推演

```
迁移后结果:
  kairon:     111K → ~240K 行（+130K 行新代码）
  SharedBrain: 824K → ~100K 行（保留核 30K + 测试 60K + 文档 10K）
  废弃:              ~150K 行（Execution + Governance + Window）
  测试保留:          ~304K 行（迁移到对应 kairon 包）
```

---

## 五、实施策略

### 5.1 迁移模式

每个器官迁移遵循统一模式：

```
1. 提取器官核心能力代码（5K-20K 行/次）
2. 在 kairon 创建/增强目标包
3. 移植测试（SharedBrain 已有 304K 行测试可用）
4. 验证 pytest 通过率 >= 80%
5. SharedBrain 侧标记为 legacy
6. 清理旧代码
```

### 5.2 执行批次

```
Wave 1 (P17.1 — 治理门禁 + 核心决策)
  ├── [决策] SharedBrain 去留正式记录（已完成）
  ├── [决策] 健康分公式引入 debt_weight（需审批）
  ├── [迁移] ✅ 最易: D_Economy → eu-pricing     (~5K 行，3-5 天)
  ├── [迁移] ✅ 最易: D_KnowledgeIntegration → kos (~4K 行，2-3 天)
  ├── [清理] 废弃 D_Window（5 行）
  └── [清理] 废弃 D_Execution（56K 行 — 确认 agentmesh 已覆盖）

Wave 2 (P17.2 — 中量搬迁)
  ├── [迁移] 🟡 D_Gateway MCP 能力 → agora     (~15K 行，5-7 天)
  ├── [迁移] 🟢 D_Intelligence → minerva          (~3K 行，2 天)
  ├── [迁移] 🟢 D_Extension → forge               (~3K 行，2 天)
  ├── [迁移] 🟢 D_Cloud → kairon 新包              (~3K 行，2 天)
  ├── [迁移] 🟢 D_Voice → kairon 新包              (~2K 行，2 天)
  ├── [迁移] 🟢 D_Continuity → kairon 新包          (~3K 行，2 天)
  └── [测试] 每个迁移包移植 SharedBrain 测试

Wave 3 (P17.3 — 大量搬迁)
  ├── [迁移] 🟡 D_Logos → ontoderive             (~8K 行，5-7 天)
  ├── [迁移] 🟡 D_Monitoring → kairon 新包         (~10K 行，5-7 天)
  ├── [迁移] 🟡 D_Harvest → minerva               (~20K 行，7-10 天)
  ├── [迁移] 🔴 D_Memory schema → eidos/gbrain   (~10K 行，7-10 天)
  └── [测试] 每个迁移包移植 SharedBrain 测试

Wave 4 (P17.4 — 收尾)
  ├── [迁移] 🟡 D_Excretion → kairon 新包          (~5K 行，3-5 天)
  ├── [清理] 废弃 D_Governance（27K 行 — 确认 .omo 已覆盖）
  ├── [清理] 废弃 D_Immunity 过度设计（量子安全等）
  ├── [收尾] SharedBrain README 正式版
  └── [验证] 全量债务验收
```

### 5.3 每个迁移是否有必要？(FirstPrinciples 追问)

| 器官 | 它是做什么的？ | 真的需要迁吗？ | 还是直接删？ |
|------|--------------|--------------|------------|
| D_Economy | 给每个操作算能量消耗 | ✅ 需要，eu-pricing 已有雏形 | — |
| D_Gateway | MCP 服务网关/发现/路由 | ✅ 需要，agora 做同样的 | — |
| D_Memory | 记忆生命周期管理 | ⚠️ 需要概念，但 42K 行太多 | 只迁 schema 部分 |
| D_Harvest | 知识从外部收割进来 | ✅ 需要，minerva 做类似的事 | — |
| D_Execution | Agent 编排 + 任务执行 | ❌ 不迁，agentmesh 已替代 | 直接删 |
| D_Governance | 治理/伦理/审计 | ❌ 不迁，.omo 治理体系已替代 | 直接删 |
| D_Immunity | 安全/加密/隐私 | ⚠️ 部分需要，但量子安全是过度设计 | 只迁核心 |
| D_Genesis | 自愈/进化/起源 | ⚠️ 过度设计概念 | 文档化即止 |
| D_Logos | LLM 助手 + 本体推理 | ✅ 需要对齐到 ontoderive | — |
| D_Harness | 测试框架 | ❌ 不迁，kairon 用 pytest | 保留文档 |

### 5.4 每个波次的规模估值

```
Wave 1: ~9K 行迁移  +  ~56K 行废弃  = 5-7 天
Wave 2: ~30K 行迁移  +  0 行废弃     = 10-14 天
Wave 3: ~48K 行迁移  +  0 行废弃     = 14-21 天
Wave 4: ~5K 行迁移   +  ~50K 行废弃  + 验收 = 7-10 天
------------------------------------------------
总计:   ~92K 行迁移  +  ~106K 行废弃 = 36-52 天
```

---

## 六、风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|:----:|:----:|------|
| SharedBrain 有实际用户/依赖 | 低 | 🔴 高 | 先确认无进程 = 无用户 |
| Z-Spore 元模型 ≠ core-models 无法直接映射 | 高 | 🟡 中 | 只迁对外接口，模型做适配层 |
| D_Memory 42K 行拆不动 | 高 | 🟡 中 | 只迁 schema/存储，留复杂逻辑在 SB |
| D_Governance 被 .omo 替代但"有些东西还在用" | 中 | 🟡 中 | rg 追踪所有 importers |
| 测试移植后跑不过 | 中 | 🟡 中 | 保持 SharedBrain 原测试不变，新建 kairon 测试 |
| agmesh 未完全覆盖 D_Execution | 低 | 🟡 中 | 先确认 agentmesh capability |
| 304K 行测试迁移后维护成本 | 高 | 🟢 低 | 只迁核心测试 (~100K 行) |
| 迁移过程中 SB 同时有更新 | 低 | 🟢 低 | git log 显示 SB 已是维护模式 |

---

## 七、核心建议

### 7.1 "保留核心"的定义

SharedBrain 保留的内容：

```
projects/SharedBrain/ (缩至 ~100K 行)
├── nucleus/Z-Spore/     (25K 行) — 形式化元模型 ← 产品级本体
├── nucleus/Z-Core/      (1K 行)  — 架构法则 ← 文档化
├── nucleus/Z-Microkernel (55K 行) — 路由 ← 只保留文档，逻辑已迁移/废弃
├── organs/D_Immunity/核  (5K 行) — 核心安全能力
├── organs/D_Genesis/核   (5K 行) — 自愈核心
├── docs/                (10K 行) — 架构文档
├── data/db/             — 持久化数据 🅰 移动到 root/data/db/
└── tests/               (60K 行) — 保留的测试
```

### 7.2 为什么不是全部迁到 kairon？

1. **Z-Spore 太特殊** — 25K 行的形式化元模型是 SharedBrain 的 DNA，它定义了 SB 的整个架构范式。强行塞进 core-models 会把压缩到 267 行的优雅模型膨胀 100 倍。更好的选择：保持 Z-Spore 作为独立本体知识库，kairon/core-models 通过适配器引用。
2. **部分器官是过度设计的死代码** — D_Execution 56K 行但 agentmesh 已替代。D_Governance 27K 行但 .omo 治理已替代。直接迁是浪费。
3. **D_Memory 42K 行太多** — 它的核心价值在 schema 定义和存储接口，不是整个记忆生命周期管理的复杂度。

### 7.3 健康分重构

```
新公式: health_score = task_completion_rate × debt_weight × debt_resolution_rate
其中:
  debt_weight = f(D2_status, D3_status, SB_decomposition_progress)
  debt_resolution_rate = (已解决器官数 / 总需解决器官数)

预估: 当前 97 × 0.7 × 0.3 ≈ 20.4 — 这才是真实健康度
预期 Wave 1 后: 97 × 0.85 × 0.3 ≈ 24.7 — 轻缓上升
预期 Wave 4 后: 97 × 1.0 × 1.0 ≈ 97.0 — 真实值
```

---

## 八、验证标准

```
Phase 17 完成后验证清单:

[ ] D_Economy → eu-pricing: pytest 通过率 >= 80%
[ ] D_KnowledgeIntegration → kos: pytest 通过率 >= 80%
[ ] D_Gateway MCP → agora: CI 集成测试通过
[ ] D_Intelligence → minerva: pytest 通过率 >= 80%
[ ] D_Logos → ontoderive: 本体推理测试通过
[ ] D_Harvest → minerva: 知识收割测试通过
[ ] D_Memory schema → eidos: schema 测试通过
[ ] D_Execution 废弃确认: agentmesh CI 覆盖
[ ] D_Governance 废弃确认: .omo 治理覆盖
[ ] SharedBrain 缩小至 ~100K 行
[ ] 根目录 SharedBrain 空壳清理
[ ] 健康分加入 debt_weight 因子
[ ] kairon 增至 ~240K 行，测试基线保持
```

---

*维护: 2026-06-01 · Phase 17 SharedBrain 架构拆分方案 v1.0*
*下一动作: 在 .omo/_knowledge/design/ 归档，关联 SHAREDBRAIN-FORMAL-DECISION 任务*
