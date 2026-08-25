---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-24
---

# Cockpit CLI 命令参考

> 自动生成于 1970-01-01T00:00:00Z
> 源: `docs/generated/capability-registry.yaml`

共 **152** 个命令 (含子命令)。按场景分组如下。

## 治理与门禁

| 命令 | 描述 |
|------|------|
| `cockpit audit` | 🔍 6 维度全方位审计 (调 bin/workspace-audit) |
| `cockpit audit-ledger` | 密码学级 Merkle 审计账本 (ADR-0201) |
| `cockpit cards` | 显示 CARDS 卡片状态 |
| `cockpit contracts` | 契约验证 |
| `cockpit debt` | 债务评分 (omo-debt Pattern 09 v2.1) |
| `cockpit domain-status` | 显示 Documents 域项目绑定与引导状态 |
| `cockpit domains` | 列出 L4 所有域及其状态 |
| `cockpit facts-audit` | 审计 Documents 文档域 facts 文件 |
| `cockpit facts-validation` | 读取 Runtime Facts 审计回执 |
| `cockpit gac` | GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift) |
| `cockpit governance` | 架构治理 (委派 arcnode-*) |
| `cockpit identity` | 导出身份封套 (IdentityEnvelope) |
| `cockpit impact` | 分析符号的变更影响面 |
| `cockpit kems` | 🧬 KEMS 域治理 (domains/status/scan) |
| `cockpit mof` | MOF 元模型操作 (委派 mof CLI) |
| `cockpit mutate` | 通过 agora 统一 BOS URI 写协议修改资源 |
| `cockpit omo` | OMO CLI 委派 (debt/state/governance/lint/...) |
| `cockpit sanyi-status` | 读取 Runtime 三医状态一致性回执 |
| `cockpit scan` | 平面扫描 |
| `cockpit skill` | 运行 L4 定时技能 |
| `cockpit ssb` | [DEPRECATED] SSB 签名链操作 — ECOS SSB 独立 CLI 已弃用 |
| `cockpit validate` | 验证 Workspace 契约 |

## 工作流与协同

| 命令 | 描述 |
|------|------|
| `cockpit agent` | 🤖 Agent 治理控制入口 (bootstrap / status / start / claim / verify / closeout) |
| `cockpit agent-onboard` | 🤖 Agent 入职引导 checklist (profile + MCP + BOS + skills) |
| `cockpit agent-runtime` | 🤖 Agent Runtime 任务执行 / HTTP server (替代独立 agent-runtime 命令) |
| `cockpit agent-workflow` | 🤖 Agent 可执行治理流程 (委派 root bin/agent-workflow.py) |
| `cockpit bcos` | BCOS 业务域系统 (evolve/signals/north-star) |
| `cockpit bdsk` | 🧠 B.D.S.K. 虚拟董事会 (4角对抗辩论与 0-Touch 影子预演) |
| `cockpit c2g` | 🎯 C2G 战略罗盘 (status/pipeline) |
| `cockpit compass` | 🧭 C2G 战略罗盘 (V2P -> C2G -> AGC 统一管理) |
| `cockpit event` | 导出事件封套 (EventEnvelope) |
| `cockpit events` | 实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard) |
| `cockpit events-watch` | 实时监听 SSE 事件流简便入口 |
| `cockpit iterate` | ♻️ C2G 双擎迭代流 (MetaOS 发散 -> Model-Driven 桥接 -> OMO 门控执行) |
| `cockpit journey` | 🗺️ Journey State Graph 状态表达校验器 |
| `cockpit monitor` | 📊 实时终端大盘 (C2G Pipeline 监控仪, 实时刷新 Ctrl+C 退出) |
| `cockpit onboarding` | 为 AI 构建项目全貌上下文 |
| `cockpit panorama` | 🌐 7 维全景终极可观测仪表盘 (执行过程/服务/内容/知识/数据/异常/债务资产) |
| `cockpit resident` | Resident 常驻 Agent 体系 (status/roles/daemon/decision/execute/...) |
| `cockpit swarm` | 🤖 多 agent 实时活动监控 (active runs/locks/worktree/claims/子模块 dirty/冲突) |
| `cockpit wave2` | 📈 Wave2 预测治理面板 (dashboard/proposals/predictive JSON) |
| `cockpit workflow` | BOS workflow 相关 |

## 算力与推理

