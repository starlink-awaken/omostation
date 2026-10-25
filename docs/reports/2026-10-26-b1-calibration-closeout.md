---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-26
bet_id: BET-Y2Q4-T10-268
---

# BET-Y2Q4-T10-268 收口 receipt — B1 口径归一

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-268`  
规格：`docs/superpowers/specs/2026-10-26-b1-calibration.json-and-brief-readings.md`  
复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-268.md`  
Workflow：`20261025T233146Z-bet-execution-c8819b41`

## 1 交付范围

1. `bet-ledger list --json` 的序列化出口增加 `default=str`，使 YAML date/datetime 不再直接失败；专项测试直接以解析出的 `datetime.date` 验证 `cmd_list()` 输出可 `json.loads`。
2. Agent Brief 在 `work_state.readings` 增加三读数并列层：`ledger`、`objective_coverage`、`value_proof`。每行携带 `meaning`、`source`、`kind`、`live`、`generated_at`、`comparability`；当前 cohort 的 `comparable_pair_count=0`。
3. `docs/PANORAMA.md` 移除已退役 `panorama-dashboard-refresh` 的现行调度表述，订正为 `zhixing-projection-republisher`（300s）与 `zhixing-projection-fullrefresh`（1800s）。

## 2 验收读数

命令均为 2026-10-25T23:35Z 前后在 `fix/b1-calibration` worktree 实测。

```text
env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT \
  uv run --with pytest --with pytest-timeout --with pyyaml \
  python -m pytest tests/unit/test_bet_ledger_json_output.py \
    tests/unit/test_panorama_agent_brief.py -q -p no:randomly
→ 25 passed in 0.12s

uv run --with pyyaml python bin/plan/bet-ledger.py lint
→ OK -- 564 bets, 16 tracks, no errors

python3 -m py_compile bin/plan/bet-ledger.py bin/panorama/panorama-collect.py
→ exit 0
```

焦点测试覆盖 JSON 出口与 Brief 三读数；ledger lint 覆盖台账结构与 acceptance 面；`py_compile` 覆盖两个 Python 交付面。

## 3 运行时观测

| 观测面 | 读数 | 判读 |
|---|---|---|
| `com.omostation.zhixing-projection-republisher` | `runs=2281`, `last exit code=0`, `run interval=300s` | 调度按预期运行；`state=not running` 是 interval job 两次运行间的正常状态。 |
| `com.omostation.zhixing-projection-fullrefresh` | `last exit code=1`, `run interval=1800s` | 调度仍在触发，但最近一次退出失败。 |
| fullrefresh 根因 | guardian 报 `checkout_or_child_dirty` | `projects/omlxc` 子模块含 modified content；属部署卫生前置失败。 |
| projection revision | pointer mtime 鲜活，publisher checkout 落后本分支 | revision 能更新，但未合并前不会包含新 `readings` 合同。 |

本轮 non-goal 明确不启停 launchd、不写 `~/Library/LaunchAgents`、不部署 collector、不修 fullrefresh。上述失败只作为运行腿边界记录。

## 4 完成证据矩阵

- Engineering：`VERIFIED`。代码、测试、spec、台账与文档在交付分支可达；三项本地验收全绿。
- Operational：`PROVEN`。republisher 的 launchd 读数证明 300s 投影面持续运行；fullrefresh 的失败读数与根因也被显式记录。不因工程验收通过而宣称已完成部署。
- Value：`NOT_PROVEN`。本轮没有用户价值指标，也没有把三类异义读数相减；台账 `value_indicator_policy=false`。

交付合并后以 squash merge commit 更新台账 `engineering.merged_reachable_commit.ref`。报告与复盘的 SHA256 在文件定稿后写入台账。

## 5 回滚与边界

- 回滚单元是本 PR 的 squash commit；不删除或重置运行态 projection revision。
- `runtime/affected/` 是 workflow claim receipt，不进入 git。
- 已知遗留：fullrefresh 因 `projects/omlxc` dirty 而失败；publisher 部署与 fullrefresh 卫生修复需要另行授权和独立验证。
