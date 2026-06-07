# BOS URI API Reference

> 26 工作流 · 146 步骤 · 自动生成

## Agora 工具全流程编排
**bos://ecos/workflow/agora-orchestrator** · meta/I0 · MCPWorkflow

- 1. **DiscoverExternalSources** → 
  扫描并发现可用的外部 MCP 工具服务
- 2. **QualityAssessment** → 
  对发现的工具进行质量评估和评分
- 3. **SaveToCatalog** → 
  将通过评估的工具信息保存到工具目录
- 4. **InstallTool** → 
  安装工具所需依赖和配置
- 5. **LoadViaLifecycleManager** → 
  通过生命周期管理器加载工具至内存，引用计数 +1
- 6. **HealthMonitor** → 
  对已加载工具执行持续健康监控
- 7. **IdleTimeoutTrigger** → 
  空闲超时检测 — 引用计数归零后触发卸载流程
- 8. **UnloadTool** → 
  安全卸载空闲工具，释放资源

## Agora MCP 工具编排管线
**bos://ecos/workflow/agora-pipeline** · meta/I0 · MCPWorkflow

- 1. **LoadPipelineDefinition** → 
  加载管线定义，解析工具链配置和模板变量
- 2. **ResolveToolReferences** → 
  解析工具引用，定位实际可用的 MCP 工具实例
- 3. **ExecuteSequential** → 
  顺序执行模式 — 按定义顺序逐个调用工具
- 4. **ReturnUnifiedOutput** → 
  组装并返回统一的管线执行结果

## Create 工作流
**bos://ecos/workflow/create** · meta/L3 · AgentWorkflow

- 1. **CREATETask** → 
  创建工作流——脚手架→编码→文档→提交

## Debug 工作流
**bos://ecos/workflow/debug** · meta/L3 · AgentWorkflow

- 1. **DEBUGTask** → 
  Agent 调试工作流——定位问题→分析根因→修复→验证

## Deploy 工作流
**bos://ecos/workflow/deploy** · meta/L3 · AgentWorkflow

- 1. **DEPLOYTask** → 
  部署工作流——构建→测试→部署→健康检查

## 每日健康巡检管线
**bos://ecos/workflow/daily-health** · meta/L0 · ScheduledWorkflow

- 1. **SystemHealthCheck** → 
  检查所有核心服务和节点的健康状态
- 2. **DomainValidateAll** → 
  全量校验各域索引和路由的有效性
- 3. **IndexSync** → 
  同步域索引，确保注册信息最新
- 4. **BOSValidate** → 
  校验所有 BOS URI 引用的有效性
- 5. **RoutesUpdate** → 
  更新 Agora Mesh 路由表
> ⚠️ Critical · 300s

## 全量同步管线
**bos://ecos/workflow/sync-all** · meta/L0 · ScheduledWorkflow

- 1. **SyncDomainIndex** → 
  全量同步所有域的索引信息
- 2. **UpdateRoutes** → 
  更新 BOS 路由表，确保所有 URI 解析正确

## 每周全量审计管线
**bos://ecos/workflow/weekly-audit** · meta/L0 · ScheduledWorkflow

- 1. **KEMSValidateAll** → 
  全量 KEMS 校验所有域的完整性和正确性
- 2. **DriftDetection** → 
  检测配置漂移 — 比较期望状态与实际状态
- 3. **ReferenceCheck** → 
  检查所有跨域引用和链接的有效性
- 4. **BOSValidate** → 
  校验所有 BOS URI 引用和命名空间一致性
- 5. **RoutesUpdate** → 
  根据审计结果更新 Agora Mesh 路由表
- 6. **IndexSync** → 
  同步所有域索引至最新状态
- 7. **HealthCheck** → 
  审计后健康检查，确保所有服务正常
> ⚠️ Critical · 600s

## Eidos 多工具编排链
**bos://ecos/workflow/eidos-pipeline** · omo/L2 · PipelineWorkflow

- 1. **LoadSchema** → 
  加载 Schema 定义和约束规则
- 2. **ValidateConstraints** → 
  基于加载的 Schema 校验数据约束
- 3. **ChainTools** → 
  链式调用 kos/minerva/ontoderive 等下游工具处理
- 4. **AggregateResults** → 
  聚合所有工具链的输出结果
- 5. **ReturnOutput** → 
  返回最终校验和编排结果

## Enhance 工作流
**bos://ecos/workflow/enhance** · meta/L3 · AgentWorkflow

- 1. **ENHANCETask** → 
  增强工作流——代码审查→重构→优化→验证

## gbrain 知识同步管线
**bos://ecos/workflow/gbrain-knowledge-sync** · memory/L2 · PipelineWorkflow

