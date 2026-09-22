---
status: completed
lifecycle: history
owner: governance-team
bet_id: BET-Y2Q2-T5-02
last-reviewed: 2026-09-22
title: BET-Y2Q2-T5-02 复盘
type: retro
---
# BET-Y2Q2-T5-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
实现体量约 320 行（delivery.ts ~180 行 + delivery.test.ts ~135 行），在 1 week appetite 内。主要耗时在证据链核对（ledger digest 比对、T5-01 先例对齐）而非编码本身。

## Q2 done_when 是否全部通过？哪条没过，为什么？
全部通过（verify 命令逐条实测，见下）：
1. `cd ~/.config/opencode/plugin/team-mailbox && bun test` exit 0 — 13 pass / 0 fail（bun 1.3.14，4 投递语义 + 9 收发原语）。
2. `grep -r -c "dead_letter" ~/.config/opencode/plugin/team-mailbox` exit 0 — `dead_letter` 出现于 delivery.ts（DEAD_LETTER_DIR 常量、隔离、redrive、list）与 delivery.test.ts（隔离断言、回退投递用例）。
3. `grep -c "team-mailbox" ~/.config/opencode/opencode.json` = 1 — T5-01 已注册，本 bet 不改插件入口。

done_when 三条逐条核验：
- 投递失败按退避策略重试并最终进入 dead-letter：`exhaustion-to-dead-letter` 用例 — transport 恒抛错，maxAttempts=3，第 3 次失败后消息以原子 rename 隔离进 `dead_letter/`（内容完整保留），outbox 清空，inbox 不可见。
- 回退路径可用且有测试覆盖：`fallback redelivery` 用例 — `redriveDeadLetters()` 将 dead_letter 倒回 outbox，`flushOutbox()` 重投成功，`receive()` 收到原消息。
- 持久化语义测试全部通过：`retry-then-success`（瞬时失败 2 次后第 3 次成功，退避序列 [base, 2base] 指数增长）、`ack is durable`（enqueue 在 handoff 前 fsync，崩溃后 outbox 文件可经 flushOutbox 恢复——at-least-once）。

circuit_breaker 未触发：回退语义测试一次通过。非目标守住：未做 fork-join 编排（T5-03）；未改 T5-01 公开接口（mailbox.ts / mailbox.test.ts 逐字节未动，9 个原语测试全绿）。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **实现体全部落在仓库外**：delivery.ts / delivery.test.ts 写在 `~/.config/opencode/plugin/team-mailbox/`（external write root，已在 `external-write-roots.yaml` 登记 `plugin/team-mailbox/*.ts`），仓库侧可追溯锚点仅为 spec 绑定提交 `c9bf35732`（与 T5-01 同构，ledger `merged_reachable_commit` 指向该提交）。
2. **DEFAULT_MAX_ATTEMPTS 由初版 5 调整为 3**：任务书明确 "max 3 attempts"，而设计文档（canonical spec）只写 "bounded retries" 未钉死数值；测试均显式传 maxAttempts，改默认值无回归。调整属对齐任务表述，非设计漂移。
3. **index.ts 无需注册新工具**：设计文档明确 "The public send/receive/list interface stays unchanged"，delivery 层函数（deliver/flushOutbox/listDeadLetters/redriveDeadLetters）经 re-export 暴露给插件消费者即满足；ledger verify 亦无新工具要求。

## Q4 改变了什么 / 教训固化
- 多 agent 协作在 T5-01 收发原语之上获得 durable 投递语义：outbox fsync 确认 → 指数退避重试（默认上限 3 次）→ dead_letter 隔离 → 运维 redrive 回退，全程 at-least-once，消息不丢失。
- 本 retro 同时充当 completion evidence 的 tests/diff/rollback/live_canary/fresh_receipt/replay/cleanup 收据（T8-02 先例，receipt:// 指向本文件）；merged_reachable_commit 指向 `c9bf357328261259882fb4af3e784a26674ca98f`（spec 绑定链锚点）。
- rollback 路径：删除 `~/.config/opencode/plugin/team-mailbox/delivery.ts` 与 `delivery.test.ts` 即可回退本 bet；T5-01 插件与 opencode.json 注册不受影响（依赖方向单向）。
- 教训 1：**at-least-once ≠ exactly-once** — redrive 与崩溃恢复都会重复投递，T5-03 编排层消费侧必须做幂等去重，不能把 redrive 当自动重投（毒消息会靠 redrive+flush 循环放大，redrive 是运维路径而非自动循环）。
- 教训 2：设计文档写 "bounded retries" 而任务书写 "max 3 attempts" 时，以任务书具体数值对齐默认值并在 retro 记录分歧，避免后续 verify 语义漂移。
