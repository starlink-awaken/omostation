---
type: report
title: BET-Y2Q4-T10-345 收口收据 —— 常驻自愈派发按 objective 折叠重复建档
bet_id: BET-Y2Q4-T10-345
status: completed
created: 2026-11-10
last-reviewed: 2026-11-10
lifecycle: record
owner: governance-agent
schema_version: closeout-receipt/v1
---

# BET-Y2Q4-T10-345 收口收据

## 0. 一句话

`omo.resident.dispatch.dispatch_task` 每次调用无条件新建一份 TaskObject JSON + 一张 Action Desk
卡片 + 一次隔离工作树请求，而巡检探针与大屏 triage 是**周期性重报同一条件**的生产者，于是
`.omo/_truth/task-center/dispatches/` 无界增长（实测 33 份档案只有 6 个 distinct objective，
最多一个重复 10 次）；本次在生成侧加一道「归一化 objective + TTL 新鲜度」的折叠，命中时复用
既有 `task_id`、不新建任何东西。

## 1. 缺陷面证据（实测计数，非推断）

在 canonical 主工作区只读扫描 33 份已提交档案：

```
档案=33 distinct_objective=6 全部重复?=True 最大重复=10
   10  自治自愈 [HEAL_BRANCH_CLAIMS_ARCHIVE]: 将超期已完成的分支认领文件归档至 .omo/tasks/archived/
    6  自愈修复: dashboard_projection · 根因初判: dashboard_projection 运行态
    5  自愈修复: projects/omo/tests · 根因初判: projects/omo/tests 代码逻辑或
    4  自治自愈 [HEAL_TEMP_RESIDUE]: 清理或归档根目录临时缓存与临时产物
    4  自治自愈 [HEAL_STRAY_TEST_SCRIPTS]: 将根目录游离测试脚本安全归档至 projects/omo/tests/scrat
建档年龄(天) max=24.5 p50=22.4 min=13.1
```

状态分布 `ready_for_review`(12)/`worktree_ready`(11)/`worktree_missing`(10)；`worktree_missing`
**全库无代码写入方**（只命中 ADR-0466 的诚实失败措辞与 `bin/gac/check-test-host-hygiene.py:58`
注释），由执行侧手写。这就是判据不能取 `status` 的实证依据（spec §2）。

## 2. 工程面证据（tests）

命令（worktree `/Users/xiamingxing/ws-dispatch-dedupe/projects/omo`，run
`20261110T114451Z-governance-state-mutation-169ece60`）：

```
cd projects/omo && env HOME=$(mktemp -d) UV_CACHE_DIR=$(mktemp -d) PYTHONPATH=src \
  uv run --no-project --with pytest --with pyyaml python -m pytest \
  tests/unit/test_resident_dispatch.py -q -p no:randomly -o addopts=""
```

- 基线（`-k "not dedupe and not window_and_corruption"` 摘掉新增 4 条）：`5 passed`
- 改动后：**`9 passed`**
- 同一套件的第二种跑法（不经 uv，用 `PYTHONPATH=src` + 仓内 venv 解释器，绕开 `addopts` 分片）
  读数一致：`9 passed` / 与 worker 合跑 `13 passed`。
- 变异（`if existing is not None:` → `if False:`）：**`2 failed, 7 passed`** —— 恰红在
  折叠正例与「消费面四键」用例上，证明这两条断言真挂在这道分支上；
  `/bin/cp -f` 逐字节复原后回到 `9 passed`，最终 blob 内 `if existing is not None:` 在位。
- 族回归：`pytest tests/unit -k "resident or dispatch"` → **388 passed, 251 deselected**
- done_when 第 3 条点名的两个文件直接对拍：`pytest tests/unit/test_resident_worker.py
  tests/unit/test_resident_dispatch.py -q -p no:randomly -o addopts=""` → **13 passed**
  （4 worker + 9 dispatch，零回归）。注：先前「单跑该文件 no tests ran」是 `addopts`
  分片参数与该目录 cwd 的叠加工，不是文件缺失 —— 该文件 3608B / 4 用例，`--collect-only` 可证。
- `uvx ruff check src/omo/resident/dispatch.py tests/unit/test_resident_dispatch.py` → `All checks passed!`
- 插曲：`uvx ruff` 会改写受跟踪的 `projects/omo/uv.lock`，已 `git checkout -- uv.lock` 复原，未入 commit。

## 3. 差异面证据（diff）

子仓 PR `starlink-awaken/omostation-omo#247`（lint / test / test-cov 全绿，CLEAN）squash 为
`b8c191c`；主仓 PR #5253 squash 为 `ba3dd71afc996c2b1abda6ab1de79fc7160737fa`：

