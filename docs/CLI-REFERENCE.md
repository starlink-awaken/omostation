# Cockpit CLI 命令参考

> 自动生成于 1970-01-01T00:00:00Z
> 源: `docs/generated/capability-registry.yaml`

共 **134** 个命令 (含子命令)。按场景分组如下。

## 入门

| 命令 | 描述 |
|------|------|
| `cockpit help` | 查看产品地图与快速入门 (cockpit help <关键词> 模糊搜命令/工具/服务) |
| `cockpit init` | 🚀 初始化向导（同 quickstart） |
| `cockpit quickstart` | 🚀 新用户快速上手向导（环境核验 + 上手指引） |

## 研究

| 命令 | 描述 |
|------|------|
| `cockpit daily` | 每日研究简报 |
| `cockpit discover` | 发现可用功能和资源 |
| `cockpit import` | 导入外部内容 |
| `cockpit research` | 深度研究 |
| `cockpit search` | 全文搜 CARDS |
| `cockpit vault` | 搜索 L4 Vault 知识库 |

## 系统与状态

| 命令 | 描述 |
|------|------|
| `cockpit brief` | 会话简报 |
| `cockpit context` | 显示系统上下文 (Phase/CARDS/约束/引导) |
| `cockpit dashboard` | 打开 Web Dashboard |
| `cockpit demo` | 快速演示 |
| `cockpit health` | 一键系统健康检查 |
| `cockpit product-health` | 产品健康度检测 |
| `cockpit readiness` | P66: governance readiness dashboard 摘要 (4 卡片: summary/dimensions/alerts/history) |
| `cockpit status` | 系统健康 |
| `cockpit version` | 版本信息 |

## 治理

| 命令 | 描述 |
|------|------|
| `cockpit audit` | 🔍 6 维度全方位审计 (调 bin/workspace-audit) |
| `cockpit cards` | 显示 CARDS 卡片状态 |
| `cockpit contracts` | 契约验证 |
| `cockpit debt` | 债务评分 (omo-debt Pattern 09 v2.1) |
| `cockpit domains` | 列出 L4 所有域及其状态 |
| `cockpit gac` | GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift) |
| `cockpit governance` | 架构治理 (委派 arcnode-*) |
| `cockpit mof` | MOF 元模型操作 (委派 mof CLI) |
| `cockpit omo` | OMO CLI 委派 (debt/state/governance/lint/...) |
| `cockpit skill` | 运行 L4 定时技能 |
| `cockpit ssb` | [DEPRECATED] SSB 签名链操作 — ECOS SSB 独立 CLI 已弃用 |

## 项目入口

| 命令 | 描述 |
|------|------|
| `cockpit agora` | Agora BOS 网关入口 (委派 agora CLI) |
| `cockpit bus` | Omni-Bus 三平面入口 |
| `cockpit compute` | 算力与 LLM 网关操作 (委派 aetherforge) |
| `cockpit family-hub` | 家庭数字枢纽入口 |
| `cockpit gbrain` | Postgres-native 知识库入口 (委派 gbrain CLI) |
| `cockpit kairon` | kairon 知识引擎 monorepo 聚合入口 |
| `cockpit mesh` | omlx 算力网格路由入口 |
| `cockpit model-driven` | [DEPRECATED] 模型驱动生命周期入口 (ADR-0240 D1) — 拒绝执行 |
| `cockpit observe` | 可观测性栈（Langfuse）入口 |
| `cockpit runtime` | runtime CLI 委派 (Matrix/Scheduler/KEI 沙箱) |

## 工作流与 Agent

