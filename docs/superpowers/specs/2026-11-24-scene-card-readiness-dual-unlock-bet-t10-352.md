---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-24
accepted: "2026-11-24 Principal 会话原话「go, 授权, 批」— proposal-lock (a) 路线 + 8 张卡逐卡批准"
bet_id: BET-Y2Q4-T10-352
spec_version: 1.0.0
---

# 场景卡就绪度双解锁 — proposal-lock 二选一语义 + 8 张卡 owner 审批落地

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-352`

## 背景与问题（实测）

scene-card 总检 ready=7/70。两个主卡点：

1. **proposal-only 红线自相矛盾**（`bin/ssot/internal-scene-preflight.py:213-216`）：
   要求 `activation ∈ {None, forbidden}` 与 `lifecycle ∈ {None, proposal_only}`，但
   两个值不在 standards 枚举（lifecycle 合法值 draft/shadow/assisted/supervised/
   routine；activation 合法值 preview/controlled/active）——显式写了合法值的卡必
   违反。源码注释 195-212 行已标注 owner 待裁，两路：(a) 补枚举+锁改二选一；
   (b) 卡回 locked。
2. **8 张卡 approval 待批**（trial 已过、唯一卡点）：admin-inbox / admin-submit /
   agora-bos-gateway / health-archive / health-intake / health-visit-prep /
   health-visit / knowledge-curation。

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | (a) vs (b) | **(a) 补枚举+二选一锁** | (b) 违反生命周期单向升级（CLAUDE.md B.0.5：draft→…→routine 只升不降）；53 张 supervised 是既成事实，回退破坏面大 |
| 2 | 豁免通道形态 | 单字段 `proposal_lock_exemption: <理由>` | 源码注释 (a) 原文"要么 locked，要么显式记录豁免"；单字段最简、可审计 |
| 3 | 8 张审批 | confirmed | Principal 2026-11-24 会话逐名批准（原话「go, 授权, 批」）；trial 皆已过 |

## 修复方案

1. `.omo/standards/scene-card-lifecycle.yaml`：lifecycle 补 `proposal_only`
   （内部轨提案锁，order -1 不参与升级链，can_execute: false）；activation 补
   `forbidden`（提案锁配对值）。
2. `bin/ssot/internal-scene-preflight.py`：两把锁各加豁免分支——卡有非空
   `proposal_lock_exemption` 时不报 missing（显式豁免）；无豁免照报（红线保留）。
3. 8 张卡：6 张补 `approval_state: confirmed`（原无字段）；agora-bos-gateway
   `approved → confirmed`；knowledge-curation `pending_business_confirmation →
   confirmed`。
4. `tests/test_scene_preflight_lock_semantics.py`（新）：豁免路径放行 / 无豁免仍报锁 /
   standards 枚举含两新值。

## 验收标准

- `pytest tests/test_scene_preflight_lock_semantics.py` 全过。
- `make scene-card-check`：ready ≥ 13（7 + 8）。
- standards YAML 可解析且含 proposal_only / forbidden。

## 反指标

- ready 数不得因"放宽检查"上涨——本 BET 的上涨全部来自 owner 显式审批与枚举
  正式化，豁免通道必须逐卡显式理由。

## 回滚

`git revert` 三类文件；无状态迁移。
