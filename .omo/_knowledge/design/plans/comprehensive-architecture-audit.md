# 全景架构深度审查：SSOT 本体拆解与缺口分析

> 日期: 2026-05-29 | 版本: v1.0
> 输入: ~/Documents、iCloud、Model/卷、SharedDisk/卷、Desktop、TOOL_REGISTRY、Hermes
> 分析框架: 4+1+3+I 架构模型 + SSOT 本体建模

---

## 目录

1. [数据全景：你拥有什么](#一数据全景你拥有什么)
2. [SSOT 本体拆解：统一领域建模](#二ssot-本体拆解统一领域建模)
3. [4+1+3+I 架构推演：缺口分析](#三413i-架构推演缺口分析)
4. [AI 应用场景对标](#四ai-应用场景对标)
5. [缺失能力清单](#五缺失能力清单)
6. [架构演进建议](#六架构演进建议)

---

## 一、数据全景：你拥有什么

### 1.1 知识矩阵

| 来源 | 位置 | 规模 | 内容域 | omostation 关联度 |
|------|------|------|--------|:----------------:|
| **学习进化** | ~/Documents/Obsidian | 317 .md, 3.1GB | AI架构/方法论/项目/新闻/专利 | ⭐⭐⭐⭐⭐ 核心知识库 |
| **知识库** | ~/Documents/Obsidian | 空壳 | LLM Wiki 结构 | ⭐⭐ 待填充 |
| **Claude 数据** | ~/Documents/Claude | KOS 状态 700/10165 docs | AI 会话资产 | ⭐⭐⭐⭐ 需要修复 |
| **基建架构** | 学习进化/基建架构/ | 68 篇 | 宪法/Phase0-6/机制 | ⭐⭐⭐⭐⭐ 架构知识的源头 |
| **KEMS v3.0** | 学习进化/经验积累/ | 完整方法论 | 四平面+三链+三协议 | ⭐⭐⭐⭐⭐ 可运行时化 |

### 1.2 工作矩阵

| 项目 | 位置 | 规模 | 领域 | 成熟度 | 可复用度 |
|------|------|------|------|:------:|:--------:|
| **卫健委** | ~/Documents/工作文档/ | 16 目录+助手系统 | 卫生健康公文 | ⭐⭐⭐⭐ | 工作助手模板 |
| **国转中心** | ~/Documents/工作文档/ | 22 目录+Wiki | 绿色能源技术转化 | ⭐⭐⭐⭐⭐ | ALE框架+方法论源头 |
| **合同协议** | ~/Documents/工作文档/ | 20 PDF | IT基础设施 | — | 法律文本参考 |
| **法律法规** | ~/Documents/工作文档/ | PDF+WPS | 行政法规 | — | 政府文档格式 |

### 1.3 能力矩阵

| 能力 | 现状 | 位置 | 规模 |
|------|------|------|------|
| **本地 LLM** | 462GB 模型 | /Volumes/Model/ | LMStudio(449G) + ollama(13G) |
| **MCP 工具** | 33+ 服务器 | 多配置 | 8 OpenCode + 15 Claude + 6 ECC + ~12 kairon |
| **Hermes Agent** | 10+ 平台入口 | ~/.hermes/ | CLI/Discord/微信/Telegram 等 |
| **Agora 网关** | 统一 SSE | :7431 | 通往所有下游 MCP 服务 |
| **Obsidian 工具** | vault-ops + KOS | 99-系统/tools/ | Python 脚本 |
| **公文模板** | 数万篇 | ~/Documents/公文模版/ | 16 PPT 类 + 通用模板 |

### 1.4 存储矩阵

| 存储 | 总容量 | 已用 | 主要用途 |
|------|:------:|:----:|------|
| **Mac SSD** | — | — | 工作空间+文档 |
| **iCloud** | — | 31GB | 知识库同步+配置分发 |
| **Model 卷** | 931GB | 553GB | LMStudio(449G)+Docker(76G)+ollama(13G) |
| **SharedDisk (SMB)** | 5.5TB | 48GB | 备份+媒体+软件归档 |
| **Desktop** | — | 1.4MB | 审计报告+临时文件 |

---

## 二、SSOT 本体拆解：统一领域建模

### 2.1 一级领域模型

```
omostation: Personal AI OS
├── 🧠 Knowledge     知识域
│   ├── Architecture    架构知识 (Obsidian/基建架构)
│   ├── Methodology     方法论 (KEMS v1/v2/v3)
│   ├── Research        研究 (报告/论文/资讯)
│   └── Reference       参考资料 (认知科学/心理/游戏)
│
├── 💼 Work          工作域
│   ├── Government      政府事务 (卫健委)
│   ├── Consulting      咨询服务 (国转中心)
│   ├── Legal           法律法规
│   └── Templates       公文模板库
│
├── 👨‍👩‍👧‍👦 Family        家庭域
│   ├── Members         成员档案
│   ├── Health          医疗健康
│   ├── Education       教育成长
│   └── Assets          资产设备
│
├── 🤖 AI             AI 能力域
│   ├── Models          模型资产 (462GB 本地+API)
│   ├── Agents          Agent 类型 (30+)
│   ├── Tools           MCP 工具 (33+)
│   ├── Skills          Agent 技能 (40+)
│   └── Pipelines       处理管线
│
├── ⚙️ System        系统域
│   ├── Architecture    4+1+3+I 架构
│   ├── Governance      .omo 治理 (89 docs)
│   ├── Operations      ops 运维 (监控/备份/健康)
│   ├── Security        安全 (RBAC/免疫/护栏)
│   └── Economy         EU 资源会计
│
├── 📁 Data          数据域
│   ├── Obsidian        Obsidian vaults
│   ├── iCloud          iCloud Drive
│   ├── SharedDisk      NAS 存储
│   └── Desktop         桌面文件
│
└── 🎬 Media         媒体域
    ├── Photos          照片 (家庭档案)
    ├── Videos          视频 (家庭视频)
    ├── Music           音乐
    └── Movies          电影
```

### 2.2 二级实体模型（每领域核心实体）

| 领域 | 核心实体 | 当前建模状态 |
|------|---------|:----------:|
| **Knowledge** | Article, Book, Paper, Note, Concept, Tag, Source | KOS 有索引但退化（10165→700） |
| **Work** | Project, Task, Document, Meeting, Decision, Regulation | 卫健委/国转中心各有独立建模 |
| **Family** | Member, HealthRecord, EducationPlan, Event, Asset | FamilyShared 有部分建模 |
| **AI** | Model, Agent, Tool, Skill, Pipeline, ModelBenchmark | TOOL_REGISTRY + Agora registry 有部分 |
| **System** | Service, Port, Config, Rule, Alert, HealthMetric | .omo + Hermes ports registry 有部分 |
| **Data** | Vault, File, Directory, Mount, SyncStatus | 无统一建模 |
| **Media** | Photo, Video, Audio, Album, Collection | 无建模 |

### 2.3 关系模型（跨域连接）

```
Article ──[references]──→ Paper
Project ──[uses]──→ Methodology
HealthRecord ──[belongs_to]──→ Member
Agent ──[has_permission]──→ Tool
Service ──[exposes]──→ Port
Model ──[benchmarked_by]──→ ModelBenchmark
Document ──[stored_in]──→ Vault
KnowledgeEntity ──[indexed_in]──→ KOS
```

---

## 三、4+1+3+I 架构推演：缺口分析

### 3.1 L1 契约层 — 缺口

| 当前 | 缺口 | 建议 |
|------|------|------|
| core-models: Entity, Relation, KnowledgeGraph, Provenance | **无 Family、Work、Media 域实体模型** | 新增 `family-models`, `work-models`, `media-models` |
| eidos: 22 Schemas | **无 Obsidian vault schema、文档模板 schema** | 新增 `vault-schema`, `template-schema` |
| | **无 KEMS 方法论形式化 Schema** | 新增 `methodology-schema` — 让 KEMS 从静态文档变成可验证的 Schema |

### 3.2 L2 能力层 — 缺口

| 当前 | 缺口 | 建议 |
|------|------|------|
| kronos: 4 层抓取管道 | **不支持 Obsidian vault 直接摄取** | 新增 `kronos/ingest/vault_adapter.py` |
| | **不支持公文模板库索引** | 新增模板发现+分类管道 |
| minerva: 深度研究 | **不支持跨域研究（家庭+工作+知识）** | 新增 `minerva/cross_domain_research.py` |
| | **不支持方法论驱动的结构化研究** | 集成 KEMS 方法栈到研究管道 |
| ontoderive: 本体推导 | **仅推导知识域** | 扩展到全部 7 个域 |
| ssot: 单一事实源 | **仅注册 SharedBrain domain** | 扩展到全部 7 个域 |
| eu-pricing: EU 会计 | **仅 kairon pipeline** | **无** — 已有扩展计划（Phase 2） |

### 3.3 L3 协作层 — 缺口

| 当前 | 缺口 | 建议 |
|------|------|------|
| forge: 工具图谱治理 | **无模型资产管理**（462GB 模型无库存） | 新增 `forge/model_garden.py` — 模型版本/大小/性能跟踪 |
| kos: 知识 OS | **索引从 10165→700 严重退化** | 🔴 **紧急修复** — 重建 KOS 索引 |
| | **无跨 vault 统一搜索**（Obsidian×2 + 知识库） | 新增 `kos/unified_vault_search.py` |
| iris: 连接器 | **无 Apple 生态连接**（Notes/Calendar/Reminders） | 新增 `iris/apple_connector.py` |
| | **无 WeChat 连接**（消息/文件/联系人） | 新增 `iris/wechat_connector.py` |
| | **无 SMB/NAS 连接**（SharedDisk 5.5TB） | 新增 `iris/smb_connector.py` |
| | **无 iCloud 数据访问** | 新增 `iris/icloud_connector.py` |

### 3.4 L4 元层 — 缺口

| 当前 | 缺口 | 建议 |
|------|------|------|
| agent-runtime: Agent 生命周期 | 旧版（:9876），待 agentmesh 吸收 | 已有融合路线图 |
| metaos: 系统编排 | **无设备协同**（mbp-m5 + y7000p 两机协作） | 新增 `metaos/device_orchestrator.py` |
| | **无家庭 OS 调度**（提醒/健康/教育） | 新增 `metaos/family_os_scheduler.py` |
| ecos: 认知监控 | **无 KOS 健康自愈**（索引退化未被检测） | 🔴 新增 `ecos/kos_health_monitor.py` |
| cron-service: 调度 | **已有 12 job**，但未充分利用 | 扩展到自动备份/同步/健康检查 |
| wksp: CLI | 仅知识研究 | **无家庭/工作/系统管理命令** |

### 3.5 I0 集成织物 — 缺口

| 当前 | 缺口 | 建议 |
|------|------|------|
| Agora: 统一 MCP 网关 (:7431) | **未连接 Apple 生态** | 通过 iris/apple_connector 连接 |
| | **未连接 WeChat** | 通过 iris/wechat_connector 连接 |
| | **未连接 SMB/NAS** | 通过 iris/smb_connector 连接 |
| | **未连接 Obsidian vault** | 通过 kronos/vault_adapter 连接 |

### 3.6 X 跨切面 — 缺口

| 当前 | 缺口 | 建议 |
|------|------|------|
| ops: 运维 | **无统一备份策略**（SSD/iCloud/SharedDisk 三方存储） | 新增 `ops/backup_strategy.py` |
| | **无数据隐私隔离**（工作/家庭/个人数据混存） | 新增 `ops/data_isolation.py` |
| | **无 KOS 健康监控** | 新增 `ops/kos_health.py` |
| Security | **无 Apple 生态安全策略** | 新增 iCloud 访问权限模型 |
| | **无多设备安全策略** | 新增设备间认证 |

---

## 四、AI 应用场景对标

### 4.1 主流 AI 场景 × omostation 对标

| 场景 | 主流方案 | omostation 现状 | 缺口 |
|------|---------|:--------------:|------|
| **个人知识管理 (PKM)** | Obsidian + AI 插件 / Mem.ai / Reflect | ✅ 有 Obsidian vault | 🔴 KOS 索引退化，无自动整理 |
| **工作助手** | Copilot / Cursor / Claude Code | ✅ 卫健委/国转中心 AI 系统 | 🟡 公文模板库未接入 AI 管线 |
| **家庭 OS** | 无成熟方案 | ⚠️ FamilyShared 有结构 | 🔴 无运行时调度 |
| **模型花园** | Ollama / LM Studio / OpenRouter | ✅ 462GB 本地模型 | 🔴 无统一库存和基准测试 |
| **深度研究** | GPT Researcher / Perplexity / Elicit | ✅ minerva L0-L4 | 🟡 未接入 PKM 个人知识库 |
| **Agent 平台** | CrewAI / AutoGen / LangGraph | ✅ agentmesh 30+ Agent | 🟡 未接入家庭/工作场景 |
| **内容创作** | Jasper / Copy.ai / WPS AI | ✅ content-creator skill | 🟡 未接入公文模板库 |
| **代码助手** | Copilot / Cursor / Claude Code | ✅ agentmesh + codeanalyze | 🟡 未接入 SharedWork 90+ 项目 |
| **生活 OS** | Motion / Akiflow / Notion Calendar | ⚠️ Hermes cron-service | 🔴 无日历/提醒/习惯跟踪 |

### 4.2 独有场景（omostation 独特的护城河）

这些是通用 AI 产品无法覆盖的、只有 omostation 能做到的场景：

| 场景 | 独特能力 | 价值 |
|------|---------|------|
| **跨域知识融合** | KOS 统一索引代码+文档+知识+家庭+工作 | 一个查询看清所有维度的关联 |
| **方法论驱动研究** | KEMS 四平面+三链指导 minerva 研究 | 不是随便搜搜，是有方法论的深度研究 |
| **合规安全屏障** | SharedBrain 免疫+护栏+审计 | AI 自主操作的安全网 |
| **虚拟资源会计** | EU 经济全链路计价 | 每次 AI 调用的成本可见 |
| **本地优先** | 462GB 本地模型 + 离线可用 | 隐私+速度+无 API 费用 |
| **公文写作** | 数万篇模板 + 卫健委实战 | 通用 AI 产品没有的领域深度 |

---

## 五、缺失能力清单

### 5.1 🔴 Critical — 必须在 Phase 1-2 解决

| # | 缺失 | 影响 | 建议包 |
|---|------|------|--------|
| C1 | **KOS 索引修复** (10165→700) | 知识检索能力崩溃 | `kos-repair` — Phase 1 紧急任务 |
| C2 | **Obsidian vault 连接器** | 主知识库未接入 kairon | `iris/obsidian_connector.py` — Phase 2 |
| C3 | **Apple 生态连接器** | Notes/Calendar/Reminders 未接入 | `iris/apple_connector.py` — Phase 2 |
| C4 | **KOS 健康监控** | 索引退化未被检测 | `ecos/kos_health_monitor.py` — Phase 2 |
| C5 | **SSOT 域扩展** | 仅注册 SharedBrain domain | 扩展到全部 7 个域 — Phase 2 |

### 5.2 🟠 Major — Phase 3 解决

| # | 缺失 | 建议包 |
|---|------|--------|
| M1 | **模型花园** — 462GB 模型无库存/基准测试 | `forge/model_garden.py` |
| M2 | **家庭 OS 调度** — 提醒/健康/教育 | `metaos/family_os_scheduler.py` |
| M3 | **跨域研究引擎** — minerva 跨越 7 个域 | `minerva/cross_domain_research.py` |
| M4 | **KEMS 运行时** — 从文档到可执行方法论 | `sophia/kems_runtime.py` |
| M5 | **WeChat 连接器** — 消息/文件/联系人 | `iris/wechat_connector.py` |
| M6 | **设备协同** — mbp-m5 + y7000p | `metaos/device_orchestrator.py` |

### 5.3 🟡 Minor — Phase 4+ 解决

| # | 缺失 | 建议包 |
|---|------|--------|
| N1 | **公文模板库 AI 管线** | `kronos/templates/template_pipeline.py` |
| N2 | **SMB/NAS 连接器** | `iris/smb_connector.py` |
| N3 | **媒体文件索引** — 图片/视频目标检测+标签 | minerva 多媒体扩展 |
| N4 | **数据隐私隔离** — 工作/家庭/个人 | `ops/data_isolation.py` |
| N5 | **统一备份策略** — 三方存储自动化 | `ops/backup_strategy.py` |

---

## 六、架构演进建议

### 6.1 当前架构健康评估

| 维度 | 当前 | 目标 (Phase 4) | 缺口 |
|------|:----:|:-------------:|------|
| L1 契约层 | 2 域 (知识+系统) | 7 域 | +5 域 |
| L2 能力层 | 7 包 | 10 包 | +3 包 (family/work/media) |
| L3 协作层 | 3 包 | 5 包 | +2 包 (model-garden, cross-domain) |
| L4 元层 | 5 包 | 8 包 | +3 包 (device, family-os, kos-health) |
| I0 织物层 | 1 网关 | 1 网关 (能力增强) | +4 iris 连接器 |
| SSOT 域 | 1 域 | 7 域 | +6 域 |
| MCP 工具 | 33+ | 50+ | +17 工具 |

### 6.2 建议新增的 kairon 包

```
kairon/packages/ 新增:
├── family-models/         L1 — 家庭域实体模型
├── work-models/           L1 — 工作域实体模型
├── media-models/          L1 — 媒体域实体模型
├── model-garden/          L2 — 模型资产管理
├── cross-domain/          L3 — 跨域研究引擎
├── kems-runtime/          L3 — KEMS 方法论运行时
├── device-orchestrator/   L4 — 设备协同
├── family-os/             L4 — 家庭 OS 调度
└── kos-health/            L4 — KOS 健康监控
```

### 6.3 建议新增的 iris 连接器

```
kairon/packages/iris/ 新增:
├── obsidian_connector.py    — 读写 Obsidian vault
├── apple_connector.py       — Apple Notes/Calendar/Reminders
├── wechat_connector.py      — 微信消息/文件/联系人
├── smb_connector.py         — SMB/NAS 文件索引
└── icloud_connector.py      — iCloud Drive 文件同步
```

### 6.4 修复优先级

```
🔴 现在 (Phase 1):
  C1: KOS 索引修复
  C5: SSOT 7 域注册

🟠 短期 (Phase 2):
  C2: Obsidian 连接器
  C3: Apple 生态连接器
  C4: KOS 健康监控
  M1: 模型花园
  M4: KEMS 运行时

🟡 中期 (Phase 3):
  M2: 家庭 OS 调度
  M3: 跨域研究引擎
  M5: WeChat 连接器
  M6: 设备协同

🟢 长期 (Phase 4+):
  N1-N5: 公文/媒体/隐私/备份/SMB
```
