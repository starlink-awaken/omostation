---
schema: md/v1
status: active
lifecycle: history
owner: engineering-agent
last-reviewed: 2026-11-23
type: report
bet_id: BET-Y2Q4-T10-344
title: BET-Y2Q4-T10-344 closeout — mini Cron 作用域主机别名（#5226 已落地）与七组回放矩阵补钉
---

# BET-Y2Q4-T10-344 收口收据

主体改动早在 2026-11-10 由 PR #5226（squash `d284efcaa`）合并进 main：`.omo/cron/registry.yaml` 的
`work-agent-respire-mbp-watchdog` 从 `hosts: [mini]` 改为 `hosts: [mini, Mac-mini]`，并同步两个测试模块。
本 BET 的残余工作是**独立验证 + 一处真实覆盖缺口 + 台账收口**，不是重做主体。

本文件是 `completion-evidence-matrix/v1` 的 `tests` / `diff` / `rollback` / `fresh_receipt` / `live_canary` /
`cleanup` 载体；`replay` 载体是 `.omo/_knowledge/retros/BET-Y2Q4-T10-344.md`。

## 读数前置条件

| 条件 | 实测 |
|---|---|
| 检出形态 | 隔离 worktree `ws-t10347-leg2`，分支 base = `origin/main@4a1459230`，非共享主工作区 |
| 交付 commit | `1e2c6cfb3 test(cron): 补齐主机作用域回放的第 7 组用例并钉住组数`（+3 行，只动 `tests/test_scheduler_compile.py`） |
| 作用域实现 | 单一函数 `bin/lib/cron_normalize.py:435 host_scoped_jobs()`；`bin/scheduler-compile.py:26` 以 `from cron_normalize import host_scoped_jobs as _host_scoped` 引它，`bin/ops/install-cron-plane.py` 的 `_compiled_lines()` 复用同一条编译链 ⇒ 「编译与安装预览同一主机作用域」不是两处平行实现，而是同一函数（M3 变异证明该分支真被测到） |
| 未动面 | `launchd` 段、命令、频率、解释器逐字未改 —— #5226 的 registry diff 只有 `hosts:` 一行值 + 一行注释，本轮 registry 零 diff |

## 受控测试（verify[0]）

```
uv run --with pytest --with pyyaml --with pytest-timeout python -m pytest -q \
  tests/test_scheduler_compile.py tests/unit/gac/test_install_cron_plane.py -p no:randomly -o addopts=
=> 55 passed in 3.42s   (rc=0, wall 4.92s)
```

## 独立七组回放（不经 pytest）

`/tmp/replay_344.py`：直接 load `bin/scheduler-compile.py` 与 `bin/ops/install-cron-plane.py`，
逐组 patch `socket.gethostname` / `CRON_HOST`，统计 crontab 行里出现 `respire_mbp_supervisor_watchdog` 的次数
（编译侧与安装侧各一次，两侧必须同值）：

| hostname | CRON_HOST | expect | compiler | installer | verdict |
|---|---|---|---|---|---|
| `Mac-mini` | — | 1 | 1 | 1 | OK |
| `mini` | — | 1 | 1 | 1 | OK |
| `mbp` | — | 0 | 0 | 0 | OK |
| `unregistered-host` | — | 0 | 0 | 0 | OK |
| `Mac-mini` | `mbp` | 0 | 0 | 0 | OK |
| `Mac-mini` | `mini` | 1 | 1 | 1 | OK |
| `unregistered-host` | `mini` | 1 | 1 | 1 | OK |

`cases=7 fails = 0`。前 6 组与 `test_host_scope_excludes_other_hosts_jobs` 的矩阵同源，第 6 行
（`Mac-mini` 被显式覆盖成 `mini`）是本轮补上的那一组：spec §离线验收枚举 4 个原生主机名 + 3 个
`CRON_HOST` 覆盖 = 7 组，落地矩阵此前只有 6 组。

## 判读要点（三条变异自证）

