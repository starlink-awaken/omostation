---
title: External Connection Fabric Standard
status: active
type: standard
owner: architecture-governance
last-reviewed: 2026-08-02
related:
  - ../_truth/registry/external-connection-fabric.yaml
  - ../../ARCHITECTURE.md
  - ../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../_knowledge/decisions/0298-external-connection-fabric-runtime-boundary.md
---

# External Connection Fabric 标准

## 1. 目的

外部知识、数据、资料、资源、方法、理论、渠道和工具不再以散乱的临时接入方式进入系统。
所有连接先成为可描述、可发现、可评估、可准入、可撤销的资源，再由现有的 OMO、Agora、
Workflow Mesh、Kairon、AetherForge 和 Cockpit 协同消费。

本标准不新增顶层项目，也不拥有任务、权限、凭据、持久知识或运行状态真相。

## 2. Descriptor 合同

每个连接必须提供 `external-resource/v1` descriptor，至少包含身份、类型、提供方、协议、
能力、数据分级、来源、生命周期、健康、所有者、版本和 `permission_ref`。凭据只允许使用
引用，禁止落盘 token、密码、私钥或未经治理的私人原文。

资源类型统一为：`knowledge_source`、`data_source`、`resource_provider`、`method_pack`、
`tool_capability`、`channel`、`model_provider`。

## 3. 生命周期与准入

连接必须经过 `discovered -> sandbox -> admitted -> active`，运行中可进入 `degraded` 或
`quarantined`，最终进入 `retired`。激活前必须具备一张完整的 `Scene Card`，以及健康探针、
来源证据、审查时间和回滚方案。

`Scene Card` 至少包含 `scene_id`、`journey_id`、目标、触发、输入/结果契约、消费者、审批人、
责任人、失败代价、结果指标、数据分级/范围、操作人、`permission_ref`、回滚方案、三到十个
脱敏样本引用，以及重复需求证据或明确机会窗口。样本和需求证据只能是
`evidence://` 或 `vault://redacted/` 不透明引用，不能携带业务原文。

没有真实消费者、结果指标、责任人、权限边界或需求证据时，资源保持冻结，不得因为“已经能连通”
而激活。Agora 的 `SceneCard` 评估只做确定性门禁，不拥有业务事实；业务确认和证据持久化仍归
业务负责人及 OMO。

准入请求还必须携带与 descriptor 匹配的 `permission_ref`。`permission_ref` 是权限/凭据的
不透明引用，不是凭据本身；场景绑定不匹配时必须拒绝，不允许由 Agora 猜测或降级放行。

## 4.1 动态发现

Agora 通过 Python entry point group `external.resources` 发现提供方。提供方可以是类、实例或
映射，但必须返回 `external_descriptor()` 结果。单个提供方加载失败只生成错误记录，不能阻断
其他连接器发现；Agora 不得直接导入 Kairon、Iris 或某个具体供应商模块。

Iris 同时保留 `iris.connectors` 作为自身注册组，并将同一批 connector 暴露到
`external.resources`，因此新增外部连接只需要新增插件声明和 descriptor，不需要修改 Agora
路由代码。

动态扩展必须经过四步：发现 descriptor、隔离探活、重新评估场景准入、再进入路由候选。descriptor
变更不能静默覆盖活动连接，至少要记录 `id + provider + version` 的差异并重新检查权限、健康、
期限和回滚方案。单个插件探活失败只能隔离该候选并生成错误记录，不能污染其他连接或让旧的健康
快照继续伪装成实时可用。

发现结果先通过 `external-resource-catalog/v1` 只读投影进入人工目录。投影必须保留资源身份、类型、生命周期、健康探针摘要、来源引用、入口标识和可解释的 `reason_codes`；缺失探针时间、来源或有效期限时只能显示为 `stale/unavailable`。根仓入口为 `bin/ssot/external-resource-catalog.py`，默认只调用 provider 明确声明的只读 `health_probe`，不调用业务方法、不写 OMO；`--no-health-probe` 仅用于 descriptor 观察，不能把未探活的资源当作实时可用。Cockpit 入口为 `GET /api/external-resources` 和 `/external-resources`，这些入口均固定 `activation: forbidden`，也不把目录观察误判为业务激活。

目录命令支持调用方传入 `--previous-snapshot`，输出 `external-resource-catalog-diff/v1`，比较资源新增、移除、健康/生命周期变化以及 provider 错误恢复。上一份快照不由根命令隐式保存，避免在目录投影旁形成第二份状态真相；需要持久化的证据由 OMO 或后续受治理的观察任务承接。

### 4.1.1 受治理观察

当目录需要进入可审计的人机消费链时，根仓命令可以使用 `--observe` 将同一个安全目录通过
OMO CLI broker 记录为 `external-resource-observation/v1`。根仓脚本不得直接写入 `.omo`；
OMO 是观察日志和最新投影的唯一写入所有者：