| 命令 | 描述 |
|------|------|
| `cockpit backends` | 列出 BOS 后端 |
| `cockpit compute` | 算力与 LLM 网关操作 (委派 aetherforge) |
| `cockpit fabric` | 检查 omlxc 智能算力织网 (温控/分诊/显存/缓存) |
| `cockpit fabric-mesh` | 局域网边缘算力漫游网格 (ADR-0202) |
| `cockpit mesh` | omlx 算力网格路由入口 |
| `cockpit proxy-env` | 输出兼容外部客户端的本地环境变量 (OPENAI_API_BASE) |
| `cockpit snapshot` | KV 缓存快照管理与预热 |
| `cockpit speculative-eval` | 本地首选投机推演评估 |
| `cockpit triage` | 分析 Prompt 意图复杂度分级 |
| `cockpit vram` | 计算模型动态 KV Cache 显存预算 |
| `cockpit warm` | 预热系统 Prompt 前缀缓存以实现 0ms TTFT |

## 沙箱与卡带

| 命令 | 描述 |
|------|------|
| `cockpit cartridge` | 👁️ 长尾领域治理卡带工坊 (ADR-0198/0203) |
| `cockpit challenge` | ⚡️ 影子红蓝对抗审查与合规自动打补丁 (ADR-0196) |
| `cockpit down` | 停止观测栈 |
| `cockpit invoke` | 通过治理网关调用 exact native BOS capability |
| `cockpit pack` | 将代码库打包为 LLM 友好格式 |
| `cockpit pipeline` | pipeline 概览 |
| `cockpit run` | 在隔离沙箱中挂载卡带并执行领域意图 |
| `cockpit runtime` | runtime CLI 委派 (Matrix/Scheduler/KEI 沙箱) |
| `cockpit serve` | stdio JSON-RPC serve mode |
| `cockpit up` | 启动观测栈 |

## 内存总线与通信

| 命令 | 描述 |
|------|------|
| `cockpit ack` | 确认任务完成 |
| `cockpit agora` | Agora BOS 网关入口 (委派 agora CLI) |
| `cockpit bus` | Omni-Bus 三平面入口 |
| `cockpit channels` | 🌐 External channels inventory (ECCP) — 生成/查看 external-channels.yaml |
| `cockpit control` | 控制平面：submit / ack / nack |
| `cockpit controller-shadow` | 读取 Runtime 旧控制器影子迁移回执 |
| `cockpit daemon` | 启动 Agora 2.0 后台常驻守护进程 (Agent-to-Agent Bus) |
| `cockpit nack` | 否定确认任务 |
| `cockpit pending` | 查看未决待办快照预览 |
| `cockpit publish` | 发布事件 |
| `cockpit submit` | 提交控制任务 |

## BOS 与 MCP 网关

| 命令 | 描述 |
|------|------|
| `cockpit api` | 启动 API server |
| `cockpit bos` | BOS URI 查询与管理 |
| `cockpit bos-capability` | BOS capability / toolbox 外部能力 |
| `cockpit bos-inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit capability` | BOS capability 域 / toolbox 外部能力 |
| `cockpit client` | 以 REPL 模式连接到 MCP server |
| `cockpit mcp` | 启动 MCP server 或列出工具 |
| `cockpit nodes` | 列出 KOS 中注册的算力节点 |
| `cockpit register` | 注册 BOS 服务 |
| `cockpit reload` | 重载 BOS 配置/M1 |
| `cockpit resolve` | 统一 BOS URI 路由解析与目标元数据提取 |
| `cockpit route` | 为模型选择最优节点 |
| `cockpit types` | 查看已注册的数据类型 |
| `cockpit url` | 打印 Langfuse Web URL |

## 知识与图谱

| 命令 | 描述 |
|------|------|
| `cockpit archive` | 归档已处理完毕的 Inbox 待办文件 |
| `cockpit brain` | 个人数字大脑 — 知识检索 + 记忆 + 智能问答 |
| `cockpit code` | 代码库分析与审查 (基于 codeanalyze) |
| `cockpit consolidate` | sleep-time 巩固 (默认 dry-run) |
| `cockpit data` | 数据目录索引 / 类型注册 / TTL 清理 |
| `cockpit export` | 导出契约封套 |
| `cockpit export-research` | 将研究对象导出为 WorkspaceObject JSON |
| `cockpit gbrain` | Postgres-native 知识库入口 (委派 gbrain CLI) |
| `cockpit gc` | 清理 data/tmp 过期文件 |
| `cockpit graph` | 运行语义图谱分析 |
| `cockpit index` | 刷新 data/_index 元数据 |
| `cockpit kairon` | kairon 知识引擎 monorepo 聚合入口 |
| `cockpit knowledge` | 📚 KOS 知识检索 (search/status/stats) |

## 记忆与认知