| 变异 | 落点 | 读数 | 还原 |
|---|---|---|---|
| M1 删第 7 组用例 | `tests/test_scheduler_compile.py:321` | `rc=1`，`1 failed, 54 passed` —— 由新增的 `assert len(cases) == 7` 当场报「主机作用域回放应为 7 组，实得 6」 | sha256 逐字节一致 |
| M2 registry 别名退回 | `.omo/cron/registry.yaml:1167` `hosts: [mini]` | `rc=1`，`2 failed, 53 passed` | sha256 逐字节一致 |
| M3 摘掉 `CRON_HOST` 覆盖分支 | `bin/lib/cron_normalize.py:432` ⇒ `return socket.gethostname()` | `rc=1`，`2 failed, 53 passed` —— 证明覆盖分支由矩阵真覆盖，不是文档口径 | sha256 逐字节一致 |

三处还原后 `ALL_RESTORED True`（`git checkout --` + sha256 比对）。**M1 是关键钉**：补钉之前「少一组」是静默的
——没有任何断言能发现矩阵缩水，这也是本 BET 唯一真正的工程增量。

## operational-轴

| 项 | 读数 |
|---|---|
| fresh_receipt | 本文件，2026-11-23 于 `origin/main@4a1459230` 的隔离 worktree 现采，未沿用 11-10/11-22 的历史快照 |
| live_canary | 上表 M1/M2/M3 的 `rc` 即 canary：判据失效时用例必红，不复绿 |
| cleanup | worktree `ws-t10347-leg2` 的 `.omo/_delivery/**` 收据与 `/tmp/replay_344.py` 为一次性产物（前者 gitignore 内）；registry / cron_normalize 变异已按字节还原，`git status --short` 对本 BET 三路径无残留 |
| 未执行动作 | 未在 mini 现场重装 crontab、未改任何运行态 —— 本 BET 是离线编译/预览口径的验证；现场装机验证归 `BET-Y2Q4-T10-279` 那类需现场主机可达的条目 |

## rollback

本轮增量是测试文件 +3 行（用例 + 组数断言），无生产代码与 registry 改动；回滚 = `git revert <merge-sha>`
或直接删去 `("Mac-mini", "mini", 1),` 与 `assert len(cases) == 7` 两行，行为面零影响（M1 已证明该断言只
约束矩阵、不约束产物）。主体别名逻辑的回滚路径是 revert #5226（`d284efcaa`），不在本 BET 范围内。

## §14.2 运行记录（本次收口自动化每条运行落一条）

```json
[
  {
    "run": "pytest-controlled-verify",
    "inputs": ["tests/test_scheduler_compile.py", "tests/unit/gac/test_install_cron_plane.py",
               "docs/superpowers/specs/2026-11-10-cron-mini-host-alias-task-eef1cedc.md"],
    "basis": "台账 verify[0].cmd + AGENTS.md §8（Python 改动 → targeted pytest）",
    "approver": "principal（2026-11-23 授权「授权全收」：重做加固→push+PR+squash 合并→retro→台账 complete）",
    "result": "55 passed in 3.42s, rc=0",
    "duration_ms": 4920,
    "model_usage": "qoder-cn agent session（本回合无独立计费子调用），无 token 计量落盘"
  },
  {
    "run": "independent-seven-case-replay",
    "inputs": [".omo/cron/registry.yaml", "bin/scheduler-compile.py", "bin/ops/install-cron-plane.py",
               "bin/lib/cron_normalize.py"],
    "basis": "spec §离线验收的 7 组枚举；绕过 pytest 直调生产函数，避免与被验对象同源",
    "approver": "principal（同上）",
    "result": "cases=7 fails=0（compiler 与 installer 逐组同值）",
    "duration_ms": null,
    "model_usage": "none（纯脚本，无模型调用）"
  },
  {
    "run": "mutation-self-proof",
    "inputs": ["tests/test_scheduler_compile.py:321", ".omo/cron/registry.yaml:1167",
               "bin/lib/cron_normalize.py:432"],
    "basis": "AGENTS.md §7「判据接线的证明必须走生产路径」+ bet-closeout-chain 步 4 的变异读数要求",
    "approver": "principal（同上）",
    "result": "M1 rc=1 (1 failed) / M2 rc=1 (2 failed) / M3 rc=1 (2 failed)；三处按字节还原 ALL_RESTORED=True",
    "duration_ms": 23457,
    "model_usage": "none（纯脚本，无模型调用）"
  }
]
```
