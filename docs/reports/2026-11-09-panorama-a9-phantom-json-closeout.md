---
type: report
title: BET-Y2Q4-T10-343 收口收据 —— Panorama scheduler 采集器 phantom --json 修复
bet_id: BET-Y2Q4-T10-343
status: completed
created: 2026-11-09
last-reviewed: 2026-11-09
lifecycle: record
owner: governance-agent
schema_version: closeout-receipt/v1
---

# BET-Y2Q4-T10-343 收口收据

## 0. 一句话

Panorama A9 采集器给 `bin/scheduler-compile.py` 传了一个该脚本 argparse 从不认识的
`--json`，导致 A9 永久 `PARTIAL`（detail 恒为 `diagnostic command exit 2`）；本次改调用方
并补一条真实子进程契约回归，把这个「按构造就绿」的形状堵死。

## 1. 工程面证据（tests）

命令（在 worktree `/Users/xiamingxing/ws-a9-json-flag`，run `20261109T132140Z-project-code-change-9a8ef3d7`）：

```
uv run --with pytest --with pytest-timeout --with pyyaml pytest \
  tests/unit/test_scheduler_collector_registry_root.py -q
```

- 基线（main，改前）：`5 passed`
- 改后：**`6 passed in 0.12s`**
- 反证（把 `--json` 回塞进 argv 与守卫条件，在当前重建内容上重跑）：

  ```
  E  AssertionError: 被调用方拒绝采集器传的 ['--check', '--json']: rc=2
     usage: scheduler-compile.py [-h] [--check] [--generate {crontab,launchd}]
  2 failed, 4 passed in 0.06s
  ```

  逐字节复原 asset（`cmp` 一致）后回到 `6 passed`。反证证明新用例真的能测出这个缺陷，
  而不是又一条按构造就绿的断言。
- `ruff check tests/unit/test_scheduler_collector_registry_root.py` → `All checks passed!`

## 2. 差异面证据（diff）

`squash` 落 main：`afbe32105225e28cc00767bdb39a0e487ad172f6`（PR #5194，CI 15 pass / 0 fail，
2 skipping 为 `doc-freshness` 与 `Documents domain projects` 的常态跳过）。

```
git diff --stat 053438eea..HEAD
 bin/panorama/assets/host/scheduler_collector.py.asset           |  3 +-
 docs/plans/3y-bet-ledger.yaml                                   | 67 +++++++++++++-
 docs/superpowers/specs/2026-11-09-...-phantom-json-flag.md      | 70 +++++++++++++++
 tests/unit/test_scheduler_collector_registry_root.py            | 43 ++++++++++-
 4 files changed, 178 insertions(+), 5 deletions(-)
```

分支内 4 个 commit 按 `change-lane-check` 的 lane 拆分（`other` / `code` / `docs+docs_data`），
其中 `docs(governance)` 一笔是 CI 首跑红（spec 缺必填 `owner` →
`missing_frontmatter:accepted-specifications count=1` 无预算覆盖）的根因修复，
并同步重算台账 `content_digest`（`905ba008…` → `c08ff737…`）。

## 3. 回滚面证据（rollback）

单文件调用方改动，回滚成本 = 一次 revert：

```
git revert -n afbe32105225e28cc00767bdb39a0e487ad172f6   # 在 main 上
```

回滚后 A9 退回 `PARTIAL`（即当前已知不良态），不会引入新失败；
`tests/unit/test_scheduler_collector_registry_root.py` 的新用例会红 —— 这是刻意的：
它就是那个契约的守卫，回滚必须连带删掉它才自洽（revert 默认同删，符合预期）。

## 4. 运行面证据（live canary）

在仓内代码路径直接实例化采集器跑真子进程（无写盘）：

```
env PANORAMA_CODE_ROOT=/Users/xiamingxing/ws-a9-json-flag python3 - <<'PY'
  ... 加载 bin/panorama/assets/host/scheduler_collector.py.asset
  st = SchedulerCollector().collect()
PY
   state= OBSERVED  ok= True
   detail= None
   含 exit 2 短语: False
```

done_when 第 3 条（`collect_gates()` 重跑后 A9 detail 不再含 `diagnostic command exit 2`）
在**仓内侧**成立。**部署侧未验证**：cockpit 实际加载的是
`~/.local/opt/omostation` 下经 asset 镜像/发布链路同步的副本，其生效依赖该链路下一次发布，
不在本 BET 的写面内，故不据仓内结果宣称线上已好。

## 5. 清理面证据（cleanup）

- `runtime/affected/a9-json-flag-affected.json`（affected-graph 收据）按「用完即删、不进 commit」
  处理，`git status` 交付时仅剩预期项。
- 子模块 gitlink 零漂移：`git status --short` 无 `projects/**` 条目。为达此状态做过：
  6 个空检出 `checkout -f HEAD` 物化、3 个漂移 gitlink（aetherforge/agora/cockpit）按 pin
  `detach` 归位、`projects/metaos` 按 pin（`2bcc7af3`）物化（其 pin 不在远端 ref 上，
  从 canonical 检出按完整 sha 本地取物）。agora 被 `uv sync` 改写的 `uv.lock` 已 `checkout --` 复原。
- 未使用任何钩子绕过（无 `--no-verify`、无 known-debt 自签豁免、无 `SWARM_ESCAPE_ID`）。

## 6. 本地门禁的 1 项 FAIL（如实记录，非本 diff 引入）

`make gac-local-gate` 剩 `check-evidence-freshness` FAIL。三条实测定位它属环境条件：

1. canonical 主工作区同一检查 `PASS (score=100.0, age=0d)`（有定时写者落的
   `.omo/_delivery/evidence-smoke/2026-11-09.json` 与 `.omo/state/system.yaml`）；
2. 本 worktree 是新 claim，无报告 → 生成支路 `generation_failed — import_failed`
   （`No module named 'fastmcp'`，因 `projects/metaos` 空检出使 agora `uv sync` 起不来）；
   我没碰过的 `ws-readme` worktree 报**同一条**错，可作对照；
3. 物化 metaos 后 import 恢复（BOS 295 声明 / 219 可解析，真审计跑通），分数变 `84.5 < 90`，
   首行仍提示 `system.yaml missing` —— 扣分来自 claim 里不存在的 state 面输入。

即「判据泄漏 host 状态」+「claim 留空检出」两类已知形状的叠加。权威判定交给 CI
`governance-verify` / `gac-gate`（已绿）。
