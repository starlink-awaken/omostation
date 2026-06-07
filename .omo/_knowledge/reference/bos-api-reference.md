# BOS URI API Reference

> 从 26 个 Workflow M1 节点自动生成 | 2026-06-07

## Agora 工具全流程编排

- **BOS URI**: 
- **Domain**: meta | **Layer**: I0
- **MCP 工具完整生命周期管理: 发现→质量评估→保存→安装→加载→健康检查→空闲超时卸载**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | DiscoverExternalSources |  |  (object) |  (object) |
| 2 | QualityAssessment |  |  (object) |  (object) |
| 3 | SaveToCatalog |  |  (object) |  (object) |
| 4 | InstallTool |  |  (object) |  (object) |
| 5 | LoadViaLifecycleManager |  |  (object) |  (object) |
| 6 | HealthMonitor |  |  (object) |  (object) |
| 7 | IdleTimeoutTrigger |  |  (object) |  (object) |
| 8 | UnloadTool |  |  (object) |  (object) |


## Agora MCP 工具编排管线

- **BOS URI**: 
- **Domain**: meta | **Layer**: I0
- **多步 MCP 工具调用编排: 顺序/流式/并行三种执行模式，支持模板变量和事件总线**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | LoadPipelineDefinition |  |  (object) |  (object) |
| 2 | ResolveToolReferences |  |  (object) |  (object) |
| 3 | ExecuteSequential |  |  (object) |  (object) |
| 4 | ReturnUnifiedOutput |  |  (object) |  (object) |


## Create 工作流

- **BOS URI**: 
- **Domain**: meta | **Layer**: L3
- **创建工作流——脚手架→编码→文档→提交**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | CREATETask |  |  (object) |  (object) |


## Debug 工作流

- **BOS URI**: 
- **Domain**: meta | **Layer**: L3
- **Agent 调试工作流——定位问题→分析根因→修复→验证**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | DEBUGTask |  |  (object) |  (object) |


## Deploy 工作流

- **BOS URI**: 
- **Domain**: meta | **Layer**: L3
- **部署工作流——构建→测试→部署→健康检查**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | DEPLOYTask |  |  (object) |  (object) |


## 每日健康巡检管线

- **BOS URI**: 
- **Domain**: meta | **Layer**: L0
- **每日自动健康巡检: 健康检查→域校验→索引同步→BOS校验→路由更新 (每日 08:00)**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | SystemHealthCheck |  |  (array) |  (boolean),  (array) |
| 2 | DomainValidateAll |  |  |  (integer),  (integer) |
| 3 | IndexSync |  |  |  (boolean) |
| 4 | BOSValidate |  |  |  (integer) |
| 5 | RoutesUpdate |  |  |  (integer) |

⚠️ **Critical Path** — SLA: 300s, 99% completion

## 全量同步管线

- **BOS URI**: 
- **Domain**: meta | **Layer**: L0
- **全量域索引同步 + BOS 路由更新**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | SyncDomainIndex |  |  (object) |  (object) |
| 2 | UpdateRoutes |  |  (object) |  (object) |


## 每周全量审计管线

- **BOS URI**: 
- **Domain**: meta | **Layer**: L0
- **每周一全量审计: KEMS校验→漂移检测→引用检查→BOS校验→路由更新→索引同步→健康检查**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | KEMSValidateAll |  |  (object) |  (int) |
| 2 | DriftDetection |  |  (object) |  (int) |
| 3 | ReferenceCheck |  |  (object) |  (int) |
| 4 | BOSValidate |  |  (object) |  (int) |
| 5 | RoutesUpdate |  |  (object) |  (int) |
| 6 | IndexSync |  |  (object) |  (bool) |
| 7 | HealthCheck |  |  (object) |  (bool) |

⚠️ **Critical Path** — SLA: 600s, 99% completion

## Eidos 多工具编排链

- **BOS URI**: 
- **Domain**: omo | **Layer**: L2
- **通过 subprocess 串联 eidos/kos/minerva/ontoderive 多工具链式调用**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | LoadSchema |  |  (object) |  (object) |
| 2 | ValidateConstraints |  |  (object) |  (object) |
| 3 | ChainTools |  |  (object) |  (object) |
| 4 | AggregateResults |  |  (object) |  (object) |
| 5 | ReturnOutput |  |  (object) |  (object) |


## Enhance 工作流

- **BOS URI**: 
- **Domain**: meta | **Layer**: L3
- **增强工作流——代码审查→重构→优化→验证**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | ENHANCETask |  |  (object) |  (object) |


