# 全面知识基座架构方案

> 目标: 全局知识基座 + 本体建模 + 跨项目知识共享
> 范围: Workspace 16 项目 + ~/knowledge/ + ~/Documents/ + ~/ObsidianDocument/ + ~/Shared/
> 约束: 三层分离 (定义/存取/推导)，Schema 契约化

> 注: 自 2026-06-02 起，外部 OMO 方法系统 canonical home 位于 `/Users/xiamingxing/Documents/学习进化/体系/OMO`；Workspace `.omo` 继续作为 live governance kernel / SSOT，二者通过引用和治理桥接协作，而不是互相复制。

---

## 一、核心架构

```
              ┌──────────────────────────────────┐
              │          应用层 (Consume)          │
              │  Gateway / Agora / Minerva /      │
              │  eCOS / Sophia / 未来项目          │
              └──────┬──────┬──────┬──────────────┘
                     │      │      │
              MCP 调用 │      │  CLI 调用
                     │      │      │
              ┌──────┴──────┴──────┴──────────────┐
              │       知识服务层 (Knowledge)        │
              │                                    │
              │  ┌──────────┐  ┌────────────────┐  │
              │  │  KOS     │  │  OntoDerive    │  │
              │  │  (存取)  │◄─┤  (推导)        │  │
              │  │  索引    │  │  事实推导      │  │
              │  │  检索    │  │  本体推理      │  │
              │  │  图谱    │  │  规则引擎      │  │
              │  │  推荐    │  │  形式验证      │  │
              │  └────┬─────┘  └──────┬─────────┘  │
              │       │               │            │
              └───────┼───────────────┼────────────┘
                      │               │
                ┌─────┤   JSON Schema ├─────────┐
                │     │               │         │
          ┌─────┴─────┴───────────────┴────┐    │
          │       知识定义层 (Schema)       │    │
          │                                │    │
          │   Eidos (知识类型系统)          │    │
          │   ├─ KnowledgeCard Schema      │    │
          │   ├─ OntologyNode Schema       │    │
          │   ├─ Fact Schema              │    │
          │   ├─ DerivationRule Schema    │    │
          │   ├─ ResearchFinding Schema   │    │
          │   ├─ CognitiveEvent Schema    │    │
          │   ├─ ... (可扩展)             │    │
          │   ├─ validator.py            │    │
          │   └─ registry.json           │    │
          └────────────────────────────────┘
                              │
                     ┌────────┴────────┐
                     │                 │
              ┌──────┴──────┐  ┌──────┴──────┐
              │ 知识存储     │  │ 外部数据源   │
              │             │  │            │
              │ KOS/L1 卡片  │  │ knowledge/ │
              │ KOS/L0 索引  │  │ Documents/ │
              │ ontology DB  │  │ Obsidian   │
              │ facts DB     │  │ Shared/    │
              └─────────────┘  └────────────┘
```

### 为什么叫 Eidos

希腊语 εἶδος (eidos) = **"形式 / 类型 / 本质"**——这正是 Schema 层干的：定义知识的本质结构。

---

## 二、三层职责明确划分

### 1. Eidos — 知识定义层 (新建)

**职责**: 定义所有知识的类型、结构、关系、校验规则

| 功能 | 说明 |
|------|------|
| Schema 定义 | JSON Schema 约定每个知识类型的结构 |
| 本体建模 | 概念间的层次/关系/约束 |
| 运行时校验 | `validator.py` 校验任意知识对象是否符合 Schema |
| 注册中心 | `registry.json` — 所有已知 Schema 的索引 |
| 版本管理 | Schema 版本号，避免知识格式不兼容 |
| 代码生成 | 从 Schema 生成 Python dataclass + TypeScript type |

**这不是"又一个包"**，这是整个工作区的"知识宪法"——所有项目承诺遵守的契约。

### 2. KOS — 知识存取层 (已存在, 需进化)

