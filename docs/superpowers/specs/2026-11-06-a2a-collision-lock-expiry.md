---
schema_version: specification/v1
spec_version: 1.0.0
title: A2A Path Lock Collision 谓词补锁过期判据
bet_id: BET-Y2Q4-T10-292
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-06
---

# A2A Path Lock Collision 谓词补锁过期判据

## 问题与证据

`projects/omo/src/omo/workflow/lifecycle.py` 的 `claim_run()` 在 Phase 3 A2A 逻辑隔离段
（`:1409-1441`）判定路径冲突时，只问一件事：对方 run 记录的 `status` 是不是 `active`
（`:1422` `if other_payload.get("status") != "active": continue`）。它不看锁本身是否还有效。

而锁的有效性由另一套时钟决定。`lifecycle_locks.py::acquire_locks()`（`:128`）写锁时按
`runner.lock_ttl_hours`（缺省 24）算出 `expires_at`（`:139-153`），并且
`_classify_existing_lock()`（`:78`）判定 `kind` 时**先看 `expires_at`**（`:84-95`）——
已过期即 `zombie_expired`，`acquire_locks()` 随即 `unlink` 并接管（`:156-164`）。
也就是说**锁层早已按过期放行**，只有 run 记录层的谓词还按 `status` 拦。两层因此互相矛盾，
且拦下来的那一层用的是更旧的尺。

`expires_at` 不会随续期移动：`heartbeat_lock()`（`:112`）与 `_heartbeat_run_locked()` 只写
`last_heartbeat` 一个键，`expires_at` 的不变性由
`tests/test_workflow_locks.py::test_heartbeat_run_preserves_immutable_fields` 钉住。
所以一个会话闲置满 24 h，锁必然过期而 run 记录仍是 `active` —— 这不是边缘形态，是常态。

基线 `4c662cdbb`、读数时刻 `2026-11-06T23:40:48Z` 的实机协调面（`.omo/_delivery/agent-workflows/`，
全机共享面）：

- 锁 7 条，**7 条全部已过期** —— 3 条过期 35.8 h，4 条过期 38.2 h。
- `status: active` 的 run 记录 2 条：`20261104T092627Z-…-356e143c`（BET-Y2Q4-T10-282，
  记录 62.2 h 前更新）与 `20261104T115230Z-…-d825f60f`（BET-Y2Q4-T10-285，59.8 h 前更新）。
  这两条 BET 在台账里**都已是 `status: done`**，run 记录只是没收口。
- 后果：此后任何 `claim --path docs/plans/3y-bet-ledger.yaml` 都被拒
  `A2A Path Lock Collision`，尽管覆盖它的锁 `path:docs/plans/3y-bet-ledger.yaml`
  的 `expires_at` 是 `2026-11-05T11:54:48Z` —— 已过期 35.8 h。`projects/agora`、
  `protocols/port-registry.yaml` 与那 4 条 `scripts/tools/**`、`tests/unit/**` 同理。

该缺陷已由交付实录确证两次：

- `.omo/_knowledge/pitfalls/coordination/PITFALL-COO-008.yaml` 记录了一次同类阻塞
  （对方 `status=active`、心跳 28 h、锁过期 13 h），并在 `solution` 里写明正解与承接方式：
  「给谓词补一条判据——status 活跃且锁未过期才算冲突（读 lock 文件的 `expires_at`，而不是
  `run.status`），另立 BET」。
- 台账 `BET-Y2Q4-T10-285` 的 evidence note 直书「`claim --path` 台账被 PITFALL-COO-008 的
  A2A 谓词缺陷阻塞（对方 run `status=active`、心跳 43 h、锁过期 20 h），按该 PITFALL 处置为
  未 claim 交付，**谓词正解仍无承接 BET**」。本条即该承接。

## 契约（本 BET 交付的判定形状）

冲突成立当且仅当：**对方 run `status == "active"`** 且 **覆盖该重叠 claim 路径的锁未被证明已过期**。

1. 判据只读锁文件的 `expires_at`，不读 `last_heartbeat`。心跳面不得进入本谓词：
   `_HEARTBEAT_STALE_SECONDS = 3600`（`lifecycle_locks.py:27`）会把「会话闲置一小时的活 run」
   判成僵尸——PITFALL-COO-008 实测一次 `prune-locks --scan-only` 把共享面 29 条锁里的 22 条
   判成 zombie，而那三个 run 的 `status` 全是 `active`。复用 `_classify_existing_lock()` 会
   把这个宽度一起引进来，因此本谓词必须走一条**只看过期**的判据。
2. fail-closed：锁文件缺失、不可读、不是 mapping、没有 `scope`、没有 `expires_at`、
   `expires_at` 不可解析、或时间不能证明早于当前时刻 —— 一律**算冲突**（即维持今日行为）。
   放行只在「可证明已过期」时发生。
3. 作用域匹配用锁 payload 里的 `scope` 字段原文（`path:<claim 里存的路径>`），不用文件名反推：
   `_bounded_lock_name()`（`:34`）对超长 scope 做截断 + hash 后缀，文件名不是可靠的可逆键。
   claim 记录里 `claims[].paths` 与当年写入的 `scopes` 同源（实测两条 run 记录逐条对得上），
   因此按 `f"path:{op}"` 查锁即可。
4. 只放宽路径维。`surface:*` 的冲突判定不在本谓词里（它只由 `acquire_locks()` 把门），
   `acquire_locks()` 自身的准入规则一字不改。
5. 报错信息保持 `A2A Path Lock Collision:` 前缀不变，便于既有处置脚本继续按前缀识别。

## 非目标

- 不改 `expires_at` 的算法、不改 `lock_ttl_hours` 缺省值、不给心跳续期加写 `expires_at`。
- 不删除或改写任何既有 run 记录，不替别的 agent 收口 run，不手工删别人的锁。
- 不引入 force/takeover 新语义，不加豁免 flag，不放宽 WorkPacket 与 affected-graph 前置。
- 不改 `prune_stale_locks()` 的分类面（它按 PITFALL-COO-008 的告诫仍属危险动作）。

## 验证

- 反例：对方 run `status=active` 且锁未过期 → `claim` 仍拒（今日行为不得退化）。
- 正例：对方 run `status=active` 且锁可证明过期 → `claim` 放行。
- 宽度：对方心跳已过 `_HEARTBEAT_STALE_SECONDS` 但 `expires_at` 未到 → 仍拒（钉住判据 1）。
- fail-closed 四面：锁文件缺失 / YAML 不可解析 / 无 `expires_at` / `expires_at` 不可解析 → 全部仍拒。
- 实机：本 BET 交付后，`claim --path docs/plans/3y-bet-ledger.yaml` 在本协调面上成功，
  且对方 `20261104T115230Z-…-d825f60f` 的记录一字未动。
