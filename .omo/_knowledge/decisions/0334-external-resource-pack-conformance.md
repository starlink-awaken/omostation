---
id: ADR-0334
title: External Resource Pack Conformance Before Dynamic Discovery
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/external-connection-fabric.md
  - 0333-scene-card-preflight-readiness.md
---

# ADR-0334: External Resource Pack Conformance Before Dynamic Discovery

## Context

External Connection Fabric 已经具备 descriptor、动态目录、健康探针、Scene Card 和 OMO admission
边界，但“第三方连接器如何被安全地引入”仍缺一个与运行时发现隔离的入口。若直接加载新的 entry point，
扩展包可能在尚未完成权限、回滚、能力边界和敏感字段检查前触发导入或 provider 副作用。

## Decision

增加根仓静态工具 `bin/ssot/external-resource-pack.py`，以
`external-resource-pack/v1` manifest 为输入，输出 `external-resource-pack-check/v1`。
工具复用 Agora 的 credential-free descriptor 解析，并从 External Connection Fabric registry
读取 kind/capability 合同。

预检固定执行以下规则：

1. 只读取 JSON/YAML manifest；不安装、不导入 entry point、不调用 provider 或健康探针、不写 OMO。
2. entry point 必须属于 `external.resources`，provider 方法必须是 `external_descriptor`，健康探针必须声明为必需且只读。
3. descriptor 必须使用 `external-resource/v1`，生命周期只能从 `discovered` 或 `sandbox` 开始，并具备权限引用、责任人、回滚方案和允许的 capability/kind 组合。
4. 对整个 manifest 递归禁止凭据、token、Cookie、Authorization、私有原文、样例数据和输入输出载荷。
5. 预检本身的 `activation` 永远是 `forbidden`，状态只表达 `blocked`、`proposal_only` 或 `ready_for_catalog_preview`。

## Boundary

pack 预检只证明“可以被安全观察”，不证明 provider 已被加载、健康、准入或可调用。后续仍按
`pack -> catalog discovery -> health observation -> Scene Card/preflight -> OMO admission ->
Agora route -> Workflow Mesh receipt` 推进。连接器不得在 pack 或 descriptor 中承载权限判定、WorkflowRun
迁移、知识持久化或 OMO 写入。

## Consequences

- 新连接器具备统一、可自动化的接入前门禁，未来扩展外部知识、数据、方法、工具、模型和渠道不需要修改 Agora 路由代码。
- 连接器作者可以在没有真实业务场景时完成静态契约验证，但不能借此提前激活生产能力。
- 预检和 catalog 之间仍有运行时健康差异；只有 catalog/OMO 观察和后续 Scene Card 才能提供动态可用性证据。
- 工具依赖 registry SSOT；资源 kind 或允许能力变化时，预检结果随治理注册表变化而变化。

## Verification

```bash
uv run --with pyyaml --with pytest python -m pytest -q tests/test_external_resource_pack.py
```
