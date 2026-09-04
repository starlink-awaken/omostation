---
id: ADR-0325
title: 外部动态路由注册的统一准入闭环
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0319-external-resource-observation-surfaces.md
  - 0320-external-resource-evaluation-and-explainable-selection.md
---

# ADR-0325: 外部动态路由注册的统一准入闭环

## 背景

External Connection Fabric 已支持 `external.resources` 动态发现、目录观察、场景评估和
激活准入，但 Agora 的 BOSRouter 仍允许 `register()`、M1 热加载和 AGENTS.md 自动发现直接
写入路由表。这样会让一个未通过 admission 的 provider 进入可解析路由，形成“目录拒绝、路由
可见”的旁路；批量播种还会把被拒绝的条目计入成功数量，污染运营判断。

## 决策

1. BOSRouter 的每一次新路由注册都必须通过 `agora.admission.evaluate_admission`；重复的
   完全相同注册保持幂等，不重复调用 provider。
2. 准入请求只携带路由域、能力、适配器、来源及白名单上下文，不携带完整 config、凭据、
   原始数据或 provider 异常原文。未知 admission 元数据直接拒绝。
3. admission 非 `admitted`、provider 异常或结果形状非法时，路由不得进入 `_routes` 或
   Trie；BOSRouter 保留稳定、可解释的拒绝摘要供诊断读取。
4. `seed_from_poc`、M1 自动注册和 AGENTS.md 自动发现都以 `register()` 的布尔结果计数，
   不再把拒绝或重复注册虚报为新增路由。
5. `AGORA_ADMISSION_MODE=degraded` 只作为显式本地开发逃生舱；生产默认 `required`，
   缺少 provider 必须 fail-closed。该 ADR 不激活真实外部 provider，也不替代 SceneCard、
   ExternalConnectionCatalog 或 OMO Workflow admission。

## 验证

- 缺少 admission provider 时，默认路由注册被拒绝且路由表保持为空。
- 自定义拒绝、非法结果、provider 异常和不支持的 admission 元数据均不落表。
- POC seed 的新增计数只包含实际接受的路由；M1/AGENTS 自动注册复用同一写入门。
- Agora 外部连接、准入、代理、BOS 路由相关回归测试通过，目标文件 Ruff 检查通过。
