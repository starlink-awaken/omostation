---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-08 复盘：个人 Episode 与本地草稿黄金切片
type: retro
---
# BET-Y1Q2-T1-08 复盘：个人 Episode 与本地草稿黄金切片

> 日期：2026-08-12  
> 范围：W2-05，可信本地单用户阶段  
> 结论：第一条真实个人价值链已闭合；生产级并发、动态配置与故障对账仍属后续债务。

## 1. 交付结果

本轮把此前彼此独立的 W2-01 至 W2-04 资产串成一条真实可运行链路：

1. Cockpit `POST /api/workflow-mesh/personal-episode/start` 校验 active RoleAssignment 与 Responsibility，并在 Event Ledger 创建 `Episode.Decision.v1`。
2. W2-04 `GET /api/workflow-mesh/episode-projections` 立即在同一 principal 的 Inbox 中显示该卡片。
3. 明确人工确认后，OMO 授予仅限 `bos://personal/followup/draft` 的 A2/R0、单次预算、可撤销 Mandate。
4. Cockpit 从新请求实例重放 `_omo_policy`，调用真实 Agora `enforce/complete`，生成服务端命名的本地 JSON 草稿；草稿固定 `never_send=true`，不接受调用方路径，也不调用外部系统。
5. PolicyDecision、ActionReceipt、Evidence 与人工 Outcome 写入同一 Ledger/episode；投影可重放完整成员链并验证 hash chain。

子仓持久化证据：

- OMO：`89d87f7b756524509d17c16d9eb4991df7a76da5`，tag `bet/BET-Y1Q2-T1-08-omo-20260812`
- Cockpit：`a70dea8c984c466fae5a7678837b14222cfa7d39`，tag `bet/BET-Y1Q2-T1-08-cockpit-20260812`
- Agora：零源码变更，复用 W2-03 的真实 PEP。

## 2. 验证证据

- 根锚点 `projects/omo`：108 项角色、Mandate、PDP、Episode 与个人切片回归通过，Ruff 通过。
- 根锚点 `projects/cockpit`：25 项 API、Episode projection 与 Workflow Mesh 回归通过，Ruff 通过。
- 无 mock 黄金链测试真实使用 FastAPI TestClient、SQLite LedgerBroker、SovereigntyService、MandateManager、Agora PEP 和 OMO AgoraPepProvider。
- 端到端断言包括：Inbox 可见、A2/R0 confirm、Action started/succeeded、服务端 JSON 文件、Evidence、Outcome、投影只读与 ledger hash chain。
- 两轮独立只读审查均为 `APPROVE/WATCH`，无 CRITICAL/HIGH。

## 3. 范围降级决策

短期只有单用户可信本地使用，因此保留三条硬底线：人工确认、真实 PEP、全过程可追溯；暂不让以下问题阻断价值交付：

- 多租户、跨组织、鉴权后台；
- 恶意同进程绕过；
- 并发 exactly-once 与重复执行隔离；
- 进程崩溃后的自动 reconcile；
- 运行中动态切换 PEP provider。

该降级不是删除目标，而是把生产级强化后移到真实使用证据出现之后。

## 4. 已接受的 WATCH 风险

1. 同一 `request_id` 携带不同内容时，当前返回既有 Episode，不做冲突判定；可信单用户阶段接受。
2. PEP provider 绑定按启动期稳定配置设计；进程运行中显式修改环境变量可能继续使用旧缓存。
3. terminal receipt 已成功而 Evidence append 随后失败时，会保留本地草稿并返回 blocked，形成待 reconcile 的不完整链；本轮不伪装成功，但尚无自动补偿器。
4. 重复 execute 的 exactly-once 与 terminal-confirm 故障注入未纳入本轮硬门。
5. FastAPI TestClient 存在上游 deprecation warning，不影响当前行为。

## 5. 多 Agent / Orca 复盘

有效做法：

- 先由只读 Agent 审核蓝图边界和现有调用链，再把写面切为 OMO 两文件与 Cockpit 两文件。
- 执行者只写，独立 Reviewer 只读；主控只在审查后提交、打 tag、推送并同步根指针。
- 每个子仓先完成 D0 `commit + remote branch + tag`，再更新根 gitlink，避免产物从共享工作树消失。

暴露的问题：

- OpenCode `worker-start` 只把提示写入 TUI，未可靠提交执行能力；`worker_done` 还会因缺 dispatch capability 被拒。
- 两个 OpenCode 执行器在 Orca task id 与 PASW 路径上反复探测，长时间保持零文件变更。
- Claude 执行器出现长时间缓冲/无落盘。
- 主控采用“60 秒内必须出现可验证工件”的熔断：空转则精确停止该 dispatch，保留 worktree，再把窄任务转给可靠实现代理。

后续应把该熔断固化为编排策略：

- `worker-start` 后检查真实 capability receipt，而非只看 `input accepted`；
- 观察窗口内同时检查终端活动与 write-surface diff；
- 连续两个观察窗口无工件时自动 `worker-stop` 并重派；
- 外部便宜模型优先承担只读盘点、测试生成和窄模式化修改，跨仓垂直切片交给更稳定执行器；
- 所有重派保留原 task、dispatch、停止原因与最终验收证据。

## 6. 下一步

不要继续堆治理或投影。下一波应把手工 start 扩展为一个真实个人信号入口，并连续 dogfood：

- 从一个可重放、低风险信号源生成候选 Episode；
- 仍由人工确认，只生成本地草稿；
- 连续两周记录每周真实裁决数、处理耗时与节省时间；
- 只有真实价值证据达到阈值，才处理 exactly-once、reconcile 与更高自治等级。
