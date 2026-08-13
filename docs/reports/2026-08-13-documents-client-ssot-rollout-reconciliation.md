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
3. 在可接受的维护窗口执行 `cockpit kems scan`，把全盘内容审计结果作为独立
   证据，而不影响日常 `kems status` 的有界返回；
4. 为确有结构化 Facts 的其他域显式注册 Runtime job；在未注册前保持
   `facts-validation` 的 unavailable 语义。
