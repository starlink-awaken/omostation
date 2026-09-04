---
lifecycle: history
owner: governance-team
bet: BET-Y1Q1-T6-02
last_updated: 2026-08-16
title: BET-Y1Q1-T6-02 复盘
type: retro
---

# BET-Y1Q1-T6-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
Appetite 1 week。本轮在隔离 worktree `work/bet-y1q1-t6-02` 一次落地 grill Q1=A / Q2=A+ / Q3=A，未超一周。

## Q2 done_when 是否全部通过？哪条没过，为什么？
- Wave/Gate ↔ BET 映射覆盖 W0–W6 与 T1–T8 / T6-SUBTRACT：是（`docs/architecture/wave-gate-bet-map.md`）
- 无法一对一的项有差异清单：是（Episode/Mandate、G-CONV、T6-EVOLUTION、T9-OBSERV、Phase 编号）
- `start` 无 `--bet` halt、`--bet` 写入 run.`bet_id`：是（`chain-bind-check` + wrapper；pytest 7/7）
- ok closeout / `bet-ledger complete` 缺 binding / 北极星 / retro halt：是（同一 `evaluate_bind`）
- bootstrap/status 打印北极星与 bet/retro：是（两次 CLI 均含 `chain: north_star=` 与 `bound_bet`）
- `redlines.yaml::vision-to-retro-chain` executor 为 `bin/plan/chain-bind-check.py`：是
- 未新增 GaC required 规则、未造第四套 ID

## Q3 过程中发现的与 plan 不符的事实（打假）？
- T6-01 在 origin/main 已合并（#1545）但台账仍 `in_progress`，独占轨 T6-SUBTRACT 让 T6-02 的 `depends_on` 过不去。按事实置 T6-01 done，不是另开 T6-03。
- `start --bet` 原先只改 objective 字符串，run YAML 没有 `bet_id` 字段。硬门必须写回 run 文件，不能只靠字符串。
- `gen-agent-redlines` 只扫 GaC `governance-checks.yaml`，扫不到 `redlines.yaml`。本轮按目标计划把红线登记在 `redlines.yaml`，不新加 GaC required 规则。
- 既有 `tests/test_agent_workflow.py` 大量无 `--bet` 的 runner 单测；它们走已有 waiver `AGCP_REQUIREMENT_ITERATION_GATE=0`，硬门由 `tests/test_chain_bind.py` 覆盖。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
- 新文件：`bin/plan/chain_bind.py`、`bin/plan/chain-bind-check.py`、`docs/architecture/wave-gate-bet-map.md`、`tests/test_chain_bind.py`、本 retro
- 改接线：`bin/agent-workflow.py`、`bin/plan/bet-ledger.py`
- GaC required 规则：+0
- ADR：+0
- 脚本：+2（链检查，不是第四套台账）

## Q5 下一个认领本 track 的 agent 需要知道什么？
- 不要把 T6-02 标 done 却删掉 `chain-bind-check.py self-check`；`test -f` 映射表不算链门。
- D3/D5 仍未授权。不要发明 Wave/Gate 的第四套 ID。
- 生产路径 `start` 必须 `--bet`；豁免只有 `observer-audit` 与书面 waiver。
- 台账 `done` ≠ 已进 `origin/main`。#1547 合入前，共享 main 上没有这条链。
- `bootstrap` 的 `chain: bet=` 只看 **active** run；closeout 之后会显示 `missing-bet`，不是「从未绑定」。
- `bin/agent-workflow.py` 才是硬门。直接调 `omo.workflow.cli` 仍可无 `--bet` 开工。
- 本地 tag `bet/BET-Y1Q1-T6-02-20260815T134729Z` 必须 `git push origin <tag>`，否则 D0 的 tag 段只在本机。

## 验证轮 2026-08-16（重跑，不靠上次口述）

验收 5 条 + verification plan 6 条，在隔离树 `f7a87d3e1` 上重跑。

| 项 | 结果 | 证据 |
|---|---|---|
| A1 映射表 W0–W6 + T1–T8 / T6-SUBTRACT，无第四套 ID | PASS | `docs/architecture/wave-gate-bet-map.md`；T9-OBSERV / T6-EVOLUTION 在「无法一对一」 |
| A2 start 无 `--bet` halt；`--bet` 写入 run.`bet_id` | PASS | 缺 `--bet` exit 1 `missing_bet_id`；dry-run JSON 含 `"bet_id": "BET-Y1Q1-T6-02"` |
| A3 closeout/complete 缺链 halt | PASS | 缺 retro / 缺 bind / 缺北极星 均为 exit 1；三者齐备 exit 0 |
| A4 bootstrap/status 打印北极星与 bet/retro | PASS 带缺口 | 两次 bootstrap 均有北极星句；**closeout 后 `chain: bet=missing-bet`**（只扫 active run） |
| A5 一条 redline + 指针，无第二套规则正文 | PASS 带缺口 | `redlines.yaml::vision-to-retro-chain` executor 存在；`gen-agent-redlines` **扫不到**（只读 GaC） |
| pytest 驱动已上线入口 | PASS | `60 passed`：chain_bind + D0 + baseline + test_agent_workflow |
| 台账 verify --execute | PASS | self-check PASS；rg 命中 W0–W6 / T1 / T6-SUBTRACT / T8 |
| PR / 落地 | **未进 main** | #1547 OPEN, MERGEABLE, CI CLEAN；`origin/main` 无 `chain_bind.py` |
| 第一次 closeout | blocked | `09c57cbf` 被整树 claim drift 拦下 |
| 第二次 closeout | ok | `a21880cc` 在 omo #51 scoped baseline 之后 |

### 打假（本轮新发现）

1. **台账 done 早于 main 合入。** `bet-ledger complete` 只改 YAML。共享 main 读台账仍是 T6-01 时代，链门对在 main 上干活的 agent **还不存在**。
2. **感知在收工后变瞎。** `perception_fields` 只收集 `status==active` 的 `bet_id`。验证当天 bootstrap 打出 `bet=missing-bet`，尽管两条 T6-02 run 已关闭且带 `bet_id`。
3. **硬门只包着根仓 wrapper。** `omo.workflow.cli.start` 没有 `start_requires_bet`。绕过 `bin/agent-workflow.py` 的调用面（cockpit `agent start`、直接 `python -m omo.workflow`）可以无 `--bet` 开工。
4. **tag 未推远端。** 本地有 `bet/BET-Y1Q1-T6-02-20260815T134729Z`，`git ls-remote --tags origin` 为空。D0「commit 了就安全」已经被本仓证伪过；tag 不在 origin 等于还没钉死。
5. **submit 自动 wip 仍会发生。** `67e8a5438` 把无关的 `memory-os.yaml` 带进 PR，随后 revert。机制没治本。

### 净增减（相对 origin/main，2026-08-16 重测）

17 files, +1239 / −16。GaC required +0。ADR +0。根仓脚本 +2。omo submodule → `30663a2`（#51 scoped `--file`）。

### 对下一个 agent

合 #1547 之前不要假设 main 上有这条链。合入后第一件事：`git push origin bet/BET-Y1Q1-T6-02-20260815T134729Z`，并确认 `bootstrap` 在无 active run 时不要把「已关闭的绑定」说成 missing-bet。若要把硬门收口到 cockpit/omo CLI，另开 bet，不要再扩 T6-02。
