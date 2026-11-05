---
schema_version: specification/v1
spec_version: 1.0.0
title: AetherForge 与 Magpie 的 strict-local 请求契约
bet_id: BET-Y2Q4-T10-254
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-16
---

# AetherForge 与 Magpie 的 strict-local 请求契约

## 目标

让 Magpie 的 `local-only` 显式表达为 AetherForge 的服务端路由策略。请求体即使带有 `routing_mode=hybrid` 或 `cloud`，也不能把 strict-local 请求送入云端。保留 `local-first` 的现有本地优先与云端回退语义。

## 约束

- Magpie 插件中间件不是安全边界：其 hook 失败时请求会原样继续。strict-local 必须由 AetherForge 执行。
- 本地别名 `coding-local` 固定解析到现有 `coding` 本地目标；别名缺失、目标不可用或本地推理失败时明确失败，不回退到云端。
- strict-local 策略在复杂度评分、模型选择和 provider 调用之前确定；所有评分均留在本机。
- `local-first` 保持当前别名与 `group/cn-fast` 回退顺序，不改变现有使用该组的 Agent。
- 不改 LifeOS 核心/USER/MEMORY、凭据、其他 Magpie Agent 路由或用户模型数据。

## 验收条件

1. AetherForge 提供 `coding-local` 模型别名，并在当前本地模型目录包含其解析目标时从 `/v1/models` 暴露它。
2. 非流式、流式和 embedding 请求使用 `coding-local` 时，服务端强制 `routing_mode=local`；请求体的 `cloud`/`hybrid` 值不能覆盖该策略。
3. strict-local 成功时只调用本地执行器；本地容量、路由或推理失败时返回错误。测试断言云端 provider 调用次数为 0，并覆盖 AetherForge 支持的 OpenAI、Anthropic 与 Gemini 请求适配入口。
4. Magpie `local-only` 组只有 `aetherforge/coding-local`，没有云端成员或云端组回退；一次真实组请求成功且 AetherForge 侧记录为本地执行。
5. Magpie `local-first` 回读与变更前一致：`aetherforge/coding`、`aetherforge/reasoning`、`aetherforge/long-context` 先行，`group/cn-fast` 保持回退；OpenCode、Pi、OmO 的现有分配不变。
6. 代码窄测与 Ruff 通过；部署回执记录服务版本、路由回读、请求结果和回滚命令，不保存 prompt、密钥或令牌。

## 验证与回滚

- 用单测模拟 cloud/hybrid 覆盖、local capacity 失败和本地推理失败；任何分支触发 cloud 都必须失败。
- 运行 Magpie 只读组回读后再应用单个组成员变更，并立即回读确认。回滚命令将 `local-only` 的成员恢复为 `aetherforge/coding`。
- AetherForge 部署前保存当前可执行版本与服务配置。部署后通过现有服务入口验证 `/v1/models` 和一次无敏感内容的 strict-local 请求；失败则恢复原版本并重启原服务。
- 不提交、不推送、不对外发布。

## 范围

- AetherForge: aliases、Gateway 的 chat/stream/embed 路由、OpenAI 兼容模型目录和相关测试。
- 本机 Magpie: 仅 `local-only` 路由组及其验证/回滚回执。
- 不新增 daemon、second router 或第二个物理放置 owner；本地模型放置仍由 omlxc 负责。