| 命令 | 描述 |
|------|------|
| `cockpit agent` | 🤖 Agent 治理控制入口 (bootstrap / status / start / claim / verify / closeout) |
| `cockpit agent-runtime` | 🤖 Agent Runtime 任务执行 / HTTP server (替代独立 agent-runtime 命令) |
| `cockpit agent-workflow` | 🤖 Agent 可执行治理流程 (委派 root bin/agent-workflow.py) |
| `cockpit compass` | 🧭 C2G 战略罗盘 (V2P -> C2G -> AGC 统一管理) |
| `cockpit events` | 实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard) |
| `cockpit iterate` | ♻️ C2G 双擎迭代流 (MetaOS 发散 -> Model-Driven 桥接 -> OMO 门控执行) |
| `cockpit monitor` | 📊 实时终端大盘 (C2G Pipeline 监控仪, 实时刷新 Ctrl+C 退出) |
| `cockpit wave2` | 📈 Wave2 预测治理面板 (dashboard/proposals/predictive JSON) |
| `cockpit workflow` | BOS workflow 相关 |

## BOS 与 MCP

| 命令 | 描述 |
|------|------|
| `cockpit bos` | BOS URI 查询与管理 |
| `cockpit mcp` | 启动 MCP server 或列出工具 |

## 知识与大脑

| 命令 | 描述 |
|------|------|
| `cockpit brain` | 个人数字大脑 — 知识检索 + 记忆 + 智能问答 |
| `cockpit code` | 代码库分析与审查 (基于 codeanalyze) |
| `cockpit data` | 数据目录索引 / 类型注册 / TTL 清理 |

## 生活场景

| 命令 | 描述 |
|------|------|
| `cockpit finance` | 💰 个人财务门户引导 (场景/原则/入口, 委派 @个人 域) |
| `cockpit gongwen` | 📄 公文写作门户引导 (文种/规范/入口, 委派 @公文 域) |
| `cockpit profile` | 查看/编辑身份档案 (L4 入口) |
| `cockpit scenario` | P5 统一 scenario 入口 (radar/assistant/health/inbox/intake/task/approval/connector/review) |

## 其他

