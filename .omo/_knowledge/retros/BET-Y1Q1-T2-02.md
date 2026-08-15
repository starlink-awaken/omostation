---
title: BET-Y1Q1-T2-02 复盘
status: active
owner: governance-team
created: 2026-08-15
lifecycle: history
last-reviewed: 2026-08-15
---

# BET-Y1Q1-T2-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
1 week appetite，本次会话完成 connector 验证 + signal-sources.yaml 更新 + retro 补录，未超 appetite。

## Q2 done_when 是否全部通过？哪条没过，为什么？
- ✅ CDP 9222 可达且 operator grant 完成 — **本条不适用于 Apple Mail**。根据 ECCP-HANDOFF.md，Apple Mail 走本地文件系统，无需 CDP 9222；CDP 9222 是 seeyon_oa 的依赖。台账此处存在 copy-paste 误差，已打假。
- ⚠️ 连续 7 天每天有去重后 signal 落盘 — 单次会话无法覆盖 7 天运行周期，需后续 cron/launchd 持续轮询验证。当前已验证单次 poll + iris connector 可用。
- ⚠️ 断连时 health 变 unreachable 且 BRIEF 可见 — 未验证。需构造断连场景（如临时移走 Mail/V10）并观察 health 传播。

## Q3 过程中发现的与 plan 不符的事实（打假）
- Apple Mail 数据源实际可用（ECCP P3 已收编 iris connector），无需额外 CDP/grant。
- signal-poller.py 当前只做目录 mtime 哈希，不直接调用 iris connector；真实轮询打通需在 poller 或 schedule 层做 iris 集成。
- 4 条 last_signal_at 已存在于 signal-sources.yaml（T2-01 遗留），本次更新为 apple_mail_inbox 填入了实际时间戳。
- iris apple_mail connector 通过 `mesh-iris-executor.py --connector apple_mail --dry-run` 验证返回 5 items，证明连接器可用。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
待执行：`uv run --with pyyaml python bin/plan/bet-ledger.py surface`

## Q5 下一个认领本 track 的 agent 需要知道什么？
- iris apple_mail connector 已可用（list_items/search/status），可直接通过 `iris sync apple_mail` 或 `mesh-iris-executor.py --connector apple_mail` 调用。
- signal-sources.yaml 中 apple_mail_inbox 已标记 healthy + last_signal_at，但 poller 与 iris 的集成尚未完成。
- 如需完整轮询闭环，下一步是修改 signal-poller.py 或新增 schedule 脚本，将 iris connector 的 list_items 结果写入 signal-sources.yaml 约定的 trigger 格式。
- CDP 9222 是 seeyon_oa 的依赖，不是 Apple Mail 的，后续 bet 若涉及 seeyon_oa 才需关注。

---

## 状态纠正记录（2026-08-15，台账信任修复 r2，spotcheck 抽样发现）

**status: done → in_progress，done_at 已清除。** 纠正依据（可复核）：

1. done_when 第 2 条「**连续 7 天**每天有去重后 signal 落盘」从未满足——本 retro Q2 自记 ⚠️「单次会话无法覆盖 7 天运行周期」；实测 `signal-sources.yaml` 最后真实 `last_signal_at=2026-08-07T23:45:22Z`（其余源 null），窗口 **0/7**。第 3 条（断连场景 health 传播）亦未验证。
2. 原 done_evidence（保留历史）: 'PR #1142 merged: verified iris apple_mail connector via mesh-iris-executor (5 items)…CDP 9222 is seeyon_oa dependency, not applicable to Apple Mail'。
3. **真缺口留给下个 agent**：launchd `com.omostation.signal-poller`（PID 活）在跑但信号不落盘——「每天有信号」需先修 poller 落盘，再从首个成功落盘日起算 7 天。
4. 处置授权：人类 2026-08-15「按照最优解来，你来判断」（spotcheck §6 建议 1，T3-01 同款处理）。
