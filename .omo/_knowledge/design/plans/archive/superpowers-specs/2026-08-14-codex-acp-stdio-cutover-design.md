---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-08-14
type: ssot
---

# Codex ACP stdio 权限代理切换设计

> 日期：2026-08-14
> 状态：accepted
> BET：BET-Y1Q2-T1-19

## 1. 决策摘要

本轮采用以下协议分工：

- **ACP v1 over stdio**：本机 coding agent 的 session、prompt、tool call、权限请求、
  文件和 terminal 更新、cancel；
- **MCP**：工具与上下文暴露，不承担 agent 生命周期或完成真相；
- **OMO + ECOS**：WorkPacket、Task、Workflow Mesh、CompletionManifest、
  VerificationReceipt 与最终完成判定的唯一真相；
- **A2A 1.0**：后续跨 Agent、跨进程或跨节点 federation；当前 BET 不实现；
- **Orca**：观察和人工 break-glass，不做自动 fallback，不拥有完成真相。

T1-18 继续证明人工监督的等待、恢复、真实 delta、独立验证和补偿回滚。T1-19
是它的顺序后继：先保留该基线，再用 ACP 的结构化 permission request 收敛重复人工
点击。禁止把 ACP 偷塞进 T1-18，也禁止两套自动生产 transport 长期并存。

协议依据：ACP v1 的 `session/request_permission`、session update 与 cancel 合同，以及
`@zed-industries/codex-acp@0.16.0` 提供的 Codex App Server 到 ACP 翻译边界。首轮只用
本地 stdio；remote ACP transport 仍不进入生产范围。

## 2. B.D.S.K. 四角裁决

### Builder

复用现有 OMO worker admission、WorkPacket scope、clone guard、Mesh 和 receipt，给现有
Codex adapter 增加 ACP client/session/permission 映射。固定包版本和 stdio argv；不增加
数据库、任务表或第二状态机。

### Devil

最便宜的伪完成是 fake ACP server 依次返回 initialize、session/new、session/prompt 和
turn-end，再让单元测试全绿，却从未启动真实 Codex、触发真实 permission、产生真实
git delta 或独立验证。另一种风险是 ACP 结果不确定时自动回退 Orca，造成同一副作用
执行两次。因此 live canary、tree hash、process reap、permission receipt 与幂等绑定都是
硬门，Orca fallback 禁止自动触发。

### Sage

ACP 和 A2A 不竞争：ACP 是本地 editor/agent 控制协议，A2A 是 agent-to-agent federation。
先解决当前最痛的权限与会话控制，再做 A2A 1.0 conformance；比同时接两套协议更小、
更可证伪。

### Keeper

新能力必须以减法结束。切换完成后，Codex registry 只保留 `acp_stdio` 自动生产
transport，删除 Codex `cli_prompt` 自动路径；dispatcher 不再隐式默认 `cli_prompt`；
Orca supervisor 降为人工 break-glass/观察入口。T1-18 的 wait/resume、collect、rollback、
independent verify 保护测试不得下降。

裁决：**接受 ACP stdio replacement BET；A2A 后置；禁止双生产面和自动 fallback。**

## 3. 真相与状态边界

ACP 只提交 transport facts：

```text
process_started
  -> initialized
  -> session_created_or_loaded
  -> prompt_accepted
  -> permission_requested
  -> permission_decided
  -> model_output_observed
  -> turn_completed | cancelled | timed_out | failed
```

这些状态不得直接映射 `WorkflowVerified`。只有从 git、声明命令和持久对象直接测量得到的
CompletionManifest，再经独立 VerificationReceipt `accept`，才能由 OMO 写
`WorkflowVerified`。

`initialize`、`session/new`、`session/prompt`、transport exit 0、ACP turn-end、模型自报 done
或文件存在，都不是完成证据。

## 4. 权限代理合同

权限代理根据受治理 WorkPacket、Task、active claim、verified independent clone 和规范化
argv/path 计算决定，不读取或修改用户级 allow-always 配置。