## gbrain 知识同步管线

- **BOS URI**: 
- **Domain**: memory | **Layer**: L2
- **TypeScript 知识库与 Postgres 同步管线 — 67 MCP 工具支撑，从 KOS 拉取 → Schema 转换 → Upsert → 完整性校验**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | PullFromKOS |  |  (object) |  (object) |
| 2 | TransformSchema |  |  (object) |  (object) |
| 3 | UpsertPostgres |  |  (object) |  (object) |
| 4 | VerifyIntegrity |  |  (object),  (object) |  (object) |


## KOS 跨域搜索管线

- **BOS URI**: 
- **Domain**: memory | **Layer**: L2
- **跨域知识搜索管线 — 解析查询 → 全文索引 → 语义匹配 → 排序 → 返回结果**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | ParseQuery |  |  (object) |  (object) |
| 2 | FullTextIndex |  |  (object) |  (object) |
| 3 | SemanticMatch |  |  (object),  (object) |  (object) |
| 4 | RankResults |  |  (object),  (object) |  (object) |
| 5 | ReturnResults |  |  (object) |  (object) |


## Kronos 摄取管线

- **BOS URI**: 
- **Domain**: memory | **Layer**: L2
- **ETL 知识摄取管线 — 多源采集 → 内容提取 → 分类 → 分发至 Vault/WPS/KOS**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | FetchFromSources |  |  (object),  (object) |  (object) |
| 2 | ExtractContent |  |  (object) |  (object) |
| 3 | ClassifyContent |  |  (object) |  (object) |
| 4 | DispatchToTargets |  |  (object) |  (object),  (object),  (object) |

⚠️ **Critical Path** — SLA: 600s, 95% completion

## MetaOS DAG 编排管线

- **BOS URI**: 
- **Domain**: omo | **Layer**: L2
- **有向无环图并行编排 — SQLite 持久化 + 并发执行 + 指数退避重试 + HITL 干预**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | BuildDAG |  |  (object) |  (object) |
| 2 | TopologicalSort |  |  (object) |  (object) |
| 3 | ParallelExecute |  |  (object) |  (object) |
| 4 | MonitorNodes |  |  (object) |  (object) |
| 5 | CascadeResults |  |  (object),  (object) |  (object) |


## MetaOS 六步 H-M 标准协议

- **BOS URI**: 
- **Domain**: omo | **Layer**: L2
- **H-M 交互核心协议 — 权限判定 → 路由分发 → M层执行 → 免疫检测 → 结果组装 → H确认**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | DecisionGate |  |  (object) |  (string),  (boolean) |
| 2 | RouterDispatch |  |  (object) |  (object) |
| 3 | MLayerExecute |  |  (object) |  (object) |
| 4 | ImmuneMonitor |  |  (object) |  (object),  (boolean) |
| 5 | ResultAssembly |  |  (object),  (object) |  (object) |
| 6 | HConfirm |  | ['assembled_result'] | ['bos://omo/decision/result'] |

⚠️ **Critical Path** — SLA: 600s, 99% completion

## Minerva 五级深度研究管线

- **BOS URI**: 
- **Domain**: analysis | **Layer**: L2
- **L0-L4 五级分层深度研究 — 分解 → 多源搜索 → 实体提取 → 深度阅读 → 交叉分析 → 反驳论证 → 多模型投票 → 质量门 → 输出**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | Decompose |  |  (object) |  (object) |
| 2 | MultiSourceSearch |  |  (object) |  (object) |
| 3 | EntityExtraction |  |  (object) |  (object),  (object) |
| 4 | DeepRead |  |  (object),  (object) |  (object) |
| 5 | CrossAnalyze |  |  (object) |  (object) |
| 6 | CounterArgument |  |  (object) |  (object) |
| 7 | MultiModelVoting |  |  (object),  (object) |  (object) |
| 8 | QualityGate |  |  (object) |  (object) |
| 9 | Output |  |  (object) |  (object) |

⚠️ **Critical Path** — SLA: 1200s, 95% completion

## Minerva Pontus DAG 并行执行器

- **BOS URI**: 
- **Domain**: analysis | **Layer**: L2
- **基于拓扑排序的 DAG 并行管线执行器 — 支持异步/同步双模式，动态资源分配**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | BuildDAG |  |  (object) |  (object) |
| 2 | TopologicalSort |  |  (object) |  (object) |
| 3 | ParallelExecute |  |  (object) |  (object) |
| 4 | AggregateOutputs |  |  (object) |  (object) |


## Minerva VectorPipeline 向量嵌入

