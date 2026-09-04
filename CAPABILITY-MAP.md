---
type: ssot
owner: governance-team
last_updated: 2026-09-03
---

# Cockpit 能力地图

> 自动生成于 1970-01-01T00:00:00Z | 版本 1.0.0
> 源: `docs/generated/capability-registry.yaml` | 请勿手动编辑
> 生成器: `bin/ssot/gen-help-docs.py`

## 概览

| 通道 | 数量 |
|------|------|
| CLI 命令 (含子命令) | 199 |
| MCP 工具 | 584 |
| MCP 服务器 | 27 |
| BOS 服务 | 289 |
| BOS 域 | 21 |

## MCP 服务器清单

| 服务器 | 层 | 工具数 | 传输 | 文件 |
|--------|-----|--------|------|------|
| `agora` | I0 | 104 | stdio/sse | `projects/agora/src/agora/server/mcp.py` |
| `gbrain` | L2 | 75 | stdio | `projects/knowledge/gbrain/src/core/operations/exports.ts` |
| `l4-kernel` | L4 | 47 | stdio/http/sse | `projects/l4-kernel/src/l4_kernel/mcp_server.py` |
| `kos` | L2 | 44 | stdio | `projects/knowledge/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `kos-stdio` | L2 | 44 | stdio | `projects/knowledge/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `ecos` | L0 | 28 | stdio | `projects/ecos/src/ecos/mcp_server.py` |
| `model-driven` | M0 | 28 | stdio | `projects/model-driven/src/model_driven/mcp_server.py` |
| `ecos-integration` | L0 | 26 | stdio | `projects/ecos/src/ecos/services/integration/mcp_server.py` |
| `codeanalyze` | L2 | 25 | stdio | `projects/knowledge/kairon/packages/codeanalyze/src/codeanalyze/mcp.py` |
| `metaos` | L2 | 24 | stdio | `projects/metaos/src/metaos/mcp_server.py` |
| `omo` | L2 | 22 | stdio | `projects/omo/src/omo/mcp_server.py` |
| `kronos` | L2 | 16 | stdio | `projects/knowledge/kairon/packages/kronos/src/kronos/mcp_server.py` |
| `aetherforge` | X | 15 | stdio | `projects/aetherforge/src/aetherforge/mcp_server.py` |
| `agent-runtime` | L3 | 14 | stdio | `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py` |
| `ecos-ssot` | L0 | 9 | stdio | `projects/ecos/src/ecos/l0/ssot/mcp_server.py` |
| `iris` | L2 | 8 | stdio | `projects/knowledge/kairon/packages/iris/src/iris/mcp_server.py` |
| `sophia` | L2 | 8 | stdio | `projects/knowledge/kairon/packages/sophia/src/sophia/server/mcp_server.py` |
| `minerva` | L2 | 8 | stdio | `projects/knowledge/kairon/packages/minerva/src/minerva/mcp_server/server.py` |
| `forge` | L2 | 7 | stdio | `projects/knowledge/kairon/packages/forge/src/mcp_server.py` |
| `ontoderive` | L2 | 7 | stdio | `projects/knowledge/kairon/packages/ontoderive/src/ontoderive/mcp_server.py` |
| `aetherforge-mesh` | X | 6 | stdio | `projects/aetherforge/packages/mesh/src/compute_mesh/api/mcp_server.py` |
| `family-hub` | X | 6 | stdio | `projects/family-hub/mcp_server.py` |
| `toolforge` | L2 | 5 | stdio | `projects/knowledge/kairon/packages/ontoderive/src/ontoderive/toolforge/mcp_server.py` |
| `aetherforge-gateway` | X | 3 | stdio | `projects/aetherforge/packages/gateway/src/llm_gateway/mcp_server.py` |
| `c2g` | X | 3 | stdio | `projects/omo/src/omo/_vendored/c2g/mcp_server.py` |
| `model-driven-fastmcp` | M0 | 2 | stdio | `projects/model-driven/src/model_driven/fastmcp_server.py` |
| `runtime` | L1 | 0 | stdio | `projects/runtime/src/runtime/mcp_server.py` ⚠️未找到 |

## BOS 服务域分布