| 当前 (L0) | 进化后 (L0+L1) |
|-----------|---------------|
| 文档索引 + RAG | + **KnowledgeCard** 系统 |
| 15 个单文件脚本 | + 按功能组织的包结构 |
| 本地 SQLite | + Eidos Schema 校验 |
| 仅索引 ObsidianDocument | + 接入 knowledge/ + Documents/ + Shared/ |

KOS 不做推理，不做 Schema 定义——KOS 只做存取。

### 3. OntoDerive — 知识推导层 (已存在)

OntoDerive 保持现有 5 层引擎、129 tests 不变。**变动只有**: 
- 产出结果遵循 Eidos 的 Fact / DerivationRule Schema
- 能够读取 KOS 存储的卡片作为推理输入

---

## 三、跨项目适配

### 所有项目的知识适配

| 项目 | 产出什么 | 适配 Eidos Schema |
|------|---------|-------------------|
| **KOS** | 索引文档、知识卡片 | ✅ `KnowledgeCard` |
| **OntoDerive** | 事实断言、推导规则 | ✅ `Fact`, `DerivationRule` |
| **Minerva** | 研究报告、研究发现 | ✅ `ResearchFinding` |
| **Sophia** | 编译范式、范式模板 | ✅ `ParadigmSpec` |
| **eCOS** | 认知事件、涌现模式 | ✅ `CognitiveEvent` |
| **Agora** | 服务路由、Pipeline 结果 | (可选适配) |

每个项目只需两步：
1. 声明"我产出/消费什么 Schema"
2. 调用 `eidos validate()` 校验

### Gateway-schema → Eidos

之前提议的 `gateway-schema` 概念扩展为 `Eidos`，不只管 MCP 通信的类型，而是管**所有知识类型**。

---

## 四、知识接入 — 先把 46k 文件吃进来

### 知识源优先级

| 优先级 | 源 | 文件 | 方案 |
|--------|-----|------|------|
| **P0** | `~/knowledge/ingested/` | **46,075** | `kos ingest` 批量索引 |
| **P1** | `~/Documents/KOS-*.md` | 11 | 作为知识设计文档索引 |
| **P2** | `~/ObsidianDocument/` | ~1,893 | 增量索引 (已做但可改进) |
| **P3** | `~/Documents/公文/` | 5,012 | 中文文档 NER + 索引 |
| **P4** | `~/Shared/Knowledge/` | 工具配置 | 按需索引 |
| **暂不** | `~/Documents/公文模版/` | 222,381 | 模板文件，非知识内容 |

### 执行方案

```bash
kos ingest ~/knowledge/ingested/     # 46k → KOS 索引
kos ingest ~/ObsidianDocument/       # 增量更新
kos ingest ~/Documents/KOS-*.md      # 设计文档
```

`kos ingest` 内部流程：
```
文件 → Eidos Schema 分类 → KOS 索引 → KnowledgeCard
  │                           │
  │ 根据文件类型判断 Schema:   │
  │  .md → KnowledgeCard      │
  │  .json → 尝试匹配注册 Schema│
  │  .csv → TableSchema        │
  │  其他 → RawDocument        │
```

---

## 五、实施路线

### Phase 1 (3-5 天) — 基建

```
1. 创建 Eidos 项目
   ├─ schema/          JSON Schema 定义
   ├─ validator.py     运行时校验器
   ├─ registry.json    Schema 注册表
   └─ pyproject.toml   零外部依赖
   
2. KOS 进化: ingest 命令
   └─ kos ingest <path>   批量索引知识源

3. KOS + Eidos 集成
   └─ KOS 产出走 Eidos 校验
```

### Phase 2 — 互联 ✅ 已完成