- **BOS URI**: 
- **Domain**: analysis | **Layer**: L2
- **高性能批量文档向量化与索引构建管线 — 加载文档 → 分块 → 生成向量 → 构建索引 → 持久化**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | LoadDocuments |  |  (object) |  (object) |
| 2 | ChunkText |  |  (object) |  (object) |
| 3 | GenerateEmbeddings |  |  (object) |  (object) |
| 4 | BuildIndex |  |  (object) |  (object) |
| 5 | PersistVectors |  |  (object) |  (object) |


## Ontoderive D-Logos 文档代码对齐

- **BOS URI**: 
- **Domain**: analysis | **Layer**: L2
- **文档-代码对齐批量管线 — Scan → Align → Validate → Evolve，支持断点续传**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | ScanCodebase |  |  (object) |  (object) |
| 2 | AlignDocsToCode |  |  (object) |  (object) |
| 3 | ValidateAlignment |  |  (object) |  (object) |
| 4 | EvolveDocs |  |  (object) |  (object) |


## Plan 工作流

- **BOS URI**: 
- **Domain**: meta | **Layer**: L3
- **规划工作流——需求分析→方案设计→任务分解→分配**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | PLANTask |  |  (object) |  (object) |


## Runtime HITL 五阶段处理管线

- **BOS URI**: 
- **Domain**: forge | **Layer**: L1
- **Human-in-the-Loop 知识处理: 意图拆解→多源检索→洞察生成→图谱更新→闭环验证**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | Phase1_DecomposeIntent |  |  (object) |  (array) |
| 2 | Phase2_MultiSourceRetrieve |  |  (array),  (array) |  (array) |
| 3 | Phase3_InsightGenerate |  |  (array) |  (array) |
| 4 | Phase4_GraphUpdate |  |  (array) |  (array) |
| 5 | Phase5_ClosedLoopVerify |  | ['graph_updates[]'] | ['bos://forge/insight'] |

⚠️ **Critical Path** — SLA: 900s, 90% completion

## Runtime KEI 沙箱执行管线

- **BOS URI**: 
- **Domain**: forge | **Layer**: L1
- **受控沙箱执行: 环境准备→代码执行→结果收集→安全审计**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | PrepareEnvironment |  |  (object) |  (object) |
| 2 | ExecuteInSandbox |  |  (object) |  (object) |
| 3 | CollectResults |  |  (object) |  (object) |
| 4 | AuditSecurity |  |  (object) |  (object) |
| 5 | CleanupAndReturn |  |  (object),  (object) |  (object) |


## Runtime 场景管线

- **BOS URI**: 
- **Domain**: forge | **Layer**: L1
- **6 预定义知识处理场景: standard/quick-analysis/full-review/learning-cycle/knowledge-refresh/deep-analysis**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | SelectScenario |  |  (object) |  (object) |
| 2 | LoadSteps |  |  (object) |  (object) |
| 3 | ExecuteStep |  |  (object) |  (object) |
| 4 | CollectOutput |  |  (object) |  (object) |
| 5 | ReturnResult |  |  (object) |  (object) |


## SharedBrain 桥接管线

- **BOS URI**: 
- **Domain**: persona | **Layer**: L2
- **SharedBrain 知识图谱 ↔ KOS 语义网双向桥接同步，保证知识一致性**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | ReadSharedBrainGraph |  |  (object) |  (object),  (object) |
| 2 | ExtractKnowledgeNodes |  |  (object),  (object) |  (object) |
| 3 | MapToKOSOntology |  |  (object) |  (object) |
| 4 | SyncBidirectional |  |  (object) |  (object) |
| 5 | AuditConsistency |  |  (object),  (object) |  (object) |


## SSOT 桥接同步管线

- **BOS URI**: 
- **Domain**: memory | **Layer**: L2
- **单一事实源桥接 — SharedBrain ↔ KOS ↔ Vault 双向同步，保证数据一致性**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | ReadSharedBrain |  |  (object) |  (object),  (object) |
| 2 | ExtractEntities |  |  (object),  (object) |  (object) |
| 3 | MapToKOS |  |  (object) |  (object) |
| 4 | SyncVault |  |  (object) |  (object) |
| 5 | ValidateConsistency |  |  (object),  (object),  (object) |  (object) |


## Test 工作流

- **BOS URI**: 
- **Domain**: meta | **Layer**: L3
- **测试工作流——单元测试→集成测试→E2E→报告**

### Steps

| # | Step | Action | Input | Output |
|---|------|--------|-------|--------|
| 1 | TESTTask |  |  (object) |  (object) |