| 风险层 | 自动化策略 |
|---|---|
| R0 只读 | 在声明 capability 与路径内自动 `allow_once`，写脱敏决定回执 |
| R1 窄写 | 仅 verified clone、active claim、精确 write surface、无 symlink/gitlink 越界且 argv allowlist 命中时自动 `allow_once` |
| R1 越界/未知 | 自动拒绝；不提示用户替系统兜底 |
| R2 | 单次人工批准；不得转成永久授权 |
| R3/R4、外发、凭据、全局配置 | 拒绝或人工 break-glass；首轮不执行 |

每个 permission decision 至少绑定：packet id/hash、assignment、workflow/step/dispatch、
agent/session、operation、canonical scope digest、decision、policy digest、observed_at。禁止落盘
raw prompt、transcript、token、email、账号、绝对路径或环境变量原文。

## 5. ACP client 生命周期

首轮固定 `@zed-industries/codex-acp@0.16.0` 与 ACP v1 stdio，不做全局安装；依赖解析必须
可重放并记录 package/version/digest。client 必须：

1. `shell=False` 启动独立进程组；
2. 完成 initialize/capability negotiation；
3. 支持 session new/load、prompt、session update、permission request/response；
4. 对未知 method、版本或 capability fail closed；
5. cancel、EOF、timeout、协议错误时 TERM -> bounded wait -> KILL -> wait；
6. 不确认 child/session 清零时返回 `cleanup_unconfirmed`；
7. transport outcome 不确定时禁止自动启动 Orca successor。

## 6. 生产切换与减法

实施采用 shadow -> canary -> cutover：

1. fixture 只验证协议解析和失败注入；
2. 真实 Codex ACP shadow 在独立 clone 做一次非 marker R1 变更；
3. 一次越权 permission 被拒，tree 与 Mesh 不变；
4. 一次 cancel/timeout 证明进程与 session 回收；
5. 独立 verifier 通过后才允许 cutover；
6. cutover 同一提交删除 Codex `cli_prompt` 自动注册和 dispatcher 隐式默认；
7. Orca 只保留显式人工 break-glass，必须创建 successor assignment/dispatch，不能复用
   状态不确定的 ACP dispatch。

shadow 永久存在而旧路径继续自动生产不算完成。

## 7. 验收标准

1. 固定 ACP v1 stdio 与包身份；完整生命周期、错误、EOF、cancel、timeout、进程回收均有
   failure-injection 测试。
2. R0/R1 权限策略严格绑定 WorkPacket、clone、claim、canonical path 与 argv；R2+、未知和
   越权请求不自动批准；每次决定生成脱敏 receipt。
3. 真实 Codex ACP 非 marker canary 产生模型输出证据、实际 git delta、CompletionManifest；
   独立 verifier accept 后才出现 WorkflowVerified。
4. 越权 permission、协议篡改、scope drift、transport uncertainty、cancel/timeout 均无
   WorkflowVerified，且无双 dispatch/双 evidence。
5. cutover 后 Codex 自动生产 transport 仅 `acp_stdio`，dispatcher 不隐式选择
   `cli_prompt`，Orca 不在自动 fallback 路径。
6. T1-18 的 wait/resume、collect、rollback 和 independent verify 行为回归不下降；root/OMO
   定向测试、Ruff、diff check、agent-workflow verify、独立 review 与 PR checks 通过。
7. surface 报告必须列出新增与删除；若不能完成指名减法，BET 不得 done。

## 8. A2A 后续门

A2A 不属于本 BET。后续只做 A2A 1.0 HTTP+JSON shadow，并以官方 TCK MUST 级、标准
Agent Card、认证/owner scope、messageId 幂等、cooperative cancel 和两进程只读 canary
作为准入。当前 Agora 的自定义 MCP `a2a_*` 与内部 swarm envelope 不得被标记为 A2A 1.0。

## 9. Non-goals 与断路器

Non-goals：A2A live、Agora 改造、remote ACP/HTTP、第二 truth/DB/state machine、scheduler、
daemon、全局安装、用户级永久授权、自动模型/额度选择、自动 fallback、自动 merge、L2+
自动执行、真实业务外发、多租户、公网暴露。

出现以下任一条件立即停止并保留 T1-18：需要修改用户认证/全局配置；无法固定包身份；
必须使用 dangerous bypass；无法证明 cancel/reap/tree hash；live canary 只能靠 fixture；
需要第二任务真相；或三天内不能完成真实 canary 与指名减法。