- `omo external-resources observe --stdin` 校验目录 schema、`activation: forbidden` 和敏感字段禁入，
  然后追加到 `.omo/_log/external-resource-observations.jsonl`；
- `omo external-resources latest --json` 只读返回最新观察，最新快照损坏时可以从追加日志恢复；
- 观测以 `observed_at + catalog_digest` 去重，重复观测不得产生重复事实；
- Cockpit 默认先读 OMO 观察，没有观察或 OMO 不可用时才回退到动态目录，并明确标记
  `unobserved`/`observer_unavailable`；`view=dynamic` 只用于显式的实时查看；
- 观察仍然只是健康、来源、新鲜度和差异证据，不是 Scene Card 批准、OMO admission 或 WorkflowRun。

`--observe --no-health-probe` 保持只读发现语义：资源可以被记录，但未探活资源必须继续按
`stale/unavailable` 处理，不能因为进入观察日志就获得可用资格。

## 4. 触达模式

优先使用 `live_query` 和 `live_invoke`，仅在有边界时使用 `ttl_snapshot` 或
`governed_snapshot`。事件订阅和消息投递必须带最小化载荷、去重、免打扰、升级和投递回执。
方法和模型默认 `proposal_only`，必须经过评测、影子运行和人工批准才能产生生产副作用。

SourcePack 的动态刷新必须保留来源、时间、新鲜度、权限和用途标签；TTL 到期后只能标记
`degraded/unavailable`，不能继续按 live 结果使用。MethodPack、ModelPack 和 ChannelPack
必须分别留下离线评测、shadow、批准、canary 和 rollback 证据，路由或模型替换不能直接写入
admission 或 WorkflowRun 状态。

## 5. 路由与证据

Agora 根据相关性、可信度、新鲜度、权限、可用性、成本和延迟选择能力。任何选择都必须留下
候选决策因素、策略摘要和 `trace_id`。连接不可用、权限过期、来源过时或预算超限时，必须
返回显式 `unavailable/degraded`，不得使用默认值伪装成功。

每次发现、准入、调用、投递和退役都回写 `workflow-mesh/v1` 证据，至少包含资源身份、时间、
`receipt_id`、结果状态、策略摘要和来源引用。Agora 的 invocation receipt 只能包含摘要、
哈希和引用，不携带外部原文或凭据；它可以直接转换成 OMO `EvidenceRecorded` 的 payload。
外部结果只有在同一条证据链中完成 provenance 校验后，才能进入派生知识。

实际回写必须经过 OMO 的 `record_external_receipt()` broker，或其 CLI
`omo worker external-receipt`。broker 只把 `succeeded/degraded` receipt 提升为
`EvidenceRecorded`，使用 `workflow_run_id + receipt_id` 的稳定事件身份保证重试幂等，并把
`evidence_schema`、`resource_id`、`trace_id`、`result_state`、`observed_at`、`provenance_ref`、
`policy_digest` 和 `decision_factors` 投影到可查询证据。`failed`、`unavailable` 和
`proposal` 不得通过该入口伪装成成功；它们必须由 Workflow Mesh 的失败/不可用/提案事件表达。
receipt 文件和事件投影都禁止 provider 原文、模型输出、凭据和 secret 字段。

运行时入口为 `agora.external_connections.ExternalConnectionCatalog`：

- `register` / `discover_entry_points`：登记或发现 credential-free descriptor。
- `activate` / `activate_with_scene_card`：先执行 `Scene Card` 门禁，再执行场景绑定、权限、健康、
  期限和回滚检查，并推进 sandbox → admitted → active；旧 `SceneBinding` 仅保留给兼容路由，不能
  替代新连接的完整业务激活契约。
- `route`：按能力和决策因子选择资源；无候选时只返回显式 `unavailable`。
- `invoke`：返回受控 receipt；`proposal_only` 不执行副作用。
- `record_external_receipt`：由执行方在调用结束后把最小 receipt 回写 OMO；连接器本身不得直接
  改 WorkflowRun 或知识存储。

连接器开发者只需实现 descriptor、健康探针和受控调用适配器；不得把连接器注册、权限判定、
WorkflowRun 状态迁移或知识持久化塞回适配器。这样外部知识、方法、工具、模型和渠道可以动态
扩展，但能力边界仍收敛在 ECOS 合同、OMO 准入、Agora 路由和 Workflow Mesh 回执四个位置。

## 6. 受控进化

连接优化、方法改写、路由调整和模型切换只能生成提案。提案按
`proposal -> shadow -> approval -> canary -> rollback` 推进，并且必须能比较结果质量、成本、
延迟、权限失败率和人工接管率。

每轮扩展至少要有一个真实场景、一个可量化结果指标和一个可回滚版本；没有重复需求或真实消费方
时，保持 `sandbox`/`proposal_only`，不提前建设生产级连接器。

验证命令：

```bash
uv run --with pyyaml --with pytest python -m pytest -q tests/test_external_connection_fabric_registry.py
```