- 1. **PullFromKOS** → 
  从 KOS 本体拉取最新知识条目和更新差异
- 2. **TransformSchema** → 
  将 KOS 本体 Schema 映射转换为 Postgres 关系模型
- 3. **UpsertPostgres** → 
  增量 Upsert 至 Postgres 表，处理冲突与去重
- 4. **VerifyIntegrity** → 
  校验 Postgres 数据与 KOS 源的一致性

## KOS 跨域搜索管线
**bos://ecos/workflow/kos-cross-search** · memory/L2 · PipelineWorkflow

- 1. **ParseQuery** → 
  解析搜索查询，提取关键词、意图和过滤条件
- 2. **FullTextIndex** → 
  基于解析结果执行全文索引检索
- 3. **SemanticMatch** → 
  基于向量嵌入进行语义相似度匹配
- 4. **RankResults** → 
  融合全文匹配和语义匹配结果，多因子排序
- 5. **ReturnResults** → 
  组装最终搜索结果并返回

## Kronos 摄取管线
**bos://ecos/workflow/kronos-ingest** · memory/L2 · PipelineWorkflow

- 1. **FetchFromSources** → 
  从 RSS、公众号等配置源采集原始内容
- 2. **ExtractContent** → 
  提取正文、元数据、标签等结构化内容
- 3. **ClassifyContent** → 
  按主题、领域分类内容以确定分发目标
- 4. **DispatchToTargets** → 
  将分类后的内容分发到 Vault/Obsidian、WPS 和 KOS 本体
> ⚠️ Critical · 600s

## MetaOS DAG 编排管线
**bos://ecos/workflow/metaos-dag-orchestrate** · omo/L2 · PipelineWorkflow

- 1. **BuildDAG** → 
  解析任务定义，构建有向无环图依赖关系
- 2. **TopologicalSort** → 
  对 DAG 进行拓扑排序，确定并行执行顺序
- 3. **ParallelExecute** → 
  按拓扑层级并发执行节点任务，支持指数退避重试
- 4. **MonitorNodes** → 
  实时监控各节点执行状态，异常节点触发 HITL 干预
- 5. **CascadeResults** → 
  级联汇总所有节点结果，输出最终完成状态

## MetaOS 六步 H-M 标准协议
**bos://ecos/workflow/metaos-h-m-protocol** · omo/L2 · PipelineWorkflow

- 1. **DecisionGate** → 
  决策权限判定 — 校验请求来源和权限范围
- 2. **RouterDispatch** → 
  将授权请求路由分发到对应的认知框架和执行器
- 3. **MLayerExecute** → 
  M 层实际执行决策逻辑
- 4. **ImmuneMonitor** → 
  免疫系统实时监测执行过程，检测异常和违规
- 5. **ResultAssembly** → 
  组装执行结果和免疫审查结论
- 6. **HConfirm** → 
  H 层最终确认或驳回决策结果
> ⚠️ Critical · 600s

## Minerva 五级深度研究管线
**bos://ecos/workflow/minerva-deep-research** · analysis/L2 · PipelineWorkflow

- 1. **Decompose** → 
  将研究课题分解为多个子问题
- 2. **MultiSourceSearch** → 
  从多个数据源并行搜索相关信息
- 3. **EntityExtraction** → 
  从搜索结果中提取命名实体和关键概念
- 4. **DeepRead** → 
  对关键文档进行深度阅读和要点提取
- 5. **CrossAnalyze** → 
  跨文档交叉分析，发现关联和矛盾
- 6. **CounterArgument** → 
  生成反驳论证，检验结论健壮性
- 7. **MultiModelVoting** → 
  多 LLM 模型投票表决，提高结论可靠性
- 8. **QualityGate** → 
  质量门校验 — 评估置信度、完整性、一致性
- 9. **Output** → 
  输出最终研究报告和结论
> ⚠️ Critical · 1200s

## Minerva Pontus DAG 并行执行器
**bos://ecos/workflow/minerva-pontus-dag** · analysis/L2 · PipelineWorkflow

- 1. **BuildDAG** → 
  构建研究任务的有向无环图依赖关系
- 2. **TopologicalSort** → 
  拓扑排序确定并行执行批次
- 3. **ParallelExecute** → 
  按拓扑层级并发执行节点，支持异步/同步双模式
- 4. **AggregateOutputs** → 
  聚合所有并行节点的执行输出

## Minerva VectorPipeline 向量嵌入
**bos://ecos/workflow/minerva-vector** · analysis/L2 · PipelineWorkflow

- 1. **LoadDocuments** → 
  从 KOS 加载待向量化的文档
