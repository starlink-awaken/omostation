---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T2-01 复盘：本地真实信号进入个人 Episode
type: retro
---
# BET-Y1Q2-T2-01 复盘：本地真实信号进入个人 Episode

> 日期：2026-08-12
> 范围：W3-01A，可信本地单用户阶段
> 结论：E3 工程链路完成；尚未用真实个人条目证明 E4 用户价值或 W3 gate。

## 1. 交付结果

本轮没有再造 Inbox、账本或信号框架，而是把既有 Iris、OMO、Cockpit 与 Agora 串成一条窄链：

1. Cockpit 新增 `POST /api/workflow-mesh/personal-signal/ingest`，请求只接受 Iris opaque `item_id` 与 principal/role/responsibility/executor。
2. 服务端从 `PERSONAL_SIGNAL_DIR` 调用真实 `LocalFilesConnector`，复核 resolved path、regular `.md`、标题和目录边界，计算内容 SHA-256。
3. OMO 用 generated `EventEnvelope` 与 `Signal` 验证后，先写 private `SignalObserved.v1`，再写带 `causation_id/source_signal_ref` 的 private `Episode.Decision.v1`。
4. Ledger 不写 Markdown 正文或绝对源路径；仅保存标题、摘要哈希、安全 `iris://local-files/<item_id>` 引用和固定 scene/journey/outcome 锚点。
5. 同 source/item/digest 重放复用原 Signal/Episode；内容变化生成新因果对。即使后续角色/职责变化，也沿已持久化因果链返回原 Episode。
6. 新 Episode 继续复用 W2-05 的人工确认、A2/R0 Mandate、真实 Agora PEP、`never_send=true` 本地草稿与 Human Outcome。

子仓 D0 证据：

- OMO：`57d219c50a0ee64e0d73105bca9542acbdb37a41`，tag `bet/BET-Y1Q2-T2-01-omo-20260812`
- Cockpit：`9105de37e6ddae5365ead57b4c5c9eaced3d79bd`，tag `bet/BET-Y1Q2-T2-01-cockpit-20260812`
- Kairon、Agora、ECOS：零源码变更，分别复用 Iris LocalFilesConnector、W2-03 PEP 与既有 generated contracts。

## 2. 验证证据

- OMO：Ruff 与 diff check 通过；Personal Episode、Episode projection、policy enforcement 共 46 项测试通过。
- Cockpit：Ruff 与 diff check 通过；真实 Iris + SQLite Ledger + FastAPI TestClient 的 signal/personal-episode/projection 共 25 项测试通过。
- E2E 覆盖：item ingest → SignalObserved → Inbox Episode → confirm → 真实 PEP → never-send 本地草稿 → feedback。
- 负向覆盖：缺配置/缺 item、traversal、越界 symlink、非 Markdown、空标题、失效角色/职责、调用方注入 summary/content/path/source/digest/scene，均 fail closed 且 Ledger count/hash 不变。
- 两轮 OMO 审查修复了角色变化后的幂等缺口；最终独立跨仓审查结论为 `APPROVE/WATCH`，无 CRITICAL/HIGH。

## 3. 范围与价值口径

用户明确短期为可信本地单用户，优先效率。本轮保留人工确认、真实 PEP、隐私边界和 Ledger 可追溯四条硬线；并发 exactly-once、崩溃 reconcile、多租户、邮件/日历、多源 watcher 不阻断本次交付。

本轮测试条目是临时合成 Markdown，只证明 E3 工程能力。execute 的草稿字段目前仍由请求方提供，因此不得把该测试计入“系统生成有价值结果”的分子，也不得宣称 W3 或个人数字分身价值目标已通过。E4 必须由后续 observation 使用真实个人条目和人工 verdict 采样。

## 4. 已接受的 WATCH

1. Cockpit 当前为复用 Iris，在请求进程内设置 `IRIS_LOCAL_FILES_DIRECTORY`；单用户固定目录下不构成越权，但未来多实例/多目录应改显式 connector config。
2. Signal 与 Episode 是两个顺序 append；进程恰在中间崩溃时会留下无 Episode 的 Signal。本轮不做跨事件事务或 reconcile。
3. `LocalFilesConnector` 仍由 Cockpit 通过受管 Kairon source path 组合，不新增 Python package dependency；后续若独立部署 Cockpit，需要把 Iris 纳入正式 runtime packaging。
4. 文件读取失败对外统一映射为 `item_not_found`，能避免泄漏路径细节，但运维诊断仍需服务端结构化观测。

## 5. 编排复盘

本轮由 Orca Run `run_4ec48a706d36` 维护任务、依赖和回执：

- OMO task：`task_0bcef180119d`
- Cockpit task：`task_d0633ce5575b`

实际执行暴露出外部 Agent 适配器稳定性差异：OpenCode TUI 接收输入但没有产生工件；Claude 长时间只读推理；Orca 内 Codex 因隔离 HOME 缺 profile 启动失败；Kilo 在当前 Orca 未配置。主控按“有真实 diff 才算进展”熔断并保留审计，OMO 转为受控实现 Worker；Cockpit 最终由 CodeBuddy 使用 `bypassPermissions` 完成并通过 Orca `worker_done` 正式回执。

有效机制是：战略负责人冻结最小写面与验收标准，执行 Agent 只写，独立 Reviewer 只读，主控独立复跑测试后才负责 commit/tag/push 和根指针。后续应把“连续观察窗口无 diff 自动停止并换执行器”固化到 Orca 调度策略，而不是依赖人工盯 TUI。

## 6. 下一步

不要马上扩邮件、日历或自动发送。下一步只做真实 dogfood：由用户在允许目录投放一条真实但低敏、可撤销的个人跟进事项，经当前链路完成一次人工确认、草稿审阅和 accept/edit/reject/defer。随后以至少两周的真实裁决数、处理时长和采纳率决定是否进入第二信号源或更高自治。