| 命令 | 描述 |
|------|------|
| `cockpit ack` | 确认任务完成 |
| `cockpit agent-onboard` | 🤖 Agent 入职引导 checklist (profile + MCP + BOS + skills) |
| `cockpit analyze` | 运行全部分析工具 |
| `cockpit api` | 启动 API server |
| `cockpit archive` | 归档已处理完毕的 Inbox 待办文件 |
| `cockpit ask` | 向大脑提问（知识检索 + LLM 回答） |
| `cockpit backends` | 列出 BOS 后端 |
| `cockpit bdsk` | 🧠 B.D.S.K. 虚拟董事会 (4角对抗辩论与 0-Touch 影子预演) |
| `cockpit bos-capability` | BOS capability / toolbox 外部能力 |
| `cockpit bos-inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit c2g` | 🎯 C2G 战略罗盘 (status/pipeline) |
| `cockpit capability` | BOS capability 域 / toolbox 外部能力 |
| `cockpit channels` | 🌐 External channels inventory (ECCP) — 生成/查看 external-channels.yaml |
| `cockpit consolidate` | sleep-time 巩固 (默认 dry-run) |
| `cockpit control` | 控制平面：submit / ack / nack |
| `cockpit controller-shadow` | 读取 Runtime 旧控制器影子迁移回执 |
| `cockpit domain-status` | 显示 Documents 域项目绑定与引导状态 |
| `cockpit down` | 停止观测栈 |
| `cockpit event` | 导出事件封套 (EventEnvelope) |
| `cockpit events-watch` | 实时监听 SSE 事件流简便入口 |
| `cockpit export` | 导出契约封套 |
| `cockpit export-research` | 将研究对象导出为 WorkspaceObject JSON |
| `cockpit facts-audit` | 审计 Documents 文档域 facts 文件 |
| `cockpit facts-validation` | 读取 Runtime Facts 审计回执 |
| `cockpit forget` | 遗忘传播 |
| `cockpit gc` | 清理 data/tmp 过期文件 |
| `cockpit get` | 查 1 个 card |
| `cockpit graph` | 运行语义图谱分析 |
| `cockpit history` | 查看对话历史 |
| `cockpit identity` | 导出身份封套 (IdentityEnvelope) |
| `cockpit impact` | 分析符号的变更影响面 |
| `cockpit inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit index` | 刷新 data/_index 元数据 |
| `cockpit invoke` | 调用 capability 服务（执行 BOS YAML command） |
| `cockpit journey` | 🗺️ Journey State Graph 状态表达校验器 |
| `cockpit kems` | 🧬 KEMS 域治理 (domains/status/scan) |
| `cockpit knowledge` | 📚 KOS 知识检索 (search/status/stats) |
| `cockpit list` | 列债务项 (委派 omo debt) |
| `cockpit logs` | 查看日志 |
| `cockpit memory` | 🧠 Memory OS (status/recall/write/forget/consolidate/knowledge-ref) |
| `cockpit metrics` | 查看 bus metrics 快照 |
| `cockpit model-freshness` | 读取 Runtime 模型新鲜度回执 |
| `cockpit mutate` | 通过 agora 统一 BOS URI 写协议修改资源 |
| `cockpit nack` | 否定确认任务 |
| `cockpit nodes` | 列出 KOS 中注册的算力节点 |
| `cockpit onboarding` | 为 AI 构建项目全貌上下文 |
| `cockpit pack` | 将代码库打包为 LLM 友好格式 |
| `cockpit panorama` | 🌐 7 维全景终极可观测仪表盘 (执行过程/服务/内容/知识/数据/异常/债务资产) |
| `cockpit pending` | 查看未决待办快照预览 |
| `cockpit pipeline` | pipeline 概览 |
| `cockpit project` | 🔍 17 项目全景 4D 体检与诊断 |
| `cockpit proxy-env` | 输出兼容外部客户端的本地环境变量 (OPENAI_API_BASE) |
| `cockpit publish` | 发布事件 |
| `cockpit quickstart-check` | 快速检查新用户环境核验状态 |
| `cockpit read` | 通过 BOS 网关统一读取指定 URI 资源 |
| `cockpit recall` | 意图路由召回（neo4j/temporal 支持 --as-of） |
| `cockpit register` | 注册 BOS 服务 |
| `cockpit reload` | 重载 BOS 配置/M1 |
| `cockpit remember` | 手动存入偏好/事实 |
| `cockpit resolve` | 统一 BOS URI 路由解析与目标元数据提取 |
| `cockpit route` | 为模型选择最优节点 |
| `cockpit sanyi-status` | 读取 Runtime 三医状态一致性回执 |
| `cockpit scan` | 平面扫描 |
| `cockpit score` | 评分债务项 |
| `cockpit serve` | stdio JSON-RPC serve mode |
| `cockpit stats` | 索引统计 |
| `cockpit submit` | 提交控制任务 |
| `cockpit summary` | 债务摘要 (委派 omo debt) |
| `cockpit swarm` | 🤖 多 agent 实时活动监控 (active runs/locks/worktree/claims/子模块 dirty/冲突) |
| `cockpit topics` | 列出已注册 topic |
| `cockpit tui` | 极客终端交互控制台 (Textual 全屏 TUI) |
| `cockpit types` | 查看已注册的数据类型 |
| `cockpit up` | 启动观测栈 |
| `cockpit url` | 打印 Langfuse Web URL |
| `cockpit validate` | 验证 Workspace 契约 |
| `cockpit watch` | 监听 BOS Inbox 紧急待办与提醒快照 (Event-Driven Watcher) |
| `cockpit write` | 双轨写入 (+ Neo4j FACT 若配置) |

---

### MCP 工具映射

每个项目入口命令对应的 MCP 服务器:

| CLI 命令 | MCP 服务器 | 工具数 |
|----------|-----------|--------|
| `cockpit omo` | `omo` | 22 |
| `cockpit kairon` | `kos/iris/sophia/kronos/minerva/codeanalyze/forge/ontoderive` | 123 |
| `cockpit gbrain` | `gbrain` | 75 |
| `cockpit model-driven` | `model-driven` | 28 |
| `cockpit agora` | `agora` | 65 |
| `cockpit family-hub` | `family-hub` | 6 |
| `cockpit mesh` | `aetherforge` | 10 |
| `cockpit compute` | `aetherforge` | 10 |

*由 `bin/cockpit/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*