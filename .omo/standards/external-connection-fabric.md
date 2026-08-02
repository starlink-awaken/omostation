---
title: External Connection Fabric Standard
status: active
type: standard
owner: architecture-governance
last-reviewed: 2026-08-03
related:
  - ../_truth/registry/external-connection-fabric.yaml
  - ../../ARCHITECTURE.md
  - ../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../_knowledge/decisions/0298-external-connection-fabric-runtime-boundary.md
  - ../_knowledge/decisions/0320-external-resource-evaluation-and-explainable-selection.md
  - ../_knowledge/decisions/0321-external-resource-selection-evaluation-evidence.md
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
引用，禁止落盘 token、密码、私钥、API key、DSN、Cookie、Authorization、未经治理的私人
原文和结果载荷。禁止字段检查必须递归覆盖 descriptor 的 `provenance`、`health` 和
`metadata`；`permission_ref` 仍只能是不透明引用，字段名本身不能成为凭据载体。

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

### 4.1.2 外部扩展包一致性预检

第三方连接器、未来的 SourcePack/MethodPack/ToolPack/ModelPack/ChannelPack 先以
`external-resource-pack/v1` manifest 进入静态预检。根仓入口为
`bin/ssot/external-resource-pack.py`，它只读取 manifest，不安装依赖、不加载 entry point、不调用
provider 或 `health_probe`、不写 OMO，也不产生 activation/admission。

pack 至少声明 `pack_id`、`pack_version`、`extension` 和一个 `external-resource/v1` descriptor。
`extension` 必须固定使用 `external.resources`、`external_descriptor` 和声明为
`read_only` 的必需 `health_probe`。descriptor 必须处于 `discovered` 或 `sandbox`，具备不透明的
`permission_ref`、`rollback_plan`、有效的 capability/kind 组合，且递归禁止凭据、token、原文和
结果载荷。pack 自己不能将 `activation` 声明为允许。

预检输出 `external-resource-pack-check/v1`，状态只有三种：

- `blocked`：合同、权限、能力、生命周期或敏感字段不满足，不能进入目录。
- `proposal_only`：descriptor 合同完整，但方法、模型或显式 `proposal_only` 能力只能进入提案/评测。
- `ready_for_catalog_preview`：可以进入下一步只读 catalog discovery，但仍不代表探活、准入、激活或可调用。

pack 预检只负责“扩展是否可被安全观察”，目录负责“当前 provider 是否可被发现和探活”，Scene Card/OMO
负责“是否有业务场景和权限可以准入”，Agora/Workflow Mesh 负责“如何路由、执行和回写 receipt”。任何
扩展包都必须按这四层逐级推进，不能用 manifest 合规结果绕过业务准入。

### 4.1.3 外部扩展包目录预览

当预检状态为 `proposal_only` 或 `ready_for_catalog_preview` 时，checker 可以附带
`external-resource-pack-catalog-preview/v1`。这是从已校验 descriptor 提取的安全投影，不是
`external-resource-catalog/v1` 的观测结果：`availability` 和 `health.status` 必须固定为
`unobserved`，来源固定为 manifest，且不得包含 provider 响应、原文、凭据或结果载荷。

目录预览只回答“人可以先看到什么”和“下一步应进入哪一层”：普通资源进入只读 catalog discovery
和健康探针，方法/模型或显式 proposal-only 资源进入 proposal/evaluation。Cockpit 可以展示该预览，
但不得把它当作可用、已探活、已准入或可调用资源；仍需沿用 catalog、Scene Card、OMO admission 和
Workflow Mesh receipt 链。

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
- `invoke` 对 provider 异常只输出稳定的 `EXTERNAL_*` 错误码：超时为
  `EXTERNAL_TIMEOUT`，连接不可用为 `EXTERNAL_BACKEND_UNAVAILABLE`，权限拒绝为
  `EXTERNAL_PERMISSION_DENIED`，响应不合法为 `EXTERNAL_INVALID_RESPONSE`，其余为
  `EXTERNAL_PROVIDER_FAILURE`。异常类型、消息和堆栈只能留在调用方受控日志，不能进入
  receipt、OMO 事件或 Cockpit 投影；`no_route` 和 `invoker_unavailable` 仍表示连接层的
  确定性前置失败。
- `record_external_receipt`：由执行方在调用结束后把最小 receipt 回写 OMO；连接器本身不得直接
  改 WorkflowRun 或知识存储。

### 5.1 场景化资源评估

资源目录在进入正式准入前，可以通过 `external-resource-evaluation/v1` 生成一次可重放的只读评估。
评估输入是 `capability`、完整 `SceneBinding`、`trace_id`、目录快照和可选的健康观察；输出必须包含：

- 全部目录候选，而不只是最终选择；
- 每个候选的 `status`、稳定 `reason_codes`、`decision_factors` 和排序值；
- `policy_digest`、`trace_id`、场景绑定摘要和汇总计数；
- `activation: forbidden`、`mode: read_only_evaluation`，以及无 provider 调用、无 OMO 状态写入的声明。

Agora 的 `evaluate_candidates()` 是唯一决策算法，已有 `route()` 只能复用该结果，不得维护第二套
评分逻辑。根仓通过 `evaluate_external_resources()` 暴露快照评估，Cockpit 通过
`POST /api/external-resources/evaluate` 提供人机消费入口。评估结果不是 admission、不是 WorkflowRun、
不是业务成功标签，也不能替代真实 receipt；只有经过 Scene Card、人工批准和 OMO admission 后，才可
进入实际调用链。

评估因子只允许使用安全元数据：能力匹配、权限、信任、新鲜度、健康、成本、延迟和资源身份。原文、
凭据、provider 响应和模型输出不得进入评估结果。真实质量标签、人工判定、调用回执和结果指标应在
后续评测集/证据闭环中另行采集，不能从评估排名反推。

### 5.1.1 选择评测证据

评估结果需要进入长期评测时，必须由 OMO 的 `record_external_resource_evaluation()` 写入
`external-resource-evaluation-observation/v1` 追加日志。该观察是安全的选择事实，不是
`EvidenceRecorded`、admission 或 WorkflowRun 状态；默认 API 行为仍为只读，只有显式
`persist_observation=true` 才记录。观察 broker 使用 `evaluation_id`/评估摘要去重，冲突时拒绝，
并递归禁止原文、凭据、模型输出和 provider 响应。

OMO 的 `build_external_resource_selection_dataset()` 只读 join 三类真相：评估观察、Workflow Mesh
事件/receipt 和 `outcome-feedback/v1`。显式 `workflow_run_id` 优先，缺失时只允许唯一 `trace_id`
匹配；未绑定或歧义样本保留为 `not_executed`/未归因，不能成为成功样本。执行成功必须来自 Mesh
成功事件，资源对齐必须来自真实 external receipt，结果消费必须来自显式反馈；关闭、验证或证据存在
本身不能推断业务价值。

Cockpit 提供评测集只读查询和 proposal-only 策略比较。提案只输出离线指标和人工审批要求，不修改
路由、准入、WorkflowRun 或连接器状态。没有真实 Scene Card、连续使用和结果指标时，评测链保持
shadow/proposal-only，不推进 provider 激活。

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
uv run --with pyyaml --with pytest python -m pytest -q tests/test_external_resource_pack.py
```
