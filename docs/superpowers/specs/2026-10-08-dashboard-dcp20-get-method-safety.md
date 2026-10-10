---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: dashboard-convergence
bet_id: BET-Y2Q4-T10-236
spec_version: 1.0.0
title: DCP-20 P0 Zhixing GET 方法安全与受管宿主发布
accepted_at: 2026-10-08
implementation_authorized: true
decision_ref: decision://accepted/BET-Y2Q4-T10-236
value_indicator_policy: false
risk_level: L2
human_gate: true
---

# DCP-20 P0: Zhixing GET 方法安全与受管发布

## 目标

在 Cockpit、Zhixing 的任何主体会话或角色数据功能开放前，证明 Zhixing 的 GET 请求只读取数据。未经登记的 GET operation 必须拒绝；执行型 operation 不得通过通用查询分发进入业务逻辑。修复必须能通过版本化资产同步到 LaunchAgent 实际运行的代码根，并以部署摘要和运行探针证明生效。

## 已观察到的缺陷

当前 `bin/panorama/assets/host/live_server.py.asset` 的通用 `/api/v1/<operation>` GET 分支会把 operation 交给 `ObservationIndex.query()`。该查询实现包含写入或执行分支：`proposals/submit`、`proposals/adjudicate`、`health/auto-heal`、`health/execute-heal`、`bos/invoke`、`loops/step`。`copilot/ask` 也不是纯读取。投影模式对 POST 返回 405，不能约束这些 GET。Loopback、Origin、CORS 和 `read_only` 响应标记都不构成授权或副作用边界。本轮不得调用这些操作端点。

另一个发布缺陷是受管 Zhixing LaunchAgent 当前执行 `~/.local/share/zhixing-dashboard-runtime-clean-20261008/live_server.py`，而 `zhixing-host-sync.py` 只映射默认 `~/.local/share/zhixing-dashboard`。只改 Workspace 资产或默认部署目录，不能证明当前 PID 已获得修复。

## 设计约束

1. 将纯读取 GET operation 明确列入独立 allowlist；GET 分发只允许该集合。执行型、计算型、未知 operation 均 fail closed，不进入 `ObservationIndex.query()`。
2. `ObservationIndex` 查询层对执行型 operation 提供拒绝保护，避免未来路由误复用查询 API 后恢复副作用。
3. 保留 `/health`、`/api/snapshot`、静态页面、投影读取和有文档证明的只读 API。投影模式对所有 POST 继续拒绝。此 Spec 不引入 Principal session 或角色授权；该工作属于后续 DCP-21。
4. 添加 `zhixing-host-sync.py` 的精确目标目录与文件选择能力，只能把已版本化的指定资产发布到已登记 Zhixing 运行根；逐文件备份、原子替换、发布后 SHA 校验，失败即停止并恢复本次备份。不得顺带覆盖其他漂移文件。
5. 负测必须在临时 loopback server / 临时文件系统完成，逐 operation × method 验证拒绝并证明状态前后摘要一致；绝不对生产端点发起写方法或执行型查询。
6. 发布前通过受管同步流程核对当前 LaunchAgent 的实际代码根、配置摘要和资产 SHA；发布后验证运行 PID、`/health` 的代码身份以及 GET 负测对应的部署版本。若当前身份绑定/G0 门禁拒绝，不得改成手工覆盖。

## 写入面

- `bin/panorama/assets/host/live_server.py.asset`
- `bin/panorama/assets/host/observatory_query.py.asset`
- `bin/gac/zhixing-host-sync.py`
- `tests/test_zhixing_host_sync.py`
- 新增 Zhixing GET 方法安全单测及必要 fixture
- 本 Spec、BET Ledger 条目和对应 waiver evidence

## 完成判据

- 所有登记的纯读取 GET 返回合同规定的状态和 schema；六个执行型 operation 与 `copilot/ask` 的 GET 一律拒绝，且查询层拒绝执行型 operation。
- 未知 GET operation 默认拒绝；临时测试证明无磁盘写入、proposal/adjudication/loop 状态变化、BOS 调用或 subprocess 执行。
- 投影模式下全部 POST 仍被拒绝；health、snapshot 与静态页面回归通过。
- Host-sync 只能发布明确选择的资产到 LaunchAgent 实际代码根；测试证明其他文件不变、失败回滚、发布后 SHA 与 Workspace 资产一致。
- 独立复核方法×operation 清单、测试覆盖、写入面和发布回执。正式发布后，连续三轮 health 通过，浏览器实际加载 Cockpit，BFF 如实标示 provenance 缺口。

## 非目标

- DCP-21 Principal/Agent/业务人员认证、session、CSRF、资源 scope 与角色授权。
- Cockpit 其他 API 的全面认证迁移、Decision Graph 数据开放或业务功能验收。
- 完成白皮书全部价值闭环、改变 `127.0.0.1` 网络暴露、修改其他 LaunchAgent。
- 重发 Dashboard 投影、修改 BET/Run/Lock 之外的任何治理状态。

## 失败与回滚

任一纯读取 API 失效、任一负测观察到副作用、运行根不匹配、文件 SHA 不匹配、G0/身份绑定失败或既有服务在回滚后仍不可用时立即停止发布。回滚仅恢复本次发布前逐文件备份，重启只能通过登记的 Zhixing LaunchAgent 执行；不清理其他服务、锁或 Run。

## 授权边界

Principal 已授权在当前 Dashboard 白皮书 v2.1 范围内选择流程、解决现存阻塞并持续落地。本 BET 只覆盖上述 DCP-20 P0 的方法安全与精确宿主发布，不代表 DCP-21、M0/G0 绑定或完整产品验收已通过。
