---
title: "Documents 客户端投影与 Cockpit 路由阶段复盘"
date: 2026-08-13
status: reconciled
scope: "Documents 域网关、Workspace Cockpit MCP、本机客户端投影与外部 ChatGPT 隧道前置条件"
---

# Documents 客户端投影与 Cockpit 路由阶段复盘

## 结论与边界

Documents 域身份继续只由 L4 `DOMAIN.yaml` 和 Domain Registry 决定；
Workspace 只持有客户端能力绑定；Cockpit 是两者的只读组合入口。每个已注册
Documents 域都可以作为独立项目打开，并通过同一个 Cockpit MCP 请求
`domain_context(domain_id=...)`。域内网关不复制 Skills、Workflow、运行实现或
Workspace 物理路径。

本次结论不包含桌面客户端的视觉重载/模型调用，也不包含 ChatGPT Web 连接。
这些是与配置和 stdio 协议不同的外部验收面。

## 权威来源

| 事实 | 唯一来源 | 客户端消费方式 |
|---|---|---|
| 域身份、边界、生命周期 | Documents L4 Domain Registry 与各域 `DOMAIN.yaml` | 域网关恢复 ID；Cockpit 校验并返回身份 |
| 可用 MCP 工具、Skills、Workflow 路由 | Workspace `documents-domain-projects` binding registry | Cockpit `domain_context` 返回受限能力与路由指针 |
| 运行和审计回执 | 注册 Runtime owner 的 state/evidence | Cockpit 专用状态工具只读投影 |
| 本机客户端投影 | Workspace 生成器与客户端自有设置 | 只管理 Cockpit 项；保留不相关模型、凭据和 MCP 项 |

这四类来源不互相回写，因而不创建每个域各自维护运行时或能力清单的第二套
权威。

## 2026-08-13 实测

### Cockpit 与已注册域

使用已安装 `cockpit-mcp` 进行一次新的 stdio MCP 会话。会话初始化、工具列表和
逐域 `domain_context` 均在同一进程中完成：所有注册域返回
`status=ok`、`available=true` 和 `binding.profile_id=content-domain`。
`documents-domain-project-check` 也返回 `ok=true`、零错误。这个证据证明的是
协议路由和绑定解析，而不是某个客户端 UI 已显示工具。

卫健委的 `domain_context` 还明确返回 `execution_policy=workspace_only`：
知识运行时由 `kairon-kos` 负责，结构化 Facts 审计由注册的 Runtime job 负责。
因此域内文件仍是数据、资料、知识和网关，不是第二个 KEMS/Runtime。

### Facts 与 KEMS 的审计语义

`facts-audit` 和 `facts-validation` 不能混为一个绿灯：

- `facts-audit` 只审计各域人类可读的 `_entities/facts.md` 视图是否存在；
- `facts-validation` 读取 Runtime 的结构化 Facts 回执。卫健委当前回执为 `ok`，
  并包含总量、类型分布、错误数和警告数；没有为其他域虚构同类任务；
- `kems status` 现在是有界状态查询。它如实报告全盘 Documents content audit
  为 `not_run`，并提示显式运行 `cockpit kems scan`。本次没有把一次大范围内容
  扫描伪装成状态检查，也没有把 `not_run` 说成健康。
- `kems scan` 使用 L4 的有界摘要契约：日常入口只返回分类计数、违规总数和有限
  样例，不再把所有合法 artifact 的完整清单输出到终端。需要逐文件取证时，才直接
  使用 L4 的完整 `content audit --json` 输出。

### 本机客户端投影

| 客户端 | 本轮验证 | 明确未宣称 |
|---|---|---|
| Claude Desktop（第三方部署） | 活动配置中已有接受版 `cockpit-mcp` 及 Workspace/Documents/L4 scope 变量；第三方模型配置未修改 | 重启后的 UI、模型实际工具调用 |
| Codex | `documents` 专用 profile 由 Workspace 生成器安装后回检为 `ok`；仅启用 content-domain 声明的 Cockpit 只读工具，并在该 profile 禁用其他 MCP 与用户级 Skills | 应用 UI 的 profile 选择和模型旅程 |
| Zed | Documents profile 只补齐 `domain_facts_validation_status` 及其只读许可，正式 checker 回检为 `ok`，设置仍为 owner-only | 重载后的工具可见性和模型调用 |
| ZCode | 原生 JSON 配置 checker 为 `ok`；Cockpit 受管项保持符合契约，第三方 provider/model 和不相关 server 未改 | ZCode 发起的模型调用 |
| ChatGPT Web/Cowork | Secure MCP Tunnel 预检明确返回 `unavailable` | 隧道已创建、凭据已配置、Developer Mode 已连接 |

