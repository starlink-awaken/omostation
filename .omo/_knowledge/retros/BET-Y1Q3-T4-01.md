---
lifecycle: history
owner: auto-fix-loop
last_updated: 2026-08-24
title: BET-Y1Q3-T4-01 Retro — 真实个人价值证据脊柱与战略事实重基线
type: retro
---

# BET-Y1Q3-T4-01 Retro — 真实个人价值证据脊柱与战略事实重基线

- 状态: done (2026-08-21)
- 运行: 20260821T111433Z-bet-execution-967f03e6
- 目标: 把现有大量工程能力收敛成一条可证伪的个人价值主链

## 结果

12/12 AC 全部落地,核心证据:

1. **三轴分离代码强制 (AC-01)**: `compound-attribution-report.py` 的 `truth_axes` 三轴字段 + `overall = "unprovable" if "unprovable" in truth_axes.values()`; `north_star_meter_v2.py` 默认 unprovable,仅真实 receipt 才 proven。工程轴 observed 不推价值轴。

2. **Spec Binding fail-closed (AC-02/03)**: `blueprint_control.compile_packet` 校验 repo:// + semver + sha256 + accepted_specifications 匹配,start 前 fail-closed。

3. **Capability fail-closed (AC-05)**: `CapabilityCatalog.get` 精确 key + `resolve_with_capability` 生命周期拦截 + trie 最长前缀确定性,歧义不 first-match。

4. **NorthStar causal 派生 (AC-07)**: 只从带 principal/provenance 的 OutcomeFeedback 与 Human Adjudication 派生,拒绝 self-assert。

5. **真实价值样本 (AC-08)**: 真实低敏信号(跨仓耦合机制半删的观察)走通完整链:
   - SignalReceipt → episode(pending_confirmation) → confirm → execute(never-send draft)
   - 用户裁决 accept → RevisionReceipt + OutcomeFeedback
   - north_star: qualifying_outcomes 0→1, four_week gate not_ready→collecting, verdict_distribution {accept: 1}
   - ledger 无正文/绝对路径泄漏(evidence:// 引用,content_sha256 摘要)

6. **Codex transport (AC-06)**: T1-19 done 后 acp_stdio 为唯一默认 transport,cli_prompt 清零。

## 关键发现/教训

- **#1815 半删跨仓 bug**: 主仓删 instruction binding 但 ecos/omo/worker 仍要求,导致所有 BET start 失败。恢复主仓而非全链移除(全链移除是独立架构迁移)。教训: 跨仓耦合机制删除前必须盘点全部消费侧。
- **台账 status 落后于实现**: candidate 但 10/12 AC 已实质落地。检查 AC 落地状态不能只看台账。
- **真实样本是唯一推进价值的方式**: 工程事件(30+)不能推 personal_value,只有真实人类裁决(accept)才推进 qualifying_outcomes。

## 遗留

- 旧测试数据(principal:alice)含 file:// 绝对路径,是历史遗留,建议后续清理。
- 信号文件保留在 ~/personal-signals/ 作为真实样本。
