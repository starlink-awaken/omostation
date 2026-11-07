---
schema_version: specification/v1
spec_version: 1.0.0
title: A2A 冲突谓词补「锁对象缺席」判据并让 force 接管可达
bet_id: BET-Y2Q4-T10-342
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-07
---

# A2A 冲突谓词补「锁对象缺席」判据并让 force 接管可达

## 问题与证据

BET-Y2Q4-T10-292 把 `claim_run()` 的 A2A 冲突谓词（`projects/omo/src/omo/workflow/lifecycle.py:1411`
取过期集合、`:1440-1446` 判定）从「只看对方 `status == active`」补成「还要那把锁没被证明过期」。
它交付的是**有对象、能证明过期**这一类。剩下的两类在它自己的契约 2 里被**故意**折叠成同一个
「不可证明 ⇒ 算冲突」：

| 形状 | 盘上状态 | T10-292 之后 | 有无自愈路径 |
|------|----------|--------------|--------------|
| 锁存在且未过期 | 文件在，`expires_at` 未到 | 冲突 | 有（等它过期） |
| 锁存在但读不出 / 无 `expires_at` | 文件在，字段坏 | 冲突 | 有（补锁字段或等 release） |
| **锁对象根本不在** | 该 scope 一个文件都没有 | **冲突，且永久** | **无** |

第三行是本轮要消灭的形状。缺自愈路径不是因为没人去自愈，而是**三条自愈通道按构造都碰不到它**：
`release_locks()`（`lifecycle_locks.py:231`）只 unlink `run_id` 等于自己的锁；`prune_stale_locks()`
只遍历**存在**的文件；对方的 `closeout` 需要那个早已消失的会话。于是 claim 记录会一直 advertise
一条没有任何东西持有的路径。

实测读数（2026-11-07T03:42Z，共享协调面 `.omo/_delivery/agent-workflows/`，与 canonical 同一 inode 桥）：
`status=active` 的 run 4 条，其 claim 路径合计 7 条，按 scope 归一后
**ABSENT=1 / EXPIRED=6 / LIVE=0 / UNREADABLE=0**。被挡住的那一条正是台账：

- run `20261104T115230Z-project-code-change-d825f60f`，`status: active`，`updated_at: 2026-11-04T11:54:48Z`
  （三天前），记录里**没有** `last_heartbeat` 键；
- 它的 `bet_id` 是 `BET-Y2Q4-T10-285`，该条在 `origin/main` 台账里已是 `status: done`
  + `done_at: 2026-11-06` —— 活儿干完了，run 记录还活着；
- 记录 advertise 5 把锁，盘上**五把全部不存在**；它的 3 条 claim 路径里，
  `path:projects/agora` 与 `path:protocols/port-registry.yaml` 两把锁**在**且已过期
  （`expires_at: 2026-11-05T11:54:48Z`，靠 T10-292 契约 1 放行），
  而 `path:docs/plans/3y-bet-ledger.yaml` 这把**不在** —— 这一条按今日谓词落进「不可证明」，永久拒绝。

还有一层：这个拒绝**连显式接管都绕不过**。`claim_run()` 的 A2A 段（`:1440-1446`）不看 `force_lock`，
而 `force_lock` 在锁层是有语义的（`acquire_locks()` 的 `force` 分支会拆掉别人的活锁）。也就是说，
今天 `--force` 这条 sanctioned 的接管路径对第三形状**同样无效**——API 里宣称有逃生口，谓词把它挡在门外。

## 判据的依据：记录与锁的先后是确定的

`claim_run()` 里锁写在记录之前：`acquire_locks()`（`:1468`）先建锁，`write_run()`（`:1484`）才把
claim 追加进 run 记录；且记录写入失败会回滚刚建的锁（`:1485-1491` 逐条 `unlink(missing_ok=True)`）。
所以

> 「记录里 advertise 了这条路径」蕴含「claim 那一刻这把锁存在」。

逆否给出本轮放行条件的soundness：现在这把锁不在，只能是**事后**消失的（被 release、被 prune、
或被手工 unlink）。无论哪种，都不存在「该 scope 上仍有一个遵循协议的活持有者」这一状态 ——
冲突所依赖的事实已经没有了，剩下的只是一份历史意图。