| 命令 | 描述 |
|------|------|
| `cockpit ask` | 向大脑提问（知识检索 + LLM 回答） |
| `cockpit forget` | 遗忘传播 |
| `cockpit get` | 查 1 个 card |
| `cockpit intent` | 🧠 自然语言意图解构与工程规格编译器 (ADR-0195) |
| `cockpit memory` | 🧠 Memory OS (status/recall/write/forget/consolidate/knowledge-ref) |
| `cockpit memory-distill` | 记忆自蒸馏与冲突自愈 (ADR-0200) |
| `cockpit read` | 通过 BOS 网关统一读取指定 URI 资源 |
| `cockpit recall` | 意图路由召回（neo4j/temporal 支持 --as-of） |
| `cockpit remember` | 手动存入偏好/事实 |
| `cockpit write` | 双轨写入 (+ Neo4j FACT 若配置) |

## 研究与探索

| 命令 | 描述 |
|------|------|
| `cockpit daily` | 每日研究简报 |
| `cockpit discover` | 发现可用功能和资源 |
| `cockpit import` | 导入外部内容 |
| `cockpit research` | 深度研究 |
| `cockpit search` | 全文搜 CARDS |
| `cockpit topics` | 列出已注册 topic |
| `cockpit vault` | 搜索 L4 Vault 知识库 |

## 系统状态与观测

| 命令 | 描述 |
|------|------|
| `cockpit brief` | 会话简报 |
| `cockpit context` | 显示系统上下文 (Phase/CARDS/约束/引导) |
| `cockpit dashboard` | 打开 Web Dashboard |
| `cockpit health` | 一键系统健康检查 |
| `cockpit history` | 查看对话历史 |
| `cockpit inspect` | 查看算力网格健康度与节点状态 |
| `cockpit logs` | 查看日志 |
| `cockpit metrics` | 查看 bus metrics 快照 |
| `cockpit model-freshness` | 读取 Runtime 模型新鲜度回执 |
| `cockpit observe` | 可观测性栈（Langfuse）入口 |
| `cockpit product-health` | 产品健康度检测 |
| `cockpit readiness` | P66: governance readiness dashboard 摘要 (4 卡片: summary/dimensions/alerts/history) |
| `cockpit score` | 评分债务项 |
| `cockpit stats` | 索引统计 |
| `cockpit status` | 系统健康 |
| `cockpit summary` | 债务摘要 (委派 omo debt) |
| `cockpit tui` | 极客终端交互控制台 (Textual 全屏 TUI) |
| `cockpit version` | 版本信息 |
| `cockpit watch` | 监听 BOS Inbox 紧急待办与提醒快照 (Event-Driven Watcher) |

## 生活与业务场景

| 命令 | 描述 |
|------|------|
| `cockpit family-hub` | 家庭数字枢纽入口 |
| `cockpit finance` | 💰 个人财务门户引导 (场景/原则/入口, 委派 @个人 域) |
| `cockpit gongwen` | 📄 公文写作门户引导 (文种/规范/入口, 委派 @公文 域) |
| `cockpit inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit list` | 列债务项 (委派 omo debt) |
| `cockpit profile` | 查看/编辑身份档案 (L4 入口) |
| `cockpit scenario` | P5 统一 scenario 入口 (radar/assistant/health/inbox/intake/task/approval/connector/review) |

## 新手与入门

| 命令 | 描述 |
|------|------|
| `cockpit analyze` | 运行全部分析工具 |
| `cockpit demo` | 快速演示 |
| `cockpit help` | 查看产品地图与快速入门 (cockpit help <关键词> 模糊搜命令/工具/服务) |
| `cockpit init` | 🚀 初始化向导（同 quickstart） |
| `cockpit model-driven` | [DEPRECATED] 模型驱动生命周期入口 (ADR-0240 D1) — 拒绝执行 |
| `cockpit project` | 🔍 17 项目全景 4D 体检与诊断 |
| `cockpit quickstart` | 🚀 新用户快速上手向导（环境核验 + 上手指引） |
| `cockpit quickstart-check` | 快速检查新用户环境核验状态 |

---

### MCP 工具映射

每个项目入口命令对应的 MCP 服务器:

| CLI 命令 | MCP 服务器 | 工具数 |
|----------|-----------|--------|
| `cockpit omo` | `omo` | 22 |
| `cockpit kairon` | `kos/iris/sophia/kronos/minerva/codeanalyze/forge/ontoderive` | 123 |
| `cockpit gbrain` | `gbrain` | 75 |
| `cockpit model-driven` | `model-driven` | 28 |
| `cockpit agora` | `agora` | 89 |
| `cockpit family-hub` | `family-hub` | 6 |
| `cockpit mesh` | `aetherforge` | 15 |
| `cockpit compute` | `aetherforge` | 15 |

*由 `bin/cockpit/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*