---
schema: md/v1
status: active
lifecycle: history
owner: governance-agent
last-reviewed: 2026-11-23
type: report
bet_id: BET-Y2Q4-T10-349
title: BET-Y2Q4-T10-349 closeout — gen-service-configs --check 语义等价判定与 services.yaml 三字段回填
---

# BET-Y2Q4-T10-349 收口收据

主体改动已由 PR #5425（squash `93b54639c`）合并进 main：`bin/mof/gen-service-configs.py` 的
`_plist_equivalent()`（:288，plistlib 深比较 + malformed 回退剥注释）、`working_directory` 渲染（:347-351）、
`calendar: list[dict]` 多时刻渲染（:361-376）、`.omo/_truth/registry/services.yaml` 的 omostation.omo-debt-refresh
三字段回填（:5875-5883）、`tests/test_gen_service_configs.py` 的 4 条新用例，以及两份 retro（T10-348/349）。
**本 BET 的残余是独立复核 + 台账收口**，未再改生产代码。

本文件是 `completion-evidence-matrix/v1` 的 `tests` / `diff` / `rollback` / `fresh_receipt` / `live_canary` /
`cleanup` 载体；`replay` 载体是 `.omo/_knowledge/retros/BET-Y2Q4-T10-349.md`（#5425 作者所写，本轮不改写、只按 sha256 绑定）。

## 读数前置条件（这条决定其余读数是否成立）

| 条件 | 实测 |
|---|---|
| `--check` 的注册表根 | `services_yaml_path() = workspace()/.omo/_truth/registry/services.yaml`，而 `workspace()` = `bin/lib/repo_root.py:canonical_root()` —— **`--check` 永远读规范检出，不读当前 worktree**（:36-57 的 docstring 记着 2026-08-08 事故：worktree 里跑 `--write` 会把机器级 plist 路径写成那个临时检出） |
| 由此产生的装置陷阱 | 在 worktree 里改 `services.yaml` 再跑 `--check`，读数不变（实测 M3：删掉 `working_directory:` 行后仍 `✅ 0 drift`，rc=0）。这条不是回归，是装置没接上 —— 要验声明层必须改规范检出，或改用下面的 M2 等价判据 |
| 对照判据（替代 M3） | 摘掉**生成侧**的 `working_directory` 渲染块 ⇒ `--check` rc=1 报 drift（实测见下表 M2'）—— 说明本机已装 plist 确实携带 `WorkingDirectory`，故 SSOT 回填与渲染两者都是承重的 |
| 取数位置 | 隔离 worktree `ws-t10347-leg2`（base `origin/main@c8efc46b8`），未碰规范检出的工作树 |

## 受控测试（verify[0]）

```
uv run --with pytest --with pyyaml python -m pytest tests/test_gen_service_configs.py -q -p no:randomly -o addopts=
=> 20 passed in 0.48s   (rc=0, wall 1.75s)
```
其中本 BET 的四条为 `test_check_ignores_xml_comment_only_drift` / `test_check_ignores_whitespace_layout_drift` /
`test_check_reports_substantive_drift_after_semantic_compare` / `test_working_directory_and_calendar_list_rendered`
（`tests/test_gen_service_configs.py:367/383/393/403`）。

## 本机判定（verify[1]）

```
uv run --with pyyaml python bin/mof/gen-service-configs.py --check
=> ✅ 0 drift (78 launchd services)   (rc=0)
```
done_when 第 3 条要求的「78 services」读数与此一致；同一条 `--check` 也是 E1 判据 `run_e1_drift()`（:531，
子进程原样调 `--check --json`）的输入，故本机 `service-config-drift` 面自此不再假红 —— 这正是 spec 写的
「自 11-10 起阻塞一切本机 gac-local-gate 全绿与 workflow closeout」的解除点。

## 判读要点（变异自证）

| 变异 | 落点 | 读数 | 还原 |
|---|---|---|---|
| M1 语义等价退回逐文本对比 | `_plist_equivalent` 内 `plistlib.loads(...) == plistlib.loads(...)` ⇒ `existing.strip() == generated.strip()` | pytest `rc=1 / 2 failed, 18 passed`；**同检出 `--check` 由 rc=0 变 rc=1**，drift 项正是 `com.omostation.omo-debt-refresh` —— 这就是 11-10 起永久假红的复现 | sha256 一致 |
| M2 摘掉 `working_directory` 渲染块 | `gen_launchd_plist()` :347-353 | pytest `rc=1 / 6 failed, 14 passed`；`--check` `rc=1`（报 drift） | sha256 一致 |
| M3 撤 `services.yaml` 的 `working_directory` 回填 | worktree 内 `.omo/_truth/registry/services.yaml:5876` | `--check` **rc=0**（无效）—— 原因见「前置条件」表：`--check` 读 canonical 检出，不读 worktree。该判据在 worktree 不可得，改由 M2' 承担 | sha256 一致 |

三处均 `git checkout --` + sha256 比对还原；`--check` 全程只读，不写 `~/Library/LaunchAgents`（`--write` 未执行）。

## operational-轴

| 项 | 读数 |
|---|---|
| fresh_receipt | 本文件，2026-11-23 现采（非沿用 #5425 落地当天作者自述） |
| live_canary | 本机 `--check` 的 rc 翻转（M1 ⇒ rc=1 且点名 omo-debt-refresh）= 判据真挂在对比层上 |
| cleanup | 无机器级写入；三处变异按字节还原；`--write` / `launchctl` 全程未调用 |
| 未执行动作 | 未重装本机 plist、未同步 `--write` 安装路径（spec 非目标第 3 条），现场部署侧另案 |

## rollback

单文件 `git revert`：`_plist_equivalent` 的语义比较、`working_directory`/`calendar` 渲染、`services.yaml`
三字段回填各自独立可回退，无状态写入、无接口变更（spec §回滚）。回退对比层即恢复 11-10 起的永久假红
（M1 实测 rc=1），因此**只应整体 revert，不应只回退对比层**。

## §14.2 运行记录

```json
[
  {
    "run": "pytest-controlled-verify",
    "inputs": ["tests/test_gen_service_configs.py", "bin/mof/gen-service-configs.py",
               "docs/superpowers/specs/2026-11-22-service-config-check-comment-false-positive-bet-t10-349.md"],
    "basis": "台账 verify[0].cmd；AGENTS.md §8（Python 改动 → targeted pytest）",
    "approver": "principal（2026-11-23「充分授权，全面推进」+「授权全收」；spec frontmatter `accepted` 记 2026-11-22 授权连续处置）",
    "result": "20 passed in 0.48s, rc=0（含本 BET 4 条新用例）",
    "duration_ms": 1750,
    "model_usage": "qoder-cn agent session，无独立子调用计量"
  },
  {
    "run": "live-check-canary-and-mutations",
    "inputs": [".omo/_truth/registry/services.yaml", "bin/mof/gen-service-configs.py",
               "~/Library/LaunchAgents/com.omostation.*.plist（只读）"],
    "basis": "spec §目标（仅注释差异必须 0 drift）+ done_when[2]（78 services）；台账 circuit_breaker 要求先量 `--write` 等消费面",
    "approver": "principal（同上）",
    "result": "基线 `✅ 0 drift (78 launchd services)` rc=0；M1 rc=1 且点名 omo-debt-refresh；M2 rc=1；M3 在 worktree 无效（canonical_root 口径），已登记为装置限制",
    "duration_ms": null,
    "model_usage": "none（纯脚本，无模型调用）"
  }
]
```