ChatGPT 的前置条件是外部平台状态：tunnel client、`CONTROL_PLANE_API_KEY` 和
`DOCUMENTS_CHATGPT_TUNNEL_ID`。这些值在本轮均不存在，且不应写入 Workspace、
Documents、客户端配置或证据文件。完成该外部 provisioning 后，仍需单独做一次
ChatGPT 发起的只读 `domain_context` 验收。

## 本轮修正

这次复核修正了一个容易产生错误归因的历史判断。此前 `kems_status` 的超时曾被
怀疑为卫健委 `kems-toolkit.py` 软链断开；当前软链目标存在，而 Cockpit 的有界
`kems status` 并不调用该脚本。旧超时来自将大规模 Documents 内容审计放进状态
查询的实现，当前设计已将其拆成显式扫描。

卫健委域仓同时存在大量独立的内容变更，因此本轮没有向该仓混入审查文档、没有
清理 `index.lock`，也没有创建域级提交。需要提交的内容应先在该域的独立变更集
中完成审阅和归属确认。

## 后续验收

1. 人工重启或重载 Claude Desktop、Codex、Zed 和 ZCode，分别验证 Documents
   项目中可见 Cockpit 工具且能调用 `domain_context`；
2. 由具备外部平台权限的操作者 provision ChatGPT Secure MCP Tunnel，随后以
   ChatGPT Developer Mode 执行只读域上下文 smoke；
3. 已在维护窗口执行一次 `cockpit kems scan`。它按预期以非零退出，报告已有
   runtime、cache 和无效 archive 内容债务；债务归类和迁移另立变更集，不在这次
   客户端/路由收口中删除或改写 Documents 内容。后续可重复运行摘要扫描，不影响
   日常 `kems status` 的有界返回；
4. 为确有结构化 Facts 的其他域显式注册 Runtime job；在未注册前保持
   `facts-validation` 的 unavailable 语义。

## 阶段收口复验（2026-08-13）

后续安装态复验发现并修正了 Cockpit 的一个实际解析缺陷：accepted checkout 中
`projects/.omo -> ../.omo` 是兼容软链；旧解析器把它当作工作区根，导致未显式设置
`WORKSPACE_ROOT` 的 CLI 将能力注册表解析到 `accepted/projects`。修复后的解析器忽略
该兼容软链，只接受真实的 Workspace authority 目录。

修复已先合并至 Cockpit PR #45（`906d009`），再由 Workspace PR #1417 将根仓库
gitlink 指向该版本。accepted root 已快进到 `66cb8fea`，并以冻结依赖重装 Cockpit。
以下是安装态的实际结果：

- 默认 `cockpit domain-status` 返回 12/12 `ok`；
- 默认 `cockpit facts-validation work-weijian` 返回 `ok`，总量 271、错误 0、警告 4；
- accepted `cockpit-documents-mcp` 仅暴露五个只读工具：`workspace_context`、
  `domain_context`、`cards_status`、`cards_check`、
  `domain_facts_validation_status`；最后一项对 `work-weijian` 返回 `ok`；
- `cockpit kems status` 在有界时间内返回 `degraded`，唯一原因仍是全盘 audit
  `not_run`，不是超时或错误成功。
- 完整 `cockpit kems scan` 已实际执行并返回预期的非零债务状态；先前完整 JSON
  将海量合法 artifact 倾倒到终端的可用性缺口，已由 L4 PR #6（`f0026cc`）的摘要
  契约和 Cockpit PR #46（`4707bed`）的有界渲染收口。扫描保留总量、违规类型与
  最多十个样例，完整逐文件取证仍需显式走 L4 明细审计。

这不是全体客户端 UI 验收：Claude、Codex、Zed 与 ZCode 的本机配置投影已分别由
其正式 checker 或生成器确认，但每个客户端的重载后 UI/模型调用仍是独立操作面。
ChatGPT 也仍缺外部 Tunnel 的实际 provision；本地已具备的只读 MCP 契约不替代
平台连接、凭据或 Developer Mode 授权。