- 2. **ChunkText** → 
  将长文档分块为适合嵌入的片段
- 3. **GenerateEmbeddings** → 
  批量生成文档块的向量嵌入表示
- 4. **BuildIndex** → 
  基于向量嵌入构建高效的相似度搜索索引
- 5. **PersistVectors** → 
  将向量索引持久化存储

## Ontoderive D-Logos 文档代码对齐
**bos://ecos/workflow/ontoderive-dlogos** · analysis/L2 · PipelineWorkflow

- 1. **ScanCodebase** → 
  扫描代码库变更，检测需要更新的文档映射
- 2. **AlignDocsToCode** → 
  将现有文档与代码结构进行对齐分析
- 3. **ValidateAlignment** → 
  校验文档与代码对齐的一致性和完整性
- 4. **EvolveDocs** → 
  基于对齐结果自动演化更新文档

## Plan 工作流
**bos://ecos/workflow/plan** · meta/L3 · AgentWorkflow

- 1. **PLANTask** → 
  规划工作流——需求分析→方案设计→任务分解→分配

## Runtime HITL 五阶段处理管线
**bos://ecos/workflow/runtime-hitl** · forge/L1 · PipelineWorkflow

- 1. **Phase1_DecomposeIntent** → 
  第一阶段 — 意图拆解，将复杂任务分解为子任务
- 2. **Phase2_MultiSourceRetrieve** → 
  第二阶段 — 多源检索，从 KOS、gbrain、Vault 等多源获取相关知识
- 3. **Phase3_InsightGenerate** → 
  第三阶段 — 洞察生成，基于检索结果生成分析洞察
- 4. **Phase4_GraphUpdate** → 
  第四阶段 — 图谱更新，将新洞察写入知识图谱
- 5. **Phase5_ClosedLoopVerify** → 
  第五阶段 — 闭环验证，HITL 审查确认结果有效性
> ⚠️ Critical · 900s

## Runtime KEI 沙箱执行管线
**bos://ecos/workflow/runtime-kei** · forge/L1 · PipelineWorkflow

- 1. **PrepareEnvironment** → 
  准备隔离沙箱环境，配置依赖和运行时
- 2. **ExecuteInSandbox** → 
  在沙箱中执行代码，捕获标准输出和错误
- 3. **CollectResults** → 
  收集执行结果，包括输出、返回值、状态码
- 4. **AuditSecurity** → 
  安全审计 — 检查执行过程中的异常和潜在风险
- 5. **CleanupAndReturn** → 
  清理沙箱环境并返回执行结果和安全审计报告

## Runtime 场景管线
**bos://ecos/workflow/runtime-scenario** · forge/L1 · PipelineWorkflow

- 1. **SelectScenario** → 
  根据请求参数选择匹配的预定义场景模板
- 2. **LoadSteps** → 
  加载场景配置，展开为可执行的步骤序列
- 3. **ExecuteStep** → 
  逐步骤执行场景中的操作，记录执行状态
- 4. **CollectOutput** → 
  收集所有步骤的执行结果
- 5. **ReturnResult** → 
  组装并返回最终场景执行输出

## SharedBrain 桥接管线
**bos://ecos/workflow/sharedbrain-bridge** · persona/L2 · PipelineWorkflow

- 1. **ReadSharedBrainGraph** → 
  读取 SharedBrain 知识图谱中的节点和边数据
- 2. **ExtractKnowledgeNodes** → 
  从图谱中提取可迁移的知识节点
- 3. **MapToKOSOntology** → 
  将知识节点映射到 KOS 语义网本体结构
- 4. **SyncBidirectional** → 
  双向同步 — KOS 变更回写 SharedBrain，SharedBrain 新数据写入 KOS
- 5. **AuditConsistency** → 
  审计 SharedBrain 与 KOS 的知识一致性

## SSOT 桥接同步管线
**bos://ecos/workflow/sot-bridge-sync** · memory/L2 · PipelineWorkflow

- 1. **ReadSharedBrain** → 
  读取 SharedBrain 图谱中的实体和关系数据
- 2. **ExtractEntities** → 
  从 SharedBrain 数据中提取知识实体并结构化
- 3. **MapToKOS** → 
  将实体映射到 KOS 本体概念体系
- 4. **SyncVault** → 
  同步至 Vault/Obsidian 本地知识库
- 5. **ValidateConsistency** → 
  三方校验 SharedBrain ↔ KOS ↔ Vault 数据一致性

## Test 工作流
**bos://ecos/workflow/test** · meta/L3 · AgentWorkflow

- 1. **TESTTask** → 
  测试工作流——单元测试→集成测试→E2E→报告
