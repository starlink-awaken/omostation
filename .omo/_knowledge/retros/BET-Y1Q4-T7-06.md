---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T7-06
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-12
type: ephemeral
---

# BET-Y1Q4-T7-06 retro — 合同网协议 (CNP) 竞标与临时突击队编排

## What changed

- **`projects/omo/src/omo/resident/contract_net.py`**（新）：CNP 竞标状态机
  —— TaskAnnouncement/Bid/Award 数据契约; 资质门槛（skills 覆盖全部
  required_skills, 无资质拒绝）; 确定性评分
  `2.0·覆盖率 + 1.5·confidence + 1.0·(1−时长归一) − 0.5·token 归一`;
  Token 预算 500（circuit breaker: 累计超限强制截断）;
  超时兜底（窗口关闭/无合格者 → Archetype 兜底, 兜底率 100%）;
  `evaluate` 纯函数 + `ContractNetManager` 经理侧授标。
- **`projects/omo/src/omo/resident/taskforce.py`**（新）：TaskForce 临时
  突击队——leader = 中标者, members = 合格投标人按 confidence 择优
  （上限 5）; 创建（同任务活跃队唯一）/解散（幂等）/ttl 过期清扫。
- **测试** `projects/omo/tests/test_contract_net.py`：17 用例全绿。

## Done when 逐条

| 判据 | 结果 |
|------|------|
| contract_net.py 竞标状态机与评分算法 | ✅ 资质门槛 + 确定性评分 + 截断/超时兜底 |
| taskforce.py 临时突击队编排管理 | ✅ 组建/解散/清扫全生命周期（幂等断言） |
| 评估 ≤300ms / Token ≤500 / 3s 超时兜底率 100% | ✅ 100 投标者压力实测 0.11s（远低于 300ms）; 截断测试断言不超预算; 多场景兜底率断言 100% |

## Circuit breaker 遵守

投标消耗超 500 token 强制截断 → Archetype 兜底指派（测试:
`test_over_budget_truncates_to_fallback` + `test_truncation_never_exceeds_budget`）;
无资质投标一律拒绝（`TestEligibility`）; 无超时等待不存在
（`test_window_closed_yields_fallback`）。

## Verify 实测（run 20260912T123453Z-project-code-change-9c2e351b）

- `cd projects/omo && python3 -m pytest tests/test_contract_net.py -q` → 17 passed (0.11s)
- `python3 bin/plan/bet-ledger.py lint` → OK, 407 bets, no errors
- `make gac-local-gate` → PASS

## Rollback

纯新增两模块 + 测试 + ledger 条目; 回滚 = revert 单 PR。

## Lessons

- ledger 的 verify 命令 `python3 -m pytest projects/omo/tests/...` 从根跑
  没有 omo pythonpath——binding PR 顺手修正为 `cd projects/omo && ...`
  （与 T8-24C/D 的 bun→vitest 修正同模式：verify 必须真实可执行）。
