---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B1 回归修复 — Agent Brief 物化器的写根改调用时刻解析
bet_id: BET-Y2Q4-T10-273
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-10-27
---

# ADR-0456 B1 回归修复 — Agent Brief 物化器的写根改调用时刻解析

## 1. 缺陷与取证

`bin/panorama/materialize-agent-brief.py` 在 **import 期**把 profile 写根冻成模块常量：

```python
OUT_DIR = state_root() / "runtime" / "dashboard"
AGENT_BRIEF_JSON = OUT_DIR / "agent-brief.json"
```

这正是 B1 契约（`.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`，BET-Y2Q4-T10-232 固化）禁止的形状：
声明 `OMOSTATION_STATE_ROOT` 的时机在 import 之后时，写面仍落在旧根上，且**没有任何测试会红**——
唯一会红的就是按 resolver 匹配、并要求「改后为 0」的那条源码扫描门禁。

门禁读数（检测器 `tests/unit/test_b1_ledger_call_time.py::_frozen_write_targets`，
每个读数都带**产出它的那份检测器所在的 base**，2026-10-27 在隔离检出与 `git archive` 对照树各测）：

| base | 命中数 | 命中 |
|---|---|---|
| `616c07338` | 2 | `panorama/materialize-agent-brief.py:58:OUT_DIR`、`:59:AGENT_BRIEF_JSON` |
| `214ad1f42` | 2 | 同上（主仓前进后仍红） |
| `ef5000b56` | 2 | 同上（PR #4911 合入后的 main tip，本轮受控后继的基线） |

CI 侧同读数：`governance-verify` 步「ADR-0456 B1 call-time write-plane gate」在 **main tip `616c07338`** 的
run 40428684471 上是 `2 failed, 42 passed`，在 **main tip `ef5000b56`** 的 run 40439736535 上仍是
`2 failed, 42 passed`，两条失败都是
`test_no_module_level_profile_root_constant_left_in_bin`（`:283`）与
`test_detector_counts_the_14_prefix_baseline_violations`（`:370`）——两处的右端都是同一次
`_frozen_write_targets(CHECKOUT / "bin", ...) == set()` 实测。因此本缺陷属**预存红（主仓同红）**，
不是任何在制 PR 引入；它挡住所有基于该 main 的交付。PR #4911 已带此红合入 main（`ef5000b56`），
所以本 lane 的参照对象从「在制 PR」改为 **main 自己的 run**：合入后 `governance-check.yml` 在 main 上的
下一次 push/schedule run，该步应为绿。

引入点：`f4ab53dd0`（#4905，Agent Brief 真数据物化）与 `8e058a808`（#4907，按仓内约定声明输出路径）。

## 2. 契约

1. **写根在调用时刻解析**：产物绝对路径一律由函数现算，模块级只保留**与根无关的相对段**常量。
2. **产物落点仍可静态声明**：`runtime/dashboard/agent-brief.json` 这一段必须仍可在文件里被
   grep 到（读者 `bin/ssot/drift-face-detector.py`、`bin/ssot/auto-pruner.py` 按该相对段定位）。
3. **B1 门禁的既有四层判据必须覆盖本文件**：把 `default_target` 登记进 `STATE_ENTRIES` 与
   `LEGACY_SUFFIXES` 这两个既有名单，而不是新建一条只扫本文件的用例——名单是单一来源，
   I5（时机）、I3（等价）两层因此自动覆盖，手写平行清单正是 T10-203 假绿的形状。
4. **observe-only 边界**：本轮不写 `~/Library/LaunchAgents`、不 `bootout/bootstrap/kickstart`、
   不改 crontab、不改 `services.yaml`；只改这份脚本与其测试名单。

## 3. 非目标

- 不判定 Agent Brief 物化器该不该活、该不该装（属署名准入面）。
- 不宣布 ADR-0456 B1/B3/B4/B4b/B5 或整个 plan 完成。
- 不放宽 `test_b1_ledger_call_time.py` 的任何判据（检测器、名单、`== set()` 三条都不动语义）。

## 4. 验证判据

| 判据 | 期望读数 |
|---|---|
| `_frozen_write_targets(CHECKOUT/"bin", _profile_resolvers())` | `set()`（改前 2 条命中） |
| `test_no_module_level_profile_root_constant_left_in_bin` | PASS |
| `test_detector_counts_the_14_prefix_baseline_violations` | PASS（合成基线仍 14，实测树仍 0） |
| `default_target()` 在 import 后才声明 `OMOSTATION_STATE_ROOT` | 落点在新根之下（I5 参数化自动覆盖本文件） |
| `default_target()` 在未声明 profile 时 | 逐字节等于 `<检出>/runtime/dashboard/agent-brief.json`（I3） |
| 变异对照 | 把 `default_target()` 改回读 import 期常量 → I5 与源码扫描两条当场红 |

## 5. 已知读数分歧（如实登记，不当作本 BET 的产物）

本地全量跑该文件会另见一条 `test_measure_value_truth_run_uses_the_db_declared_after_import` 失败
（`status='unprovable' / reason='observer_unavailable'`，期望 `not_ready`）。已实测：该失败在**不含本 BET 任何改动**的
检出上以同样方式复现（单跑即红），而在 CI run 40428684471 里它是通过的——即 42 passed 之一。
所以它是「本地 FAIL / CI PASS」的环境类分歧（host 侧 sqlite/observer 状态泄漏），不是本轮引入，
也不由放宽断言来处理；登记为独立问题，本 BET 不夹带。

## 6. 措辞更正

原文件注释声称约束来自「规划层探针的 `script_output_paths()`，只认两条形状」。
本轮全仓实测：`script_output_paths` **在整个仓库里只命中这段注释本身**（含部署 clone 共 0 处实现），
因此它不构成可依赖的接线；据此改写注释。与之相对，链检查器的路径抽取器
（`bin/gac/check-execution-chain.py:56 _extract_bin_paths`）确实存在，
所以「别在本文件里写任何 Python 源文件路径」这条警告**保留**。