## 契约

1. **新增判据函数** `lifecycle_locks.py::lock_scope_object_present(lock_dir, scope) -> bool`：
   按 `_bounded_lock_name(scope, _PATH_LOCK_NAME_MAX_LEN)` 拼名，与**写者同一个有界名**（超长 scope
   不得误报缺席）。`FileNotFoundError` ⇒ `False`；其它 `OSError`（锁目录本身不可 stat）⇒ `True`，
   即维持冲突。**显式不使用 `Path.is_file()`** —— 它把 `ENOTDIR` 吞成 `False`，会让一个坏掉的锁面
   冒充「无人持有」，正是本函数要防止的那种同形。
2. **只在显式接管时放行**：A2A 段对 `lock_absent and force_lock` 跳过该 (p, op) 对；
   `force_lock=False` 时 fail-closed 宽度一字不动 —— T10-292 契约 2 与既有用例
   `test_claim_fail_closed_when_expiry_cannot_be_proven[lock_file_absent]` 必须照常绿。
   本轮不新增 flag、不加环境变量开关、不加豁免常量；复用的是 CLI 早已存在的 `--force`。
3. **粒度按 scope 不按 run**：同一个对方 run 的两条 claim 路径，一条锁在且未过期、一条锁不在，
   则接管只放行缺席那条；放行不得顺带拆掉别人仍在持有的锁（`acquire_locks()` 一字不改，
   它只会对本次实际请求的 scope 动手）。
4. **报错面**：前缀 `A2A Path Lock Collision:` 保持不变（沿用 T10-292 契约 5，既有处置脚本按前缀识别）；
   缺席分支在原文之后追加两行诊断，点名 `scope` 与 `--force` 出口 —— 否则调用方读到的拒绝
   与「活锁在持」逐字相同，无从分诊。
5. **持有者以盘上那份 scope 锁为准**：存在性探测问「这个 scope 有没有对象」，不问「记录说该谁持有」。
   若别的 run 正持有该 scope 的锁，则对象存在，本轮一律不放行（除非它自己已可证明过期，那是契约 1 的面）。

## 非目标

- 不删改任何既有 run 记录，不手工 unlink 别人的锁，不改 `release_locks()` / `prune_stale_locks()`。
- 不改 `acquire_locks()` 的 force 分支语义，不改 `_HEARTBEAT_STALE_SECONDS` 与僵尸分类宽度。
- 不重开、不回退 T10-292 的契约 1–5，也不重开 T10-341 的同 run 续期面。
- 不把「锁缺席」推广成普通 claim 的豁免 —— 那正是 T10-292 契约 2 明令禁止的放宽。

## 验收

1. 正例：对方 active claim、该 scope 锁缺席、`force_lock=True` ⇒ claim 放行，自己拿到这把锁，
   对方 run 记录逐字节不变。摘掉放行分支 ⇒ 该用例当场红。
2. 反例配平（同一份 seed，只有 force 不同）：`force_lock=False` 仍拒，且报错前缀不变、
   正文点名缺席与 `--force`。把豁免放宽到全部 claim ⇒ 该用例与既有的
   `[lock_file_absent]` 一起红 —— 这条是「契约 2 没退化」的外部证据，不靠本轮新用例自证。
3. 反向边界两面：锁存在且 live + force ⇒ 仍拒；锁存在但 YAML 不可解析 + force ⇒ 仍拒。
4. 粒度面：混合两路径 + force ⇒ 整体仍拒；只请缺席那条 + force ⇒ 放行，且对方那把 live 锁的
   `run_id` 逐字节未变。
5. 判据面：`lock_scope_object_present()` 对超长 scope 与写者同名（经 `acquire_locks()` 造出的锁
   立即可被探到），锁目录不可 stat 时返回 `True`。把探测换成 `is_file()` ⇒ 该用例红。
6. 零回归：`projects/omo/tests/test_workflow_locks.py` 改动前基线 **58 passed**，改动后 **65 passed**
   （新增 5 个函数、其中 1 个双参，共 7 条）；ruff 干净。
