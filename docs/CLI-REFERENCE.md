---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-09
---

# Cockpit CLI 命令参考

> 自动生成于 1970-01-01T00:00:00Z | 源: cockpit.commands.registry (SSOT) + capability-registry.yaml
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑
> 分类全量详情见 [`docs/cli/`](cli/) 分册

共 **207** 个命令条目。八大正交域: **governance**、**workflow**、**memory**、**compute**、**bus**、**scene**、**system**、**user**。

## 目录

- [🏛️ 治理 (Governance)](cli/governance.md) (16 个命令)
- [👤 用户 (User)](cli/user.md) (8 个命令)
- [📄 专项工具 (Domain)](cli/domain.md) (13 个命令)
- [📋 项目 (Project)](cli/project.md) (12 个命令)
- [📚 研究 (Research)](cli/research.md) (8 个命令)
- [📡 通讯 (Messaging)](cli/messaging.md) (5 个命令)
- [📦 数据 (Data)](cli/data.md) (3 个命令)
- [🔌 总线接入 (ECCP)](cli/eccp.md) (1 个命令)
- [🖥️ 基础设施 (Infra)](cli/infra.md) (11 个命令)
- [🛠️ 系统 (System)](cli/system.md) (15 个命令)
- [🤖 Agent 协作](cli/agent-协作.md) (4 个命令)
- [🧠 知识引擎 (BOS)](cli/bos.md) (10 个命令)
- [遗留命令映射](#遗留命令映射) (46 个)
- [全局 Flags](#全局-flags)
- [MCP 工具映射](#mcp-工具映射)

---

## 🏛️ 治理 (Governance)

> 全量用法与元数据: [cli/governance.md](cli/governance.md)

| 命令 | 描述 |
|------|------|
| `cockpit audit-ledger` | 📒 [DEPRECATED] 治理审计账本 ADR-0201 → 查询 .omo/_knowledge/decisions/ + cockpit command-audit |
| `cockpit bdsk` | B.D.S.K. 虚拟董事会 (4角对抗辩论与 0-Touch 影子预演) |
| `cockpit cards` | CARDS 卡片状态管理 (list / get / search / serve) |
| `cockpit command-audit` | 15 维命令评分卡管理 (init/validate/report/lint) |
| `cockpit context` | 显示系统上下文 (Phase / CARDS / 约束 / 引导) |
| `cockpit controller-shadow` | 读取 Runtime 旧控制器影子迁移回执 |
| `cockpit dlp-guard` | 外发前防泄密扫描 (敏感识别+挂起+脱敏) |
| `cockpit domain-status` | 显示 Documents 域项目绑定与引导状态 |
| `cockpit facts-audit` | 审计 Documents 文档域 facts 文件 |
| `cockpit facts-validation` | 读取 Runtime Facts 审计回执 |
| `cockpit governance` | 架构治理 (委派 arcnode-*) |
| `cockpit harness` | Harness 全生命周期合规 (trace/verify/gac/compliance/…) |
| `cockpit mcp` | 启动 MCP server 或列出工具 |
| `cockpit model-freshness` | 读取 Runtime 模型新鲜度回执 |
| `cockpit policy` | ⚖️ 领域监管合规与 Policy-as-Code 红线审查 (E-POL-*) |
| `cockpit sanyi-status` | 读取 Runtime 三医状态一致性回执 |

## 👤 用户 (User)

> 全量用法与元数据: [cli/user.md](cli/user.md)

| 命令 | 描述 |
|------|------|
| `cockpit completion` | 生成 Shell 自动补全脚本 (bash/zsh/fish) |
| `cockpit demo` | 快速演示 |
| `cockpit docs` | CLI 参考手册生成与导出 (docs/CLI-REFERENCE.md) |
| `cockpit help` | 查看产品地图与快速入门 |
| `cockpit init` | 🚀 初始化向导（同 quickstart） |
| `cockpit profile` | 查看/编辑身份档案 (L4 入口) |
| `cockpit quickstart` | 🚀 新用户快速上手向导（环境核验 + 上手指引） |
| `cockpit quickstart-check` | 快速检查新用户环境核验状态 |

## 📄 专项工具 (Domain)

> 全量用法与元数据: [cli/domain.md](cli/domain.md)

| 命令 | 描述 |
|------|------|
| `cockpit cartridge` | 👁️ 长尾领域治理卡带工坊 (ADR-0198/0203) |
| `cockpit challenge` | ⚡️ 影子红蓝对抗审查与合规自动打补丁 (ADR-0196) |
| `cockpit code` | 代码审查与质量管理 |
| `cockpit compute` | 算力与计算任务管理 |
| `cockpit decide` | 📬 决策收件箱 (列出/添加/批准/拒绝) |
| `cockpit family-hub` | 家庭数字枢纽入口 (status / api / mcp) |
| `cockpit finance` | 💰 个人财务门户引导 (场景 / 原则 / 入口) |
| `cockpit gongwen` | 📄 公文写作门户引导 (文种 / 规范 / 入口) |
| `cockpit im-triage` | IM 消息分诊 |
| `cockpit intent` | 🧠 自然语言意图解构与工程规格编译器 (ADR-0195) |
| `cockpit omo` | OMO 健康自管系统 |
| `cockpit render` | 渲染输出 |
| `cockpit spine` | Spine 主干真值流与署名自进化操作 (ADR-0439) |

## 📋 项目 (Project)

> 全量用法与元数据: [cli/project.md](cli/project.md)

| 命令 | 描述 |
|------|------|
| `cockpit agent` | Agent 工作流编排（agent-workflow 别名） |
| `cockpit agent-workflow` | Agent 工作流编排 |
| `cockpit bcos` | BCOS 业务域系统 (evolve/signals/north-star) |
| `cockpit c2g` | Concept-to-Governance 生命周期转化 |
| `cockpit compass` | 战略罗盘 (OKR / 目标对齐) |
| `cockpit debt` | 技术债管理 (list / score / resolve) |
| `cockpit iterate` | 迭代管理 (sprint / backlog / roadmap) |
| `cockpit kems` | 知识经济指标体系 (KEMS · KPI 追踪) |
| `cockpit readiness` | Readiness Dashboard (Phase / Gate / 核验) |
| `cockpit scenario` | 统一 scenario 入口 (radar / assistant / health) |
| `cockpit wave2` | Wave2 项目战略视图 |
| `cockpit workflow` | 工作流管理 (run / list / status) |

## 📚 研究 (Research)

> 全量用法与元数据: [cli/research.md](cli/research.md)

| 命令 | 描述 |
|------|------|
| `cockpit brief` | 会话简报 (生成摘要) |
| `cockpit daily` | 每日研究简报 (生成 + 推送) |
| `cockpit discover` | 发现可用功能和资源 |
| `cockpit knowledge` | 本地知识库管理 (import / query / stats) |
| `cockpit memory` | Memory OS 统一控制面 (status/recall/write/forget → bos://memory/mos/*) |
| `cockpit memory-distill` | 🧠 [DEPRECATED] 记忆蒸馏 ADR-0200 → KOS pipeline (gbrain + eidos) |
| `cockpit research` | 深度研究工作台 (ask / publish / list / audit / …) |
| `cockpit search` | 跨源搜索 (数据库 + BOS 知识引擎) |

## 📡 通讯 (Messaging)

> 全量用法与元数据: [cli/messaging.md](cli/messaging.md)

| 命令 | 描述 |
|------|------|
| `cockpit agora` | Agora BOS 网关入口 (委派 agora CLI) |
| `cockpit bus` | Omni-Bus 三平面入口 (status / topics / publish) |
| `cockpit events` | 实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard) |
| `cockpit events-watch` | 监听 BOS Inbox 紧急待办与提醒快照 |
| `cockpit ssb` | [DEPRECATED] SSB 签名链操作 — ECOS SSB 独立 CLI 已弃用，请使用 cockpit 替代 |

## 📦 数据 (Data)

> 全量用法与元数据: [cli/data.md](cli/data.md)

| 命令 | 描述 |
|------|------|
| `cockpit contracts` | 契约验证 (validate / list / export) |
| `cockpit data` | 数据目录索引 / 类型注册 / TTL 清理 |
| `cockpit import` | 导入外部内容 (Markdown / URL / 文件) |

## 🔌 总线接入 (ECCP)

> 全量用法与元数据: [cli/eccp.md](cli/eccp.md)

| 命令 | 描述 |
|------|------|
| `cockpit channels` | External channels inventory (ECCP) |

## 🖥️ 基础设施 (Infra)

> 全量用法与元数据: [cli/infra.md](cli/infra.md)

| 命令 | 描述 |
|------|------|
| `cockpit chain` | 多命令联动链路编排 (list/show/run/validate/init, YAML 声明式) |
| `cockpit dashboard` | 打开 Web Dashboard |
| `cockpit fabric` | 🧑‍💻 主权混合算力与 KV 缓存快照 (ADR-0197) |
| `cockpit fabric-mesh` | 🕸️ [DEPRECATED] 算力网格检视 ADR-0202 → omlxc-compute-fabric skill |
| `cockpit mesh` | omlx 算力网格路由入口 (nodes / route / serve) |
| `cockpit model-driven` | [DEPRECATED] 模型驱动生命周期入口 (ADR-0240 D1) — 拒绝执行 |
| `cockpit mof` | MOF 元模型操作 (委派 mof CLI) |
| `cockpit observe` | 可观测性栈（Langfuse）入口 (up / down / logs) |
| `cockpit ops` | 🔧 Service Gateway — 统一运维控制面 |
| `cockpit telemetry` | 命令全生命周期可观测性与 Prometheus 指标导出 |
| `cockpit watchdog` | 🐕 [DEPRECATED] 自治守护犬已退役 → Mesh-bound capability admission (Cockpit PR #78) |

## 🛠️ 系统 (System)

> 全量用法与元数据: [cli/system.md](cli/system.md)

| 命令 | 描述 |
|------|------|
| `cockpit agent-runtime` | Agent 运行时生命周期管理 |
| `cockpit audit` | 🔍 6 维度全方位审计 |
| `cockpit capabilities` | 统一能力发现入口 — 搜索/推荐/全量列出 (CLI+BOS+Scene+Journey) |
| `cockpit gac` | GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift) |
| `cockpit health` | 一键系统健康检查 (7 维度) |
| `cockpit journey` | Journey State Graph 状态表达校验器 |
| `cockpit monitor` | 实时监控 (进程 / 资源 / 指标) |
| `cockpit panorama` | 7 维全景终极可观测仪表盘 (执行/服务/内容/知识/数据/异常/债务) |
| `cockpit product-health` | 产品健康度检测 |
| `cockpit project` | 16 项目全景 4D 体检与诊断 |
| `cockpit proxy-env` | 输出兼容外部客户端的本地环境变量 (OPENAI_API_BASE) |
| `cockpit runtime` | 运行时环境管理 |
| `cockpit status` | 系统健康仪表盘 (Phase / CARDS / 研究工作台) |
| `cockpit tui` | 极客终端交互控制台 (Textual 全屏 TUI · Vim 键盘流) |
| `cockpit version` | 版本信息 |

## 🤖 Agent 协作

> 全量用法与元数据: [cli/agent-协作.md](cli/agent-协作.md)

| 命令 | 描述 |
|------|------|
| `cockpit agent-onboard` | 新 Agent 入职 checklist + 环境初始化 |
| `cockpit cell` | 🤖 AGE-v2 动态 Agent Cell (规划/执行/验证/治理) |
| `cockpit resident` | Resident 常驻 Agent 体系 (status/roles/daemon/decision/execute/...) |
| `cockpit swarm` | 多 agent 实时活动监控 (runs/locks/worktree/冲突) |

## 🧠 知识引擎 (BOS)

> 全量用法与元数据: [cli/bos.md](cli/bos.md)

| 命令 | 描述 |
|------|------|
| `cockpit ask` | 快速大模型对话问答 (AetherForge) |
| `cockpit bos` | BOS URI 查询与管理 (list / resolve / read / inbox / …) |
| `cockpit bos-capability` | BOS capability 域 / toolbox 外部能力 (list / invoke) |
| `cockpit bos-inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit brain` | 个人数字大脑 (ask / remember / history / context) |
| `cockpit domains` | 列出 L4 所有域及其状态 |
| `cockpit gbrain` | Postgres-native 知识库 (search / import / stats) |
| `cockpit kairon` | kairon 知识引擎 monorepo 聚合入口 |
| `cockpit skill` | 运行 L4 定时技能 |
| `cockpit vault` | 搜索 L4 Vault 知识库 |

## 遗留命令映射

| 命令 | 域 | 目标 |
|------|-----|------|
| `cockpit agent` | workflow | agent |
| `cockpit agent-workflow` | workflow | workflow |
| `cockpit agora` | bus | agora |
| `cockpit audit` | governance | audit |
| `cockpit bcos` | workflow | bcos |
| `cockpit bos` | bus | bos |
| `cockpit brain` | memory | brain |
| `cockpit brief` | scene | brief |
| `cockpit bus` | bus | bus |
| `cockpit capability` | bus | capability |
| `cockpit completion` | user | completion |
| `cockpit contracts` | governance | contracts |
| `cockpit dashboard` | system | dashboard |
| `cockpit debt` | governance | debt |
| `cockpit demo` | user | demo |
| `cockpit docs` | user | docs |
| `cockpit events` | bus | events |
| `cockpit fabric` | compute | fabric |
| `cockpit family-hub` | scene | family-hub |
| `cockpit gac` | governance | gac |
| `cockpit gbrain` | memory | gbrain |
| `cockpit gongwen` | scene | gongwen |
| `cockpit health` | system | health |
| `cockpit help` | user | help |
| `cockpit iterate` | workflow | iterate |
| `cockpit journey` | scene | journey |
| `cockpit kairon` | memory | kairon |
| `cockpit kems` | governance | kems |
| `cockpit knowledge` | memory | knowledge |
| `cockpit memory` | memory | memory |
| `cockpit mesh` | compute | mesh |
| `cockpit policy` | governance | policy |
| `cockpit quickstart` | user | quickstart |
| `cockpit readiness` | system | readiness |
| `cockpit resident` | workflow | resident |
| `cockpit runtime` | system | runtime |
| `cockpit scenario` | scene | scenario |
| `cockpit search` | memory | search |
| `cockpit spine` | scene | spine |
| `cockpit status` | system | status |
| `cockpit telemetry` | system | telemetry |
| `cockpit triage` | compute | triage |
| `cockpit vault` | memory | vault |
| `cockpit vram` | compute | vram |
| `cockpit warm` | compute | warm |
| `cockpit watchdog` | governance | watchdog |

## 扫描发现的其他命令

| 命令 | 描述 |
|------|------|
| `cockpit ack` | 确认任务完成 |
| `cockpit add` | 手动添加决策项 |
| `cockpit analyze` | 运行全部分析工具 |
| `cockpit api` | 启动 API server |
| `cockpit approve` | 批准决策 |
| `cockpit archive` | 归档已处理完毕的 Inbox 待办文件 |
| `cockpit backends` | 列出 BOS 后端 |
| `cockpit cache` | 检查三级分层缓存与 Radix 前缀树状态 (含基准压测) |
| `cockpit calendar` | 多维日历感知与督办闭环 (T7-02) |
| `cockpit calibrate` | [v2] 校准场景卡 |
| `cockpit client` | 以 REPL 模式连接到 MCP server |
| `cockpit cluster` | 异构三节点智能路由与拓扑诊断 |
| `cockpit compact` | 上下文滑动蒸馏与双区自适应量化压缩模拟 |
| `cockpit consolidate` | sleep-time 巩固 (默认 dry-run) |
| `cockpit control` | 控制平面：submit / ack / nack |
| `cockpit dflash` | DFlash 2 块扩散投机解码加速与集群基准 |
| `cockpit diff` | 查看待处理署名 Diff 统计 |
| `cockpit distill` | 在 Mac mini M4 触发闲时 LoRA 蒸馏 |
| `cockpit dma` | 测试雷雳 5 跨机零拷贝 DMA 通道与换页基准 |
| `cockpit docx` | 渲染为 GB/T 9704-2012 红头公文 DOCX |
| `cockpit down` | 停止观测栈 |
| `cockpit draft` | 从本地主权大模型请求草稿 |
| `cockpit event` | 导出事件封套 (EventEnvelope) |
| `cockpit execute` | [v2] 执行场景卡 (BOS/MCP 驱动) |
| `cockpit export` | 导出契约封套 |
| `cockpit export-research` | 将研究对象导出为 WorkspaceObject JSON |
| `cockpit forget` | 遗忘传播 |
| `cockpit gc` | 清理 data/tmp 过期文件 |
| `cockpit get` | 查 1 个 card |
| `cockpit graph` | 运行语义图谱分析 |
| `cockpit heatmap` | 查看分布式 KV 内存池热力分布与投机蒸馏指标 |
| `cockpit history` | 查看对话历史 |
| `cockpit hud` | 查看次世代主权算力织网全景 HUD 实时状态 |
| `cockpit identity` | 导出身份封套 (IdentityEnvelope) |
| `cockpit impact` | 分析符号的变更影响面 |
| `cockpit inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit index` | 刷新 data/_index 元数据 |
| `cockpit ingress` | 感知源接入 Spine 管线 (T2-03: OCR 扫描件) |
| `cockpit inspect` | 查看算力网格健康度与节点状态 |
| `cockpit invoke` | 通过治理网关调用 exact native BOS capability |
| `cockpit knowledge-ref` | ADR-0315 引用元数据 (无正文) |
| `cockpit lifecycle` | [v2] 场景卡生命周期管理 (list/status/promote/demote/validate) |
| `cockpit list` | 列债务项 (委派 omo debt) |
| `cockpit logs` | 查看日志 |
| `cockpit lora` | 查看与测试端侧在线 LoRA 适配层热插拔 |
| `cockpit mail-draft` | 邮箱 3 档拟复 (经 BOS inbox/mail/draft 服务) |
| `cockpit metrics` | 查看 bus metrics 快照 |
| `cockpit minutes` | 会议转写文本 → 交办事项督办清单 |
| `cockpit mutate` | 通过 agora 统一 BOS URI 写协议修改资源 |
| `cockpit nack` | 否定确认任务 |
| `cockpit nodes` | 列出 KOS 中注册的算力节点 |
| `cockpit onboarding` | 为 AI 构建项目全貌上下文 |
| `cockpit org-relation` | 组织人脉图谱查询 (单位-人物-来件关系网络) |
| `cockpit pack` | 将代码库打包为 LLM 友好格式 |
| `cockpit pending` | 查看未决待办快照预览 |
| `cockpit persona-radar` | 个人文风一致性多维雷达评估 (T3-01) |
| `cockpit pipeline` | pipeline 概览 |
| `cockpit pptx` | 渲染为 16:9 高管技术汇报 PPTX |
| `cockpit prebrief` | ICS 日历事件 → 会前速递简报 |
| `cockpit publish` | 发布事件 |
| `cockpit read` | 通过 BOS 网关统一读取指定 URI 资源 |
| `cockpit recall` | 意图路由召回（neo4j/temporal 支持 --as-of） |
| `cockpit register` | 注册 BOS 服务 |
| `cockpit reject` | 拒绝决策 |
| `cockpit reload` | 重载 BOS 配置/M1 |
| `cockpit remember` | 手动存入偏好/事实 |
| `cockpit replay` | 查看 Experience Replay 缓冲区状态 |
| `cockpit resolve` | 统一 BOS URI 路由解析与目标元数据提取 |
| `cockpit review` | 左右分栏 Diff 审阅工作台 (初稿 vs 编辑态) |
| `cockpit route` | 为模型选择最优节点 |
| `cockpit run` | 在隔离沙箱中挂载卡带并执行领域意图 |
| `cockpit scan` | 平面扫描 |
| `cockpit scene` | 🗺️ 业务场景正交领域 (scenario/journey/gongwen/brief/family-hub) |
| `cockpit score` | 评分债务项 |
| `cockpit send` | 一键确认署名并经外发网关真实外发 |
| `cockpit serve` | stdio JSON-RPC serve mode |
| `cockpit sign` | 提交用户署名 Diff 并入队 Experience Replay |
| `cockpit snapshot` | KV 缓存快照管理与预热 |
| `cockpit speculative-eval` | 本地首选投机推演评估 |
| `cockpit stats` | 索引统计 |
| `cockpit strategy` | 🎲 战略决策沙盘 → 蒙特卡洛多智能体推演 (T5-01) |
| `cockpit stream` | 跨节点 Chunk-level 流式协同流水线基准 |
| `cockpit submit` | 提交控制任务 |
| `cockpit summary` | 债务摘要 (映射 omo debt report) |
| `cockpit svg` | 渲染 ```diagram 代码块为矢量架构图 SVG |
| `cockpit system` | 🖥️ 系统与运维正交领域 (status/health/dashboard/readiness/runtime) |
| `cockpit test_export_formats` | 离线自测: 三格式导出 + GB/T 参数断言 |
| `cockpit topics` | 列出已注册 topic |
| `cockpit tree` | 自适应熵感知树状投机解码与多候选验证基准 |
| `cockpit types` | 查看已注册的数据类型 |
| `cockpit up` | 启动观测栈 |
| `cockpit url` | 打印 Langfuse Web URL |
| `cockpit user` | 👤 用户体验与向导正交领域 (quickstart/help/demo/init/profile/completion) |
| `cockpit validate` | 验证 Workspace 契约 |
| `cockpit voice-memo` | 语音随想 → 转录润色分拣 → Spine 备选池 (T2-01) |
| `cockpit watch` | 监听 BOS Inbox 紧急待办与提醒快照 (Event-Driven Watcher) |
| `cockpit write` | 双轨写入 (+ Neo4j FACT 若配置) |

## 全局 Flags

所有命令共享的全局参数面:

| Flag | 说明 |
|------|------|
| `--help` / `-h` | 命令帮助 |
| `--version` / `-V` | 版本号 |
| `--json` | 机器可读 JSON 输出 |
| `--dry-run` | 预检模式 (不执行副作用) |
| `--quiet` / `-q` | 静默模式 |
| `--verbose` / `-v` | 详细输出 |
| `--output` / `-o` | 输出文件路径 |
| `--trace-id` | 链路追踪 ID (跨命令 trace 贯穿) |

## Shell 自动补全

```bash
source <(cockpit completion bash)   # Bash
source <(cockpit completion zsh)    # Zsh
cockpit completion fish | source    # Fish
```

输错命令时会给出 Levenshtein 最近邻建议 (`Did you mean ...`)。

## MCP 工具映射

| CLI 命令 | MCP 服务器 | 工具数 |
|----------|-----------|--------|
| `cockpit omo` | `omo` | 24 |
| `cockpit kairon` | `kos/iris/sophia/kronos/minerva/codeanalyze/forge/ontoderive` | 123 |
| `cockpit gbrain` | `gbrain` | 75 |
| `cockpit model-driven` | `model-driven` | 28 |
| `cockpit agora` | `agora` | 111 |
| `cockpit family-hub` | `family-hub` | 6 |
| `cockpit mesh` | `aetherforge` | 15 |
| `cockpit compute` | `aetherforge` | 15 |

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成 (T8-16 全量模式)*