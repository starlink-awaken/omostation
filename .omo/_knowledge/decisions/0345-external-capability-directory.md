---
id: ADR-0345
title: External Capability Directory 只读能力地图
status: ACCEPTED
date: 2026-08-03
owner: architecture-governance
last-reviewed: 2026-08-03
lifecycle: spec
scope: Workflow Mesh external connection fabric
type: ssot
---

# ADR-0345: External Capability Directory 只读能力地图

## 背景

External Connection Fabric 已经能够发现资源、探活、记录观察、预检扩展包和校验场景，但原始
`external-resource-catalog/v1` 主要是资源清单。产品和运营仍需要一个稳定的能力视图来判断：
当前有哪些能力、哪些候选可用、哪些因为健康/权限/提案状态不可用，以及下一步该怎样推进。

## 决策

新增 `external-resource-directory/v1` 作为 catalog 的确定性只读投影，由根仓
`build_external_resource_directory_snapshot()` 构建，CLI 入口为：

```text
bin/ssot/external-resource-catalog.py --directory
```

directory 包含：

- `capability_index`：能力到资源候选和可用资源的索引；
- `kind_index`：知识、数据、方法、工具、渠道、模型等资源类型索引；
- `next_steps`：基于当前 availability/lifecycle/health 的确定性治理动作提示；
- catalog/directory digest 与安全摘要，便于重放和变化评审。

## 边界

1. directory 的来源真相仍是 catalog，不持久化第二份资源状态。
2. directory 固定 `activation=forbidden`、`provider_invocation=false`、
   `workflow_run_creation=false`、`admission_mutation=false`。
3. `next_step` 只是产品队列提示，不是生命周期迁移、路由决策或准入批准。
4. `--directory` 不得与 `--observe` 合并；需要持久化时由 OMO 记录 catalog observation，
   后续由受治理消费者重建 directory。
5. 没有真实业务场景时，能力只停留在目录、评测或 proposal-only；不得把能力地图当成业务消费证据。

## 影响

Agora 继续拥有发现和路由，OMO 继续拥有观察/证据持久化，Workflow Mesh 继续拥有执行与回执，
Cockpit 可以在不新增状态写入口的前提下消费能力地图。未来新增知识源、数据源、方法包、工具、渠道
或模型提供方只需进入现有 descriptor/pack/catalog 链，不需要为每一类资源再造导航和生命周期。

## 验证

- `tests/test_external_resource_catalog.py` 覆盖 capability/kind 索引、可用性汇总和 next step；
- `tests/test_external_connection_fabric_registry.py` 覆盖 directory registry contract；
- 根仓 capability directory 保持纯函数和无外部副作用。