```
已完成:
  4. OntoDerive Eidos 适配器
     └─ engine/ecosystem/eidos_adapter.py
     └─ FormalFact ↔ Eidos Fact
     └─ FormalEntity ↔ Eidos OntologyNode
     └─ derive --eidos 标志位

  5. Minerva Eidos 适配器
     └─ src/minerva/knowledge/eidos_adapter.py
     └─ ResearchResult → Eidos KnowledgeCard
     └─ Entity → Eidos OntologyNode
     └─ research --eidos-output 标志位

  6. Agora Eidos 服务注册
     └─ tests/test_eidos_service.py
     └─ Eidos validate 可注册为 MCP 服务

  7. 集成测试
     └─ .omo/tests/test_phase2_integration.py (5 tests)
     └─ 端到端验证: Eidos → OntoDerive → Minerva → Agora
```

### Phase 3 (长期) — 生态

```
7. 更多项目适配 (Sophia, eCOS, ...)
8. Eidos 代码生成 (Python dataclass / TS type)
9. 外部知识源接入 (API, 爬虫, ...)
10. Web Dashboard
```

---

## 六、三个关键决策

### 1. Eidos 放哪？

| 选项 | 好处 | 代价 |
|------|------|------|
| `Workspace/eidos/` | 独立干净，0 历史包袱 | 新建项目 |
| `Workspace/starlink-types/` 复活 | 复用已有目录名 | 改名麻烦，历史包袱 |
| `Workspace/kos/schema/` | 少一个项目 | KOS 被搞重了 |

**推荐: 新建 `Workspace/eidos/`** — 这是全工作区的基础设施，不应该挂靠在任何项目下。

### 2. KOS 要不要重构

| 选项 | 好处 | 代价 |
|------|------|------|
| 不重构，只加 `ingest` 命令 | 立即能用 | 代码结构不变 |
| 按 SPEC 阶段重组 | 长远可维护 | 需要时间 |

**推荐: 先不重构 KOS，只加 `ingest` 命令让知识跑起来**。代码重组可以等 L1 实现时一起做。

### 3. 现在的起点

**我的建议**: 从 Eidos 开始。
1. 先定义 3 个最核心 Schema: `KnowledgeCard`, `Fact`, `OntologyNode`
2. KOS 加 `ingest` 命令
3. KOS 产出走 Eidos 校验
4. 46k 文件先索引进来
5. 再考虑 OntoDerive 适配

这样节奏是: **Schema → 入口 → 数据 → 推理**，每一步都有价值，不会卡在中途。

---

---

## 九、技术债务跟踪

### 已清理 ✅

| 债务 | 清理方式 | 日期 |
|------|---------|------|
| OntoDerive Eidos Adapter 缺单元测试 | 新增 `tests/test_eidos_adapter.py` (7 tests) | 2026-05-21 |
| Minerva Eidos Adapter 缺单元测试 | 新增 `tests/test_eidos_adapter.py` (7 tests, 6 skip without eidos) | 2026-05-21 |

### 待清理 (LOW priority)

| 债务 | 类型 | 说明 | 建议 |
|------|------|------|------|
| KOS CLI 大量 stub 命令 | 结构 | ~80 add_parser call 含大量命名重复的命令 | 可归档到 commands/ 目录，主 CLI 只保留核心 |
| OntoDerive 非标准目录 `engine/` | 结构 | `engine/engine/formal/` 四层嵌套 | 按标准 `src/` 布局迁移 |
| Minerva eidos_adapter 6/7 skip | 覆盖 | 测试环境不含 eidos 时覆盖率不足 | 集成测试可加 PYTHONPATH 规则 |
| Eidos CLI test 覆盖率 | 覆盖 | cli.py 的 validate 和 list 测试不够完整 | 新增 test_cli_validate_edge_cases 等 |
| Agent CLI 配置硬编码路径 | 运维 | gateway/bin/*.sh 含 `/Users/xiamingxing/` 路径 | 改为相对路径或命令名模式 |

### 监控指标

| 指标 | Phase 1 | Phase 2 | 趋势 |
|------|---------|---------|------|
| 总测试数 | 50+ | 58+ | ↑ |
| 跨项目集成测试 | 3 | 8 | ↑ |
| Zero-dep 项目 (Eidos) | ✅ | ✅ | → |
| 已索引知识文件 | 46,075 | 46,075 | → |
