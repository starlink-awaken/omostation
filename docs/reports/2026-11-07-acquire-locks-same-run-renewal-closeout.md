---
type: report
title: BET-Y2Q4-T10-341 收口收据 —— acquire_locks 同 run 同 scope 补 claim 改为幂等续期
bet_id: BET-Y2Q4-T10-341
status: completed
created: 2026-11-07
last-reviewed: 2026-11-07
lifecycle: record
owner: governance-agent
schema_version: closeout-receipt/v1
---

# BET-Y2Q4-T10-341 收口收据

## 0. 一句话

T10-292 receipt §7 登记的同 run 锁自撞，根因不在 run 记录层而在 `acquire_locks()` 的 `live` 分支；
本轮把该分支补成「先算这把锁是不是本 run 按同一 scope 自己持有的」，两个身份同时成立才原地续期，
否则维持原拦截 —— fail-closed。

## 1. 交付位

| 面 | 位置 |
|----|------|
| 代码 | omo `0e36d07` → PR **omo#240** → squash 合并为 omo origin/main `97fae96e9`（2026-11-07T02:14:24Z） |
| 根仓 gitlink | `66056471e` → `97fae96e9`，随工程腿 PR **#5108** squash 合并为 origin/main `a8bdba3af`（2026-11-07T02:45:53Z） |
| spec | `docs/superpowers/specs/2026-11-07-acquire-locks-same-run-renewal.md`，`sha256:51af92050f6251fb602030b417b370e69dbf175a5adca086d18acb37cb8a6567` |
| 台账 | `docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-341` |
| 改动面 | `src/omo/workflow/lifecycle_locks.py` +14，`tests/test_workflow_locks.py` +98（净 112 insertions，0 deletions） |

## 2. 契约落点（改了什么判定）

`acquire_locks()` 原来只有一条分类：锁存在且 `_classify_existing_lock()` 判 `live` → 抛
`WorkflowError: lock HELD (live)`。它**不读持锁者身份**，所以同 run 的第二批 claim 只要与第一批
的某个 scope 字面相同，就会被自己早已持有的那把锁拦下。

现在在抛错之前加一次身份比对：

```python
held = classification.get("payload")
if isinstance(held, dict) and held.get("run_id") == run_id and held.get("scope") == scope:
    held["last_heartbeat"] = now_ts
    held["expires_at"] = expires_at.isoformat().replace("+00:00", "Z")
    lock_path.write_text(yaml.safe_dump(held, allow_unicode=True, sort_keys=False), encoding="utf-8")
    acquired.append(display_path(lock_path))
    continue
```

三条 fail-closed 约束，每条都有对应用例：

1. **两个身份同时成立**，不看其一。锁文件名经过 `sanitize_lock_name()` + `_bounded_lock_name()`
   （截断 + sha256 后缀），**同名不蕴含同 scope**，所以 `scope` 必须独立比对。
2. **payload 解析不出 mapping 即不放行**（老格式锁、坏锁一律维持原冲突原文）。
3. **`created_at` 保留**、不 unlink、不进回滚集合 `acquired_paths`（该集合只收本次新建的锁，
   所以整批后续失败不得拆掉本 run 早已持有的那把）。`force` 路径语义未动。

## 3. 读数

### 3.1 用例（verify[0]）

装置：`env HOME=$(mktemp -d) UV_CACHE_DIR=$(mktemp -d) PYTHONPATH=src uv run --no-project
--with pytest --with pyyaml python -m pytest tests/test_workflow_locks.py -q -p no:randomly
-o addopts=""`

| 阶段 | 读数 |
|------|------|
| 改动前基线（本轮先前复算） | `54 passed` |
| 改动后（omo 工作树 `0e36d07`） | **`58 passed, 2 warnings in 1.41s`** |
| 变异对照：只摘续期分支、保留 4 条新用例 | **`1 failed, 57 passed`**，红的恰是 `test_acquire_same_run_same_scope_renews_instead_of_colliding` |

变异读数的意义在「恰红 1 条」：其余 3 条与本改动不共享失效模式，正例承重。

新增 4 条用例与各自钉的面：

| 用例 | 面 |
|------|-----|
| `test_acquire_same_run_same_scope_renews_instead_of_colliding` | 正例：不报错、返回同一把锁、锁文件数不增、`created_at` 逐字节不变、`expires_at` 推后 ≥23h |
| `test_acquire_same_run_other_scope_on_same_filename_still_blocks` | 反例：同 run 同文件名但 payload `scope` 与本次不一致 → 仍拒，且原 payload 逐字节未被改动 |
| `test_acquire_same_run_legacy_lock_without_identity_still_blocks` | 反例：payload 缺 `run_id`/`scope`（老格式）→ 仍拒 |
| `test_acquire_partial_failure_keeps_same_run_existing_lock` | 回滚面：本 run 续期成功后后续 scope 撞车导致整批失败，早已持有的锁不被删除 |

### 3.2 实机 canary（verify[1]）

```
$ python3 -c "…a=l.acquire_locks(r,['path:x.py'],'run-c','agent-a',False);
              b=l.acquire_locks(r,['path:x.py'],'run-c','agent-a',False);
              print('SAME_RUN_RENEW', a==b, len(b), len(list((d/'locks').glob('*.lock.yaml'))))"
SAME_RUN_RENEW True 1 1
```