| 域 | 服务数 |
|-----|--------|
| `agent-cell` | 23 |
| `agora` | 3 |
| `analysis` | 28 |
| `bcos` | 3 |
| `capability` | 44 |
| `cockpit` | 7 |
| `compute` | 17 |
| `ecos` | 10 |
| `fabric` | 1 |
| `forge` | 1 |
| `governance` | 70 |
| `l4-kernel` | 1 |
| `memory` | 47 |
| `meta` | 1 |
| `omo` | 4 |
| `perception` | 2 |
| `persona` | 10 |
| `resident` | 4 |
| `runtime` | 1 |
| `swarm` | 1 |
| `system` | 11 |

## CLI 命令清单

> 完整命令参考见 [`CLI-REFERENCE.md`](CLI-REFERENCE.md)

| 命令 | 描述 |
|------|------|
| `cockpit ack` | 确认任务完成 |
| `cockpit add` | 手动添加决策项 |
| `cockpit agent` | 🤖 Agent 治理控制入口 (bootstrap / status / start / claim / verify / closeout) |
| `cockpit agent-onboard` | 🤖 Agent 入职引导 checklist (profile + MCP + BOS + skills) |
| `cockpit agent-runtime` | 🤖 Agent Runtime 任务执行 / HTTP server (替代独立 agent-runtime 命令) |
| `cockpit agent-workflow` | 🤖 Agent 可执行治理流程 (委派 root bin/agent-workflow.py) |
| `cockpit agora` | Agora BOS 网关入口 (委派 agora CLI) |
| `cockpit analyze` | 运行全部分析工具 |
| `cockpit api` | 启动 API server |
| `cockpit approve` | 批准决策 |
| `cockpit archive` | 归档研究记录 |
| `cockpit ask` | 对指定研究发起追问 |
| `cockpit audit` | 扫描可疑研究记录 |
| `cockpit audit-ledger` |  |
| `cockpit backends` | 列出 BOS 后端 |
| `cockpit backup` | 全量备份研究数据到 JSON 文件 |
| `cockpit backup-restore` | 从备份 JSON 文件恢复研究数据 |
| `cockpit batch` | 批量研究模式: 逐个处理多个 topic，汇总结果 |
| `cockpit bcos` | BCOS 业务域系统 (evolve/signals/north-star) |
| `cockpit bdsk` | 🧠 B.D.S.K. 虚拟董事会 (4角对抗辩论与 0-Touch 影子预演) |
| `cockpit bos` | BOS URI 查询与管理 |
| `cockpit bos-capability` | BOS capability / toolbox 外部能力 |
| `cockpit bos-inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit brain` | 个人数字大脑 — 知识检索 + 记忆 + 智能问答 |
| `cockpit brief` | 会话简报 / 每日早报 (--morning) |
| `cockpit bus` | Omni-Bus 三平面入口 |
| `cockpit c2g` | 🎯 C2G 战略罗盘 (status/pipeline) |
| `cockpit cache` | 检查三级分层缓存与 Radix 前缀树状态 (含基准压测) |
| `cockpit capabilities` | 统一能力发现入口 — 搜索/推荐/全量列出 (CLI+BOS+Scene+Journey+Governance) |
| `cockpit capability` | BOS capability 域 / toolbox 外部能力 |
| `cockpit cards` | 显示 CARDS 卡片状态 |
| `cockpit cartridge` | 👁️ 长尾领域治理卡带工坊 (ADR-0198/0203) |
| `cockpit cell` | 🤖 AGE-v2 动态 Agent Cell (规划/执行/验证/治理) |
| `cockpit challenge` | ⚡️ 影子红蓝对抗审查与合规自动打补丁 (ADR-0196) |
| `cockpit channels` | 🌐 External channels inventory (ECCP) — 生成/查看 external-channels.yaml |
| `cockpit client` | 以 REPL 模式连接到 MCP server |
| `cockpit cluster` | 异构三节点智能路由与拓扑诊断 |
| `cockpit code` | 代码库分析与审查 (基于 codeanalyze) |
| `cockpit compact` | 上下文滑动蒸馏与双区自适应量化压缩模拟 |
| `cockpit compare` | 对比多个研究结果 |
| `cockpit compass` | 🧭 C2G 战略罗盘 (V2P -> C2G -> AGC 统一管理) |
| `cockpit compute` | 算力与 LLM 网关操作 (委派 aetherforge) |
| `cockpit consolidate` | sleep-time 巩固 (默认 dry-run) |
| `cockpit context` | 显示系统上下文 (Phase/CARDS/约束/引导) |
| `cockpit contracts` | 契约验证 |
| `cockpit control` | 控制平面：submit / ack / nack |
| `cockpit controller-shadow` | 读取 Runtime 旧控制器影子迁移回执 |
| `cockpit create` | 创建新研究 |
| `cockpit daily` | 每日研究简报 |
| `cockpit dashboard` | 打开 Web Dashboard |
| `cockpit data` | 数据目录索引 / 类型注册 / TTL 清理 |
| `cockpit debt` | 债务评分 (omo-debt Pattern 09 v2.1) |
| `cockpit decide` | 📬 决策收件箱 (列出/添加/批准/拒绝) |
| `cockpit demo` | 快速演示 |
| `cockpit dflash` | DFlash 2 块扩散投机解码加速与集群基准 |
| `cockpit diff` | 查看待处理署名 Diff 统计 |
| `cockpit digest` | 提炼多个研究结果 |
| `cockpit discover` | 发现可用功能和资源 |
| `cockpit distill` | 在 Mac mini M4 触发闲时 LoRA 蒸馏 |
| `cockpit dma` | 测试雷雳 5 跨机零拷贝 DMA 通道与换页基准 |
| `cockpit docx` | 渲染为 GB/T 9704-2012 红头公文 DOCX |
| `cockpit domain-status` | 显示 Documents 域项目绑定与引导状态 |
| `cockpit domains` | 列出 L4 所有域及其状态 |
| `cockpit dossier` | 查看研究的关系与产物视图 |
| `cockpit down` | 停止观测栈 |
| `cockpit draft` | 从本地主权大模型请求草稿 |
| `cockpit event` | 导出事件封套 (EventEnvelope) |
| `cockpit events` | 实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard) |
| `cockpit events-watch` | 实时监听 SSE 事件流简便入口 |
| `cockpit export` | 导出研究 (markdown/text/json) |
| `cockpit export-research` | 将研究对象导出为 WorkspaceObject JSON |
| `cockpit fabric` | 检查 omlxc 智能算力织网 (温控/分诊/显存/缓存) |
| `cockpit fabric-mesh` |  |
| `cockpit facts-audit` | 审计 Documents 文档域 facts 文件 |
| `cockpit facts-validation` | 读取 Runtime Facts 审计回执 |
| `cockpit family-hub` | 家庭数字枢纽入口 |
| `cockpit finance` | 💰 个人财务门户引导 (场景/原则/入口, 委派 @个人 域) |
| `cockpit follow-up` | 查看追问工作台（待追问/已回答统计） |
| `cockpit forget` | 遗忘传播 |
| `cockpit gac` | GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift) |
| `cockpit gbrain` | Postgres-native 知识库入口 (委派 gbrain CLI) |
| `cockpit gc` | 清理 data/tmp 过期文件 |
| `cockpit get` | 查 1 个 card |
| `cockpit gongwen` | 📄 公文写作门户引导 (文种/规范/入口, 委派 @公文 域) |
| `cockpit governance` | 架构治理 (委派 arcnode-*) |
| `cockpit graph` | 运行语义图谱分析 |
| `cockpit health` | 查看研究健康报告（衰减状态/保鲜建议） |
| `cockpit heatmap` | 显示研究活跃度热力图 |
| `cockpit help` | 查看产品地图与快速入门 (cockpit help <关键词> 模糊搜命令/工具/服务) |
| `cockpit history` | 查看对话历史 |
| `cockpit hud` | 查看次世代主权算力织网全景 HUD 实时状态 |
| `cockpit identity` | 导出身份封套 (IdentityEnvelope) |
| `cockpit impact` | 分析符号的变更影响面 |
| `cockpit import` | 导入外部内容 |
| `cockpit inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit index` | 刷新 data/_index 元数据 |
| `cockpit ingress` | 感知源接入 Spine 管线 (T2-03: OCR 扫描件) |
| `cockpit init` | 🚀 初始化向导（同 quickstart） |
| `cockpit inspect` | 查看算力网格健康度与节点状态 |
| `cockpit intent` | 🧠 自然语言意图解构与工程规格编译器 (ADR-0195) |
| `cockpit invoke` | 通过治理网关调用 exact native BOS capability |
| `cockpit iterate` | ♻️ C2G 双擎迭代流 (MetaOS 发散 -> Model-Driven 桥接 -> OMO 门控执行) |
| `cockpit journey` | 🗺️ Journey State Graph 状态表达校验器 |
| `cockpit kairon` | kairon 知识引擎 monorepo 聚合入口 |
| `cockpit kems` | 🧬 KEMS 域治理 (domains/status/scan) |
| `cockpit knowledge` | 📚 KOS 知识检索 (search/status/stats) |
| `cockpit knowledge-ref` | ADR-0315 引用元数据 (无正文) |
| `cockpit list` | 查看研究历史 |
| `cockpit logs` | 查看日志 |
| `cockpit lora` | 查看与测试端侧在线 LoRA 适配层热插拔 |
| `cockpit mcp` | 启动 MCP server 或列出工具 |
| `cockpit memory` | 🧠 Memory OS (status/recall/write/forget/consolidate/knowledge-ref) |
| `cockpit memory-distill` |  |
| `cockpit merge` | 合并多个研究结果为新研究 |
| `cockpit mesh` | omlx 算力网格路由入口 |
| `cockpit metrics` | 查看 bus metrics 快照 |
| `cockpit model-driven` |  |
| `cockpit model-freshness` | 读取 Runtime 模型新鲜度回执 |
| `cockpit mof` | MOF 元模型操作 (委派 mof CLI) |
| `cockpit monitor` | 📊 实时终端大盘 (C2G Pipeline 监控仪, 实时刷新 Ctrl+C 退出) |
| `cockpit mutate` | 通过 agora 统一 BOS URI 写协议修改资源 |
| `cockpit nack` | 否定确认任务 |
| `cockpit nodes` | 列出 KOS 中注册的算力节点 |
| `cockpit observe` | 可观测性栈（Langfuse）入口 |
| `cockpit omo` | OMO CLI 委派 (debt/state/governance/lint/...) |
| `cockpit onboarding` | 为 AI 构建项目全貌上下文 |
| `cockpit open` | 打开研究全文 |
| `cockpit ops` | 🔧 Service Gateway — 统一运维控制面 (status/up/down/deploy/deps/logs/discover/validate/generate) |
| `cockpit pack` | 将代码库打包为 LLM 友好格式 |
| `cockpit panorama` | 🌐 7 维全景终极可观测仪表盘 (执行过程/服务/内容/知识/数据/异常/债务资产) |
| `cockpit pending` | 查看未决待办快照预览 |
| `cockpit pipeline` | pipeline 概览 |
| `cockpit policy` | ⚖️ 领域监管合规与 Policy-as-Code 红线审查 (E-POL-*) |
| `cockpit pptx` | 渲染为 16:9 高管技术汇报 PPTX |
| `cockpit product-health` | 产品健康度检测 |
| `cockpit profile` | 查看/编辑身份档案 (L4 入口) |
| `cockpit project` | 🔍 17 项目全景 4D 体检与诊断 |
| `cockpit proxy-env` | 输出兼容外部客户端的本地环境变量 (OPENAI_API_BASE) |
| `cockpit publish` | 发布研究为正式 Markdown 报告 |
| `cockpit quarantine` | 隔离可疑研究记录 |
| `cockpit quickstart` | 🚀 新用户快速上手向导（环境核验 + 上手指引） |
| `cockpit quickstart-check` | 快速检查新用户环境核验状态 |
| `cockpit read` | 通过 BOS 网关统一读取指定 URI 资源 |
| `cockpit readiness` | P66: governance readiness dashboard 摘要 (4 卡片: summary/dimensions/alerts/history) |
| `cockpit recall` | 意图路由召回（neo4j/temporal 支持 --as-of） |
| `cockpit register` | 注册 BOS 服务 |
| `cockpit reject` | 拒绝决策 |
| `cockpit reload` | 重载 BOS 配置/M1 |
| `cockpit remember` | 手动存入偏好/事实 |
| `cockpit rename` | 重命名研究标题 |
| `cockpit render` | 初稿 Markdown 一键渲染导出 (GB/T 9704 DOCX / 16:9 PPTX / 矢量图) |
| `cockpit replay` | 查看 Experience Replay 缓冲区状态 |
| `cockpit research` | 深度研究 — 创建/查询/管理研究对象 |
| `cockpit resident` | Resident 常驻 Agent 体系 (status/roles/daemon/decision/execute/...) |
| `cockpit resolve` | 统一 BOS URI 路由解析与目标元数据提取 |
| `cockpit restore` | 恢复已隔离研究记录 |
| `cockpit route` | 为模型选择最优节点 |
| `cockpit run` | 在隔离沙箱中挂载卡带并执行领域意图 |
| `cockpit runtime` | runtime CLI 委派 (Matrix/Scheduler/KEI 沙箱) |
| `cockpit sanyi-status` | 读取 Runtime 三医状态一致性回执 |
| `cockpit scan` | 平面扫描 |
| `cockpit scenario` | P5 统一 scenario 入口 (radar/assistant/health/inbox/intake/task/approval/connector/review) |
| `cockpit score` | 评分债务项 |
| `cockpit search` | 全文搜索 |
| `cockpit serve` | stdio JSON-RPC serve mode |
| `cockpit sign` | 提交用户署名 Diff 并入队 Experience Replay |
| `cockpit skill` | 运行 L4 定时技能 |
| `cockpit snapshot` | KV 缓存快照管理与预热 |
| `cockpit speculative-eval` | 本地首选投机推演评估 |
| `cockpit spine` | Spine 主干真值流与署名自进化操作 (ADR-0437) |
| `cockpit ssb` |  |
| `cockpit stats` | 索引统计 |
| `cockpit status` | 系统健康 |
| `cockpit stream` | 跨节点 Chunk-level 流式协同流水线基准 |
| `cockpit submit` | 提交控制任务 |
| `cockpit summary` | 债务摘要 (委派 omo debt) |
| `cockpit svg` | 渲染 ```diagram 代码块为矢量架构图 SVG |
| `cockpit swarm` | 分布式跨节点 KV 共享池与超长上下文置换基准 |
| `cockpit tag` | 为研究添加/覆盖标签 |
| `cockpit test_export_formats` | 离线自测: 三格式导出 + GB/T 参数断言 |
| `cockpit timeline` | 查看研究的演化时间线 |
| `cockpit topics` | 列出已注册 topic |
| `cockpit tree` | 自适应熵感知树状投机解码与多候选验证基准 |
| `cockpit triage` | 分析 Prompt 意图复杂度分级 |
| `cockpit tui` | 极客终端交互控制台 (Textual 全屏 TUI) |
| `cockpit types` | 查看已注册的数据类型 |
| `cockpit unarchive` | 恢复已归档研究记录 |
| `cockpit up` | 启动观测栈 |
| `cockpit url` | 打印 Langfuse Web URL |
| `cockpit validate` | 验证 Workspace 契约 |
| `cockpit vault` | 搜索 L4 Vault 知识库 |
| `cockpit version` | 版本信息 |
| `cockpit vram` | 计算模型动态 KV Cache 显存预算 |
| `cockpit warm` | 预热系统 Prompt 前缀缓存以实现 0ms TTFT |
| `cockpit watch` | 监听 BOS Inbox 紧急待办与提醒快照 (Event-Driven Watcher) |
| `cockpit watchdog` | 🐕 自治守护犬与自愈探针 (Agora Bus / Resident 监视器) |
| `cockpit wave2` | 📈 Wave2 预测治理面板 (dashboard/proposals/predictive JSON) |
| `cockpit workflow` | BOS workflow 相关 |
| `cockpit write` | 双轨写入 (+ Neo4j FACT 若配置) |

---
*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*