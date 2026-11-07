---
schema_version: specification/v1
spec_version: 1.0.0
title: acquire_locks 同 run 同 scope 补 claim 改为幂等续期
bet_id: BET-Y2Q4-T10-341
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-07
---

# acquire_locks 同 run 同 scope 补 claim 改为幂等续期

## 问题与证据

BET-Y2Q4-T10-292 修的是 `claim_run()` 的 A2A 冲突谓词（`lifecycle.py:1411`/`:1442`），
它让「对方 run 仍 `status: active`、但覆盖该 claim 的锁早已过期」不再构成冲突。
该轮的 receipt §7 显式登记了一个**残余形状**：同一 run 的第二次 claim 仍然会被挡。

本轮把残余形状定位到**另一个函数**，并且与 A2A 段无关：

- `claim_run()` 的 A2A 循环在遍历 run 文件时**跳过自己**
  （`other_run_file.name == f"{run_id}.yaml"` → `continue`），所以同 run 的第二次 claim
  根本不会走到 `expired_lock_scopes` 那段。
- 撞车发生在 `projects/omo/src/omo/workflow/lifecycle_locks.py` 的 `acquire_locks()`
  原 `:194-202`：只要目标锁文件存在且 `_classify_existing_lock()` 判为 `live`，
  就直接 `raise WorkflowError("lock HELD (live) ...")`，**不问持锁 `run_id` 是不是自己**。

后果：`agent-workflow claim <run-id> --path <本 run 已持有的路径>` 必然失败。
这正是本仓既有协议「合并型交付补 claim」（`git-discipline` skill）与多路径 run 分批 claim 的必经动作，
失败形态是「明明是我自己的锁，却报别人占着」，只能靠 `--force-lock` 绕过或另起 run。

实测复现（kernel = omo `66056471e`，最小 venv + `HOME=$(mktemp -d)`，脚本三段判别）：

```text
first acquire ok: 1
DIFFERENT path same run: OK
SAME path re-acquire same run raised: lock HELD (live) for path:a.py
OTHER run blocked as expected:      lock HELD (live) for path:a.py
```

即：**不同路径不撞（缺陷范围只在同 scope 重入）**；**同 scope 重入撞**；**别 run 抢活锁正确地撞**。

## 契约

`acquire_locks(registry, scopes, run_id, actor, force)` 在锁文件存在、`force` 为假、
且该锁分类为 `live` 时，按以下顺序判定：

1. **身份两项同时成立才放行**：锁 payload 是 mapping，且 `payload["run_id"] == run_id`
   且 `payload["scope"] == scope`。命中则**原地续期**：
   - 保留 `created_at`（不重建，接管痕迹不得被抹掉）；
   - `last_heartbeat` = 本次 `utc_now()`；
   - `expires_at` = 本次新 TTL 到期时刻（缺省 24 h，取 `runner.lock_ttl_hours`）；
   - 返回该锁的展示路径，**不新增锁文件**。
2. 任一身份不成立 —— payload 不可解析、不是 mapping、缺 `run_id`/`scope`、老格式锁、
   或 `scope` 与本次不一致 —— 维持原有 `WorkflowError`，措辞不变。
   这是 **fail-closed**：算不出「这把锁是我自己持有的」就仍按冲突处理。

第 2 条里的 `scope` 逐字比对不是冗余：锁文件名经过 `sanitize_lock_name()` 与
`_bounded_lock_name()` 的截断 + 内容 hash（`:36-46`），**文件名相同推不出 scope 相同**。
只按 `run_id` 放行会让一个同 run 的 claim 改写另一 scope 的锁内容。

`zombie_expired` / `zombie_stale_heartbeat` 两种分类的行为**逐字节不变**（仍 unlink 后重建），
`force` 路径不变，回滚集合 `acquired_paths` 只收本次新建的锁 —— 续期分支不得加入，
否则一次半途失败的补 claim 会反向释放本 run 早已持有的隔离面。

## 非目标

- 不改 `claim_run()` 的 A2A 谓词与 `lock_scopes_past_expiry()`（T10-292 已交付，本轮不重开）。
- 不改 `_HEARTBEAT_STALE_SECONDS` 与 `prune-locks` 的宽度（29 条锁里 22 条被判僵尸的那条判据不动）。
- 不动 `_classify_existing_lock()` 对不可解析锁文件的处理（`except (yaml.YAMLError, OSError)`
  → `zombie_stale_heartbeat`）；该形状在极端输入下可能上抛非预期异常，属另一面，本轮只登记不修。
- 不引入 `force` 的新语义，不给 CLI 加豁免 flag。

## done_when

1. `acquire_locks` 对「同 run + 同 scope + live 锁」返回该锁且原地续期，
   `created_at` 不变、`expires_at` 被推后 ≥ 23 h。
2. 三条反面判据各自成立且被用例点名：别 run 抢活锁仍 `WorkflowError`；
   同 run 但 payload `scope` 与本次不一致仍 `WorkflowError` 且不改动原 payload；
   缺 `run_id`/`scope` 的老格式锁仍 `WorkflowError`。
3. `tests/test_workflow_locks.py` 全绿；变异对照读数记录在案：
   只摘 `acquire_locks` 的续期分支 ⇒ 新增用例中**恰好 1 条红**，其余三条必须仍绿
   （它们是防「修过头」的闸，不是防「没修」的）。

## 验证

```bash
cd projects/omo && HOME=$(mktemp -d) UV_CACHE_DIR=$(mktemp -d) PYTHONPATH=src \
  uv run --no-project --with pytest --with pyyaml \
  python -m pytest tests/test_workflow_locks.py -q -p no:randomly -o addopts=""
```