改动前同一条命令的原文读数是 `WorkflowError: lock HELD (live) for path:x.py`（本轮先前复现记录）。
三个字段各自承重：`a==b` → 返回同一把锁；`len(b)==1` → 第二批只含这一个 scope；
`glob==1` → 锁文件未新增。

### 3.3 独立性钉子（verify[2]）

```
$ python3 -c "…from omo.workflow.lifecycle import lock_scopes_past_expiry;
              print('T292_SURFACE_PRESENT', hasattr(lock_scopes_past_expiry, '__call__'))"
T292_SURFACE_PRESENT True
```

T10-292 的交付面在本轮改动后仍可达；读数转假即触发 circuit_breaker（本轮为 True）。

### 3.4 CI 与 lint 面

- omo CI（PR omo#240，三腿）：`lint pass 12s` / `test pass 1m44s` / `test-cov pass 2m3s`。
- 本地复算 CI 的 diff-scoped lint：`ruff check --select I <两文件>` → All checks passed；
  `ruff format <两文件> --check` → 2 files already formatted；
  `python scripts/contract_gatekeeper.py src/ scripts/` → Gatekeeper: 11 files checked — PASS。
- 根仓 PR **#5108**：全腿 settled，`fail=0`（`doc-freshness`、`Documents domain projects` 两条
  因 `on.paths` 过滤为 `skipping`，非红）。

### 3.5 台账写回对拍

`bin/gac/ledger-safe-insert.py --file /tmp/t341-entry-map.yaml --dry-run` 先行，
读数 `DRY-RUN OK: BET-Y2Q4-T10-341 would be inserted at line 47331`；实写读数
`OK: inserted BET-Y2Q4-T10-341 | bets now 589 | last=BET-Y2Q4-T10-341`。
按**字段路径**回读对拍（不按值匹配，见 AGENTS.md §7「刷新台账里的文件摘要必须按字段路径定位」）：

```
DIGEST_MATCH True sha256:51af92050f6251fb602030b417b370e69dbf175a5adca086d18acb37cb8a6567
ce axes: ['engineering', 'operational', 'value'] | overall: evaluating → delivery_accepted
```

## 4. 预存面（与本 diff 无关，如实记）

- `tests/test_workflow_start_preflight.py` 在本轮 hermetic 装置下 **8 failed**；把 kernel 退回改动前
  （`66056471e`）复跑同一文件，**同样 8 failed** ⇒ 预存，非本轮引入。
- `tests/test_workflow_admission.py` 在最小 venv 下 `ModuleNotFoundError: No module named 'ecos'`
  ⇒ 依赖面限制，未纳入本轮读数；该文件由 omo CI 完整依赖面覆盖且 omo#240 全绿。
- `bin/ssot/submodule-reachability-gate.py --source worktree` 在 partial worktree 下报
  `unverified=8`（advisory，非阻塞）与 `PASS (16 gitlinks)`。

## 5. 本轮另发现的第三种形状（不在本 BET 范围，读数原文）

本 run `claim` 台账路径被拒：

```
agent-workflow: A2A Path Lock Collision: path 'docs/plans/3y-bet-ledger.yaml' overlaps with
active claim 'docs/plans/3y-bet-ledger.yaml' in run 20261104T115230Z-project-code-change-d825f60f
```

实测该 run 与其 BET 的状态：

| 项 | 读数 |
|----|------|
| run `status` | `active` |
| run `last_heartbeat` | **键不存在**（`None`） |
| run `updated_at` | `2026-11-04T11:54:48Z`（3 天前） |
| run `claims[].paths` | `['docs/plans/3y-bet-ledger.yaml', 'projects/agora', 'protocols/port-registry.yaml']` |
| run `locks:` 字段 | 5 条，含 `locks/path_docs_plans_3y-bet-ledger.yaml.lock.yaml` |
| 该锁文件在磁盘 | **不存在**（`No such file or directory`） |
| 对应 BET `BET-Y2Q4-T10-285` | 台账 `status: done`、`done_at: 2026-11-06`、`overall_state: delivery_accepted`、engineering `VERIFIED` |

判据推论：`lock_scopes_past_expiry()`（`projects/omo/src/omo/workflow/lifecycle_locks.py:112-152`）
只枚举**存在的**锁文件，因此「锁文件已 release 而 run 记录未翻终态」这条路径既拿不到过期豁免，
`prune-locks` 也扫不到它（它扫的是锁文件）。叠加 `lifecycle.py:1423` 的谓词只看 `status`，
结果是**一个已交付 BET 的未关闭 run 记录，会永久阻塞其 claim 路径上的后续 claim**。

本轮处置（不扩权）：不拆别人的锁、不跑 `prune-locks`、不改别人的 run 记录；只把 `docs/plans/3y-bet-ledger.yaml`
从本 run 的 claim 集合里摘掉，其余四个 surface 正常 claim 成功，并把上面的读数原样写进本收据。
该形状另铸 BET 收口。

## 6. 回滚

单 commit `0e36d07`（omo 侧）+ gitlink 一行（根仓侧）。回滚 = 根仓 gitlink 退回 `66056471e`
（一次 revert 即足以让 `acquire_locks()` 回到「live 即冲突」的今日行为）；无 schema 迁移、无
存量锁需要清洗——续期分支只改**写入内容**，不改锁的目录布局或文件名规则，故对既有锁零影响。