## 安装态与能力目录复验（2026-08-13，Phase 49）

本节是对上文历史快照的追加核验，不回写上文的时间、范围或结论。验收使用的
Workspace accepted checkout 已处于根提交 `4291b4b`，其 Cockpit gitlink 为
`626d3a0`。

### 全域独立项目路由

以新的 Cockpit MCP 调用分别请求 12 个 L4 已注册 Documents 域的
`domain_context(domain_id)`。12 个结果都为 `status=ok`、`available=true`，且都
解析到唯一的 `content-domain` profile：

- Skills route 解析到 Workspace `.agents/skills`，状态为 `ok`；
- Workflow route 解析到 Workspace `agent-workflows.yaml`，状态为 `ok`；
- 执行策略均为 `workspace_only`，因此域内不会再成为 KEMS 或 Runtime 的第二套
  实现/状态权威；
- `documents-domain-index check` 与 `documents-domain-project-check --json` 同时
  通过，后者返回 `domain_count=12`、`gateway_count=12`、`errors=[]`。

这证明“每个 Documents 域可作为独立项目接入同一个 Workspace 控制面”的协议面已经
成立。它不意味着所有域都拥有相同的内容审计任务；例如结构化 Facts Runtime job 仍
只在已显式注册的卫健委域上返回可用回执。

### 能力目录的 SSOT 修复

复验中发现 Workspace 能力注册表生成器只扫描了 Cockpit 的旧 `cli.py`，而部分
命令已经注册在 `_subcommands.py`。结果会把 CLI 目录错误生成成零命令，影响客户端
从能力目录发现 Documents 的 Cockpit 入口。

该缺陷已由 Cockpit PR #48 和 Workspace PR #1423 修复并合并：生成器现在扫描两个
注册模块，测试锁定 `context`、`domain-status`、`facts-validation` 与 `kems`，再生成
`capability-registry.yaml`、CLI reference、MCP index 与 Cockpit capability map。
安装态重复生成后没有这些派生文件的差异；目录当前记录 130 条 Cockpit CLI 命令和
565 个 MCP 工具。该修复只同步派生目录，不改变 Documents 内容或 Runtime 行为。

### 客户端验收矩阵

| 客户端 | 当前已证实 | 尚待的外部验收 |
|---|---|---|
| Claude Desktop（第三方部署） | 配置含受管 `cockpit` server，且正在运行的 Claude 进程已启动 accepted `cockpit-mcp` | 在 Claude UI 中以实际模型调用 `domain_context` |
| Codex | `documents-codex-profile check` 为 `ok`；profile 只保留受管 Cockpit 入口 | 在 Documents 项目窗口执行一次只读工具调用 |
| Zed | `documents-zed-profile check` 为 `ok` | 重载 Agent Profile 后调用一次只读工具 |
| ZCode | `documents-zcode-config check` 为 `ok`，且不相关 provider/MCP 设置保持不变 | 安装/启动 ZCode 后调用一次只读工具 |
| ChatGPT Web/Cowork | 受管预检如实返回 `unavailable` | 建立 Tunnel 并在 Developer Mode 调用一次只读工具 |

ChatGPT 的未完成项不是本地配置遗漏。官方 Secure MCP Tunnel 文档要求：Platform
tunnel endpoint 的 `tunnel_id`、供 `tunnel-client` 使用的 runtime API key，以及该
client 能从私网到达 MCP server；创建/管理 tunnel 的权限与 ChatGPT Developer Mode
访问也相互独立。当前机器未配置 tunnel client、平台 API key 或 tunnel ID，因此本轮
没有创建 tunnel、没有写入凭据，也不宣称 ChatGPT 已连通。官方指南：
<https://developers.openai.com/api/docs/guides/secure-mcp-tunnels>。

### 阶段结论

Documents 域身份（L4 Manifest）、能力绑定（Workspace binding registry）、能力目录
（Workspace generated registry）和客户端投影已经各自回到单一权威来源，并通过
实际 12 域 MCP 路由及安装态 checker 交叉验证。剩余工作是四个本地客户端的 UI
smoke 与 ChatGPT 的外部 Platform provisioning；这些需要客户端会话或平台权限，不能
由静态配置、进程存在或本地 checker 替代。