```
docs/plans/3y-bet-ledger.yaml                                    | 台账新增 BET-Y2Q4-T10-345（593 条）
docs/superpowers/specs/2026-11-10-...-objective-dedupe.md        | 新增 spec（specification/v1, lifecycle: contract）
projects/omo                                                     | gitlink → b8c191c
```

CI 首跑 `Pre-commit hooks check` 与 `gac-gate` 两条红同一根因：spec 缺必填 `owner` ⇒
`missing_frontmatter:accepted-specifications count=1` 落进 `unbaselined_warning` error 桶。
补字段的同时重算台账 `content_digest`（`faeaf08b…` → `34b8a821…`），本地
`doc-governance-check.py --no-new-warnings` 复核 `PASS (4802 files, 0 warnings)` 后重推。

## 4. 回滚面证据（rollback）

折叠分支是 `dispatch_task` 入口的一段前置 return，回滚 = 一次 revert：

```
git revert -n ba3dd71afc996c2b1abda6ab1de79fc7160737fa   # 主仓；子仓侧同 revert b8c191c
```

亦可**不改代码**即时关闭：`OMO_DISPATCH_DEDUPE_TTL_S=0` ⇒ `_find_recent_dispatch` 直接返回
`None`，行为逐字回到改动前（实机读数 `TTL0 None? True`）。回滚后新增用例会红 —— 刻意如此，
它们是这道契约的守卫。

## 5. 运行面证据（live canary + cleanup）

对 **canonical 真实档案目录**只读调用新判据（`tasks_dir` 显式传入，不触碰写面）：

```
CANONICAL_STALE None? True     # 存量 13~24 天全在 72h 窗口外 ⇒ 折叠不追溯存量
FRESH_COPY  HIT?  True         # 拷一份真实档案把 created_at 改成 now ⇒ 命中该 task_id
OTHER_OBJ   None? True         # 不同 objective 不被误吞
WHITESPACE_EQ?    True         # `: ` vs `:  ` 归一化后命中同一档（探针与巡检的同串不同空白）
TTL0        None? True         # env 关折叠 ⇒ 逐字回到旧行为
```

**部署侧未验证**：机器上常驻作业实际加载的是 `~/.local/opt/omostation` 安装位副本，其生效
依赖该链路的下一次发布；本 BET 写面只到仓内源码，故不据仓内读数宣称线上已好。

清理面：

- `runtime/affected/affected-dedupe.json`（affected-graph 收据）按「用完即删、不进 commit」处理。
- 存量 33 份派单档案一份未删、一份未改（principal 权限）。
- 未使用任何钩子绕过：无 `--no-verify`、无 `SWARM_ESCAPE_ID`、无 known-debt 自签豁免。

## 6. 已知残余与未做（如实）

1. **残余增长是有界非零**：每个重复条件每 72h 至多再落 1 份。彻底止住需要
   `.omo/_truth/task-center/dispatches` 的 trackedness 裁决（BET-Y2Q4-T10-289 closeout 明确
   登记为未裁分叉，改 `.gitignore` 或摘库须另行授权）——本 BET 不裁、不动。
2. **本次自伤一次并已归位（含第二次咬人）**：为补 worktree 内 `projects/knowledge/gbrain` 空壳检出，误用
   `git -C <sub> checkout --detach`，该目录 `.git` 指向的 per-worktree module gitdir 不可解析 ⇒
   向上解析到**根仓**，主 worktree HEAD 被 detach 到外来 commit、gbrain 检出被抹。
   恢复：`git checkout agent/governance-agent/dispatch-dedupe`（零丢失，交付物此前已全部 commit）。
   第二段：正路重clone 跑了 10 分钟未完，为先解锁 push 我杀掉 clone 并删掉半截目录 ——
   `sync-submodules-push.sh` 放行（未初始化=合法）但 `n-gate.py` 的
   `submodule-reachability` 判 `d347eb3b unreachable: submodule working tree missing`，
   push 再拒（rc=1，多耗 251s）。最终按 `git submodule update --init --depth 1
   projects/knowledge/gbrain` 补回检出（`checked out 'd347eb3b…'`，6 分钟），
   `git -C … rev-parse --show-toplevel` 重新等于子模块路径。
   详见 retro 教训 1（`git -C` 前置条件）与教训 6（pre-push 两套相反的未初始化语义）。
3. `make gac-local-gate` 在 claim worktree 内不可复现（子模块浅 init / 空检出导致的环境类失败），
   权威判定交 CI `governance-verify` + `gac-gate`（本次已按 CI 原文修复 `owner` 缺失）。
