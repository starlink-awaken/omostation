---
type: ephemeral
status: completed
owner: governance-team
last-reviewed: 2026-11-02
lifecycle: history
---

# BET-Y2Q4-T10-280 Closeout Report — panorama-collect 账本路径的三层 import/默认参数冻结改调用时刻缝

> **BET ID**: `BET-Y2Q4-T10-280`（原铸 `BET-Y2Q4-T10-279`，因上游 #5010 占用同编号而改铸）
> **所属规划**: 3Y-BET-LEDGER (Y2Q4) / ADR-0456 决策 2「写路径在调用时刻解析」的 `bin/` 残面
> **责任团队**: governance-agent
> **交付日期**: 2026-11-02
> **规格**: `docs/superpowers/specs/2026-11-02-panorama-event-ledger-seam.md`
> **交付链**: 登记+代码腿 #5009（superseded）→ 受控后继 #5014 → squash `9f84b7487384d6164423dc70ceeef865bc7bb9e2`（mergedAt `2026-11-02T07:41:43Z`）→ 本收口腿（retro + receipt + 台账 evidence）

## 1. 缺陷与修复面（diff 轴）

`bin/panorama/panorama-collect.py` 的账本路径原先有三层冻结：模块级常量 `EVENT_LEDGER`（import 时求值）+ 两处 `event_ledger: Path = EVENT_LEDGER` 默认参数（def 时求值）+ 调用点显式传该常量。声明 profile 后三者仍钉在**当前检出根**，写面断在子进程/晚声明边界（AGENTS.md §7「写路径要在调用时刻解析」）。

合并后 `origin/main@9f84b7487` 的实际形状（本轮在新 worktree 逐行确认）：

| 位置 | 内容 |
|---|---|
| `:72` | `from repo_root import canonical_root, event_ledger_path, state_file_read, state_root` |
| `:364` `:375` `:666` | `event_ledger: Path \| None = None`（三处默认参数解冻结） |
| `:368` `:380` `:677` | 调用时刻 `event_ledger_path()` 回落解析 |

文件内 `runtime/omo/event-ledger` 字面量残留：**0 命中**（`rg -c` 实测）。

## 2. 测试轴（tests）

装置：hermetic —— `env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB HOME=$(mktemp -d) uv run --no-project --offline --with pytest --with pyyaml python -m pytest tests/unit/test_writeplane_root_pin.py tests/unit/test_panorama_event_ledger_seam.py -q -p no:randomly -o addopts=""`

| 树 | 读数 |
|---|---|
| 合并前分支检出（`d4d34c019`） | **16 passed** |
| 合并后新 worktree（`origin/main`） | **16 passed**（2026-11-02 复跑） |

CI 侧 `#5014` 全 17 项 pass，含 `interface-check`（5m4s，即上一轮唯一的红灯腿）、`governance-verify`（2m58s）、`bet-done-transition`、`evidence-gate`。

## 3. 落点 canary（live_canary / fresh_receipt）

同一把尺（`repo_root.event_ledger_path()`）在合并后树上的两次读数：

```
未声明 profile      → /Users/xiamingxing/ws-t280-closeout/runtime/omo/event-ledger.sqlite3
OMOSTATION_STATE_ROOT=/tmp/fake-state → /tmp/fake-state/runtime/omo/event-ledger.sqlite3
```

即：未声明时与历史布局逐字节一致（契约不变量），声明后写面跟随 profile 根 —— 这条正向落点断言由 `tests/unit/test_panorama_event_ledger_seam.py` 钉住，不靠「检出的没有」这类否定式。

## 4. pin 尺 shrink_only（同一把尺、两棵树）

`tests/unit/test_writeplane_root_pin.py` 是「写面钉在检出根」站点的登记面。本轮还掉一处站点，因此按 ISC-4 报错文本自述的正解**删行**，并由同一次扫描重签三读数（未放宽任何断言）：

| 树 | total | `runtime` 桶 | gated_sites / pairs / files |
|---|---|---|---|
| `origin/main` @ `ae4afbeb8`（修复前基线） | 456 | 51 | 154 / 144 / 95 |
| 本轮分支（修复后） | 455 | **50** | **153 / 143 / 95** |

恰好 -1，其余桶零移动 ⇒ 无新增债。spec `2026-10-13-writeplane-root-pin-gate.md` §1 第四次复核记录了这组读数，并显式否证上一段复核的「全表 455 与 §1 表逐桶相加一致」—— 该表逐桶相加实为 456。

## 5. 回滚轴（rollback）

单 commit 面回滚：`git revert 9f84b7487` 会同时移除缝、pin 尺删行与 spec 重签三处；因 pin 尺基线与代码由同一交付绑定，**不可只回滚代码不回滚登记面**（否则 ISC-4 双向集合相等当场红）。逐文件回滚的判据：回滚后 `python3 -m pytest tests/unit/test_writeplane_root_pin.py` 应回到 154/144/95 且 event-ledger 行在基线内。

## 6. 重放与清理（replay / cleanup）

- 重放：本 receipt 的每条读数都给了可复算命令（`rg -c`、`event_ledger_path()` 两次调用、hermetic pytest），在新检出上逐条复算一致。
- 清理：affected-graph receipt（`runtime/affected/`）用完即删，未进 commit；本 BET 无临时分支、无新增 worktree 残留；旧分支 `agent/governance-agent/t279-panorama-ledger-seam` 随 #5009 关闭失效，本地引用由 release 段清理。

## 7. value 轴

治理类任务，`value_indicator_policy: false`，`value: NOT_PROVEN` —— 不引入价值指标，不由 agent 自报成功。
