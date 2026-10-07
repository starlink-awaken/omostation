---
schema: md/v1
type: report
status: completed
lifecycle: ephemeral
owner: governance-team
last-reviewed: 2026-10-06
bet_id: BET-Y2Q4-T10-233
title: BET-Y2Q4-T10-233 closeout receipt — omo.resident 写面按 profile 收敛到 state 根
---

# BET-Y2Q4-T10-233 closeout receipt

> 交付：`omo.resident` 16 个模块的写面在**调用时刻**按 state 根解析；跨仓「读写同根」对照检测器落地。
> 本 receipt 是 completion-evidence matrix 的 tests/diff/rollback/live_canary/fresh_receipt/cleanup 共同指针；
> replay 指针指向 `.omo/_knowledge/retros/BET-Y2Q4-T10-233.md`。

## 1 交付物（逐路径）

| 侧 | commit / PR | 路径 |
|---|---|---|
| omo | PR #208 → squash `8f5c052`（tree `5358a5a`） | `src/omo/omo_paths.py`、`src/omo/resident/{__init__,daemon,status,receipt,ledger_trace,ingest,heartbeat,monitor,signals,alert,inbox,sediment,promote,decision,execute}.py`、`tests/unit/test_omo_resident_state_root.py`、`tests/unit/test_resident_daemon.py`、`tests/integration/test_resident_roles.py` |
| root | PR #4662 → squash `2124b9d82d3925515743d028caf4e4fb7d69bbda` | `tests/unit/test_resident_write_plane_split.py`、`docs/superpowers/specs/2026-10-06-omo-resident-write-plane-state-root.md`、`docs/plans/3y-bet-ledger.yaml`、`projects/omo` gitlink |

机制（非搬家）：`omo.resident.__init__.write_path(frozen)` 把「检出相对冻结模板」在调用时刻重挂到
`omo_paths.state_root()`；非检出相对路径原样返回；未声明 profile 时逐字节等于历史路径 ——
所以 43 份 launchd plist 与 crontab 一行未动。

## 2 判据逐条实测读数

| 判据 | 命令 | 读数 |
|---|---|---|
| 1 时机（import 后声明） | `pytest tests/unit/test_omo_resident_state_root.py -q -p no:randomly` | **93 passed** |
| 2 行为（真跑一次） | 一次性 canary，两相（`--once` + 循环 SIGTERM） | `expect=29 got=29`；两检出 `.omo/**`+`runtime/**` 全量 (size, mtime_ns) 集合零变化；机器级共享面 `~/Workspace` 15 854 条目 `added=0 changed=0`；state 根出现 watermark/log/receipt/ledger |
| 3 等价（未声明 profile） | 同文件 I1 段 | 每个迁移点路径字符串与改前逐字节相同（用例断言） |
| 4 自证（源码门禁） | 同文件 I4 段 | 合成违规先点名 file+line+变量名 → 真实扫描集合为空 → 反向断言 2 处纯读面不被命中；基线 6 处由 fixture 自行物化 |
| 5 读写同根（跨仓） | `pytest tests/unit/test_resident_write_plane_split.py -q -p no:randomly` | **21 passed**；I3 读数 CHECKOUT 41 / CALLER 6 / DERIVED 3 / **STATE 0** ⇒ 判据为**否定式**，本 BET 不宣布 B1 完成 |
| 6 无回归 | `pytest tests/unit/test_omo_resident_state_root.py tests/unit/test_resident_daemon.py tests/integration/test_resident_roles.py -q` | **130 passed** |
| B1 字面判据 (b) | `grep -rE "DEFAULT_(EVENT_)?LEDGER\s*=" bin/` | **0 命中**（2026-10-06 复测，含 `.subtrees/omo/{src,tests}` 亦 0） |
| lane 纪律 | `python3 bin/change-lane-check.py --staged` | 4 个单 lane commit 各自 PASS；混合曾报 `FAIL mixed lanes=code,docs,docs_data,submodule_pointer` |

## 3 变异对照（证明判据非空转）

把基线用例里 6 处冻结写点重新包成 `write_path()` 后单跑该用例：

```
MUT … :388: AssertionError
FAILED tests/unit/test_omo_resident_state_root.py::test_prechange_baseline_is_not_zero
```

## 4 CI 读数

- omo PR #208：首跑 `test` / `test-cov` 红（基线用例读 `git show HEAD:` 被自身交付动作判红，见 retro §2/§4），
  修复后全绿 → squash `8f5c052`。
- root PR #4662：首跑 `cascading_test` 红（同一个用例经 pinned gitlink 复现）→ re-pin `8f5c052` 后全绿。
  本轮复评 22 项：pass 20 / skipping 2 / fail 0。

## 5 回滚

- root：`git revert 2124b9d82d3925515743d028caf4e4fb7d69bbda`（单 commit，含 gitlink 回到 `55ef431`）。
- omo：`git -C projects/omo revert 8f5c052` 或把根 gitlink 退回上一 SHA。
- 运行时无需回滚：机制未声明 profile 时路径逐字节不变，43 份 plist / crontab / launchd 全部未改，
  `~/.local/state/omostation/{prod,dev}` 内容未被本轮写入。

## 6 清理与诚实边界

- affected-graph receipt 只落 `runtime/affected/`，用完即删、不进 commit。
- `--once` 分支在返回前 `pid_file.unlink(missing_ok=True)`，log/receipt 需一个真被路由的事件 ——
  判据未窄化，边界记在 spec §9.1。
- `OMO_PRINCIPAL_ID` 在 omo 侧是空动作（0 命中），台账「9 处」措辞的一处前提被实测否证，登记 spec §5.4。
- 生成态（`.omo/state/system.yaml` 时间戳、`governance-history.jsonl`）未随本 PR 走。
- `bin/` 读面 32 文件 / 15 族仍按 checkout 根解析，已由 I3 检测器钉成显式集合相等 + 逐条理由，
  翻动需新的 write_surfaces。
