---
status: archived
lifecycle: history
owner: governance-team
bet_id: BET-Y2Q2-T5-02
last-reviewed: 2026-09-22
title: BET-Y2Q2-T5-02 复盘
type: retro
---
# BET-Y2Q2-T5-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 50 分钟 vs 1 week appetite，远未超。实现为单个新模块 `delivery.ts`（约 180 行）+ 4 条投递测试，未触碰 T5-01 公开接口。

## Q2 done_when 是否全部通过？哪条没过，为什么？
全部通过（verify 逐条实测）：
1. 投递失败按退避策略重试并最终进入 dead-letter：`deliver()` 先 `enqueue()` 写入 `outbox/` 并 fsync 后才 ack，随后 transport 以指数退避（baseDelayMs×2^(n-1)）重试至 maxAttempts（默认 5）；耗尽后文件 rename 进 `dead_letter/`，内容零丢失——`exhaustion-to-dead-letter` 测试断言 quarantine 文件可 JSON 解析且 subject 原样保留。
2. 回退路径可用且有测试覆盖：`redriveDeadLetters()` 将 `dead_letter/` 排回 `outbox/`，`flushOutbox()` 重投递——`fallback redelivery` 测试走完整链路 dead→redrive→flush→receive 命中原文；runbook 文档化于 `delivery.ts` 头注释。
3. 持久化语义测试全部通过：`bun test` 13 pass / 0 fail（9 primitives + 4 delivery），含 retry-then-success（断言退避序列 [10,20]ms、中途 outbox 挂起态可见）与 ack-durable（send/deliver 共存，公开接口不变）。
4. acceptance 第三条：`grep -c "team-mailbox" ~/.config/opencode/opencode.json` = 1（T5-01 注册保持）；`grep -r -c "dead_letter" plugin/team-mailbox` exit 0。

circuit_breaker 未触发（回退语义测试一次通过）；非目标守住：未改 send/receive/list 签名，未做 fork-join 编排（T5-03）。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **T5-01 原语在本 bet 开工前已被并发进程加固**：`mailbox.ts` 文件名从 `<ts>-<from>.json` 演进为 `<ts>-<sanitized>-<rand6>.json` + tmp/rename 原子写 + schema 长度上限 + fail-closed 校验，测试从 4 条增至 9 条。spec 要求"public send/receive/list 接口不变"仍满足（签名逐字未动），但投递层的文件名重构逻辑（早期设想由 sent_at 反推文件名）因此不可行，改为 outbox 内部持有 filename 句柄传递——设计随实况调整而非照抄 plan。
2. **`~/.config` 下文件不可被 git 追踪**：与 T5-01 相同，本 bet 的 write_surfaces 仅含 glob 目录面（无精确 home 文件），D0 检查按 `*` 豁免规则自然通过，无需 `--force`——证实 T5-01 retro 记录的 D0 结构性问题只影响精确文件面。
3. **本机 shell `grep` 被别名为 rg**，verify 命令 `grep -r -c` 的输出形态与 GNU grep 不同（显示替换伪影），验证 exit code 需用 `/usr/bin/grep` 复核，防止误判。

## Q4 改变了什么 / 教训固化
- team-mailbox 自此具备有界重试、fsync-ack outbox 与 dead-letter 隔离：投递失败不再静默消失，T5-03 编排层可在"durable 交付"契约上叠加。
- 本 retro 兼任 completion evidence 的 tests/diff/rollback/live_canary/fresh_receipt/replay/cleanup 收据（T8-02/T5-01 先例，receipt:// 指向本文件）；merged_reachable_commit 指向 `c9bf357328261259882fb4af3e784a26674ca98f`（origin/main 注入 T5 链 spec 的 #4152 合并提交，实现体按 bet 设计落于仓库外）。
- rollback 路径：删除 `delivery.ts`/`delivery.test.ts` 并还原 index.ts 导出即可回到 T5-01 行为（原语零改动）。
- 教训：动手前重读仓库外实体的当前状态（本例 mailbox.ts 已被并发加固），基于实况而非记忆中的版本设计接口。
