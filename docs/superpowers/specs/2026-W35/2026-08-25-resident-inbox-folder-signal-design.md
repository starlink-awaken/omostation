---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-25
last_updated: 2026-08-25
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-15
type: ssot
last_updated: 2026-09-03
---

# Resident 多信号源扩流：感知文件夹 (inbox_folder) 接入事件流

> 日期：2026-08-25
> 状态：accepted
> BET：BET-Y1Q3-T10-15
> 上游：resident 体系价值兑现优化轮（T6-14 复盘「接线完整、价值未兑现」后四项之一）
> 方向：Task #51 多信号源扩流（用户选定「A 多信号源扩流」）

## 背景与问题

resident 常驻体系统一事件流 `.omo/_knowledge/workflow-mesh/events.jsonl` 已累计 2251 条，
但 idle 长达 1588s——事件源只有 `personal_signals`（2 条 PersonalSignal）+ workflow 低频突发
（733 WorkflowRequested 等）。`signal-sources.yaml` 已注册 5 个信号源，但只有 `personal_signals`
接入了 resident 事件流：

- `apple_mail_inbox` / `netease_mailmaster_inbox`：邮箱目录权限 + 解析复杂，暂缓
- `github_push`：webhook，后续轮
- **`inbox_folder`**：`~/Documents/@感知信号` 有 4 个真实 md 文件（email/insight/meeting/research）
  从未接入事件流 —— **本次补齐的缺口**

## 目标

新增 `InboxSignal` 事件类型，复用 `personal_signals` 的成熟 adapter 模式
（`omo.resident.signals`：poll → bus 发布 + 追加统一事件流 → daemon 按 routes 规则消费 →
sediment 沉淀知识草稿），把感知文件夹接入事件流：

1. **新 adapter `omo.resident.inbox`**：轮询 `~/Documents/@感知信号/*.md`，content-digest 幂等水位
   （复用 `_file_digest` 模式），发布 `mesh:perception:inbox` bus 事件 + 追加 `InboxSignal` 事件
   到 events.jsonl（producer=`perception-inbox`）。
2. **sediment 扩展**：`INBOX_EVENTS = {InboxSignal}` → `.omo/_knowledge/sediment/inbox/{slug}.md`
   感知信号草稿（与 signals/ 目录区分渠道语义）。
3. **全链接线**：`resident-routes.yaml` 加 InboxSignal 路由（→ knowledge_sediment, safe）；
   `roles.py` sediment 角色 topic_filter 加 InboxSignal；`ingest.py` topic 映射加
   InboxSignal→mesh:perception:inbox；`cli.py` SUBCOMMANDS 注册 inbox。
4. **调度**：`install-resident-cron.sh` 加每 5min `omo.cli resident inbox`（与 signals 并列）。

## 非目标

- 不接 apple_mail / netease_mailmaster / github_push（后续轮，本轮只扩 inbox_folder）
- 不改 `signal-poller.py`（感知健康通道与事件流通道并行，互不干扰）
- 不实现信号五问提炼（属下一里程碑「B sediment 五问提炼」）

## 验收

- [ ] `omo.resident.inbox.poll` 对感知文件夹扫描 → 发布 + 水位幂等（二次运行 0 新）
- [ ] `InboxSignal` 事件追加到 events.jsonl（producer=perception-inbox）
- [ ] `sediment.consume_event` 对 InboxSignal 写 `sediment/inbox/{slug}.md` 草稿
- [ ] 真实链路：`omo.cli resident inbox` 实跑 → `daemon --once --role sediment` →
      `sediment/inbox/` 出现 4 篇草稿（幂等，二次 run 0 新）
