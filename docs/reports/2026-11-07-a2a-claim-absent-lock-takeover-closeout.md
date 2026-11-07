---
type: report
title: BET-Y2Q4-T10-342 收口收据 —— A2A 谓词补「锁对象缺席」判据并让 force 接管可达
bet_id: BET-Y2Q4-T10-342
status: completed
created: 2026-11-07
last-reviewed: 2026-11-07
lifecycle: record
owner: governance-agent
schema_version: closeout-receipt/v1
---

# BET-Y2Q4-T10-342 收口收据

## 0. 一句话

PITFALL-COO-008 那条 A2A 谓词缺口的第三种落点 —— 对方 active claim 的锁对象**根本不在盘上**时，
「不可证明过期」与「无活持有者」在谓词里同形，该路径永久封锁且 `--force` 接管同样被拒 ——
本轮补了 `lock_scope_object_present()`，并把放行**严格限定**在显式接管这一支；
普通 claim 的 fail-closed 宽度（T10-292 契约 2）一字未动。

## 1. 缺陷的实机形态（改动前）

2026-11-07T03:42Z 对协调面做一次实读（4 条 `status: active` 的 run / 7 条 `claims[].scopes`）：

```
ABSENT=1  EXPIRED=6  LIVE=0  UNREADABLE=0
```

缺席的那条是 `path:docs/plans/3y-bet-ledger.yaml`，属 run
`20261104T115230Z-project-code-change-d825f60f`（actor `claude-lead`，bet `BET-Y2Q4-T10-285`，
台账实测 `status: done` / `done_at: 2026-11-06`；该记录 `last_heartbeat` 键缺失、mtime
`2026-11-04T11:54:48Z`）。它 `locks:` 列的 3 个路径里 2 个仍在盘上且均已过期，只有 ledger 这把不在 ——
即本轮用例 `test_takeover_exemption_is_per_scope_not_per_run` 所建模的混合形状，不是纯假设。

同一命令在改动前的两次读数**逐字节相同**，这就是缺陷本身（逃生口按构造不可达）：

```
$ python3 bin/agent-workflow.py claim 20261107T035147Z-project-code-change-f057f578 \
    --path docs/plans/3y-bet-ledger.yaml --affected-receipt runtime/affected/t342-receipt.json
agent-workflow: A2A Path Lock Collision: path 'docs/plans/3y-bet-ledger.yaml' overlaps with
  active claim 'docs/plans/3y-bet-ledger.yaml' in run 20261104T115230Z-project-code-change-d825f60f

$ 同上 + --force-lock
（与上一行完全相同）
```

## 2. 判据依据（为什么不放宽契约 2）

`claim_run()` 里锁写在记录之前，且记录写入失败会回滚刚建的锁：

- `projects/omo/src/omo/workflow/lifecycle.py` `acquire_locks()` → `write_run()`（顺序）
- 同文件 `write_run()` 失败分支对 `created_locks` 逐个 unlink（回滚）

⇒ **「run 记录里 advertise 这条路径」蕴含「claim 当时该路径的锁存在」**。今天探不到对象，
只能说明它事后消失了（`release_locks()` / `prune_stale_locks()` / 手工 unlink），即没有活持有者。
反过来说，锁**在**但读不出（YAML 损坏、非 mapping）时蕴含关系不成立，所以那一面继续算冲突。

探测实现用 `stat()` 而非 `Path.is_file()`：后者把 `OSError` 吞成 `False`，会让「不可探测」冒充
「无持有者」，并使 `except OSError: return True` 成为永不执行的死分支。锁目录不可 stat 时返回 `True`
（维持冲突），宽度不放宽。

## 3. 改动面

| 仓 | commit | 文件 | 量 |
|----|--------|------|-----|
| omo | `67114a3`（squash → `81185dfc1`, omo#241） | `src/omo/workflow/lifecycle_locks.py` / `src/omo/workflow/lifecycle.py` / `tests/test_workflow_locks.py` | +147 / -3 |
| omo | `ac20a93` | `tests/test_workflow_locks.py`（幽灵引用订正，见 §6） | +1 / -1 |
| 根 | `e87413174` + `9700aa847`（squash → `bd5afa2e6`, PR #5115） | 台账铸造 + spec + `projects/omo` gitlink | +188 / -1 与 gitlink |

根仓两次 commit 是 `change-lane-check` 的 lane 要求（`ALLOWED_COMBOS` 含 `{docs, docs_data}`，
不含与 `submodule_pointer` 的任何组合），不是拆修。

## 4. 验收读数

**单测**（hermetic 装置：`HOME=$(mktemp -d)` + `GIT_CONFIG_NOSYSTEM=1` + `GIT_CONFIG_GLOBAL=/dev/null`
+ `UV_CACHE_DIR=$(mktemp -d)` + 最小 venv `--with pytest --with pyyaml`）：

```
基线（既有 58 条）            58 passed
改动后（58 既有 + 7 新增）    65 passed
ruff                          clean
```

**变异对照**（按改法分别记读数，不合并成「都红」）：

| 变异 | 红数 | 承重断言 |
|------|------|----------|
| 摘掉 `force_lock` 缺席放行分支 | 2 | 正例 + 粒度面 |
| 豁免不附 `force_lock` 条件（放宽到全部 claim） | 2 | 无-force 反例 + 既有 `[lock_file_absent]`（契约 2 未退化由**既有**用例作证） |
| 探测退回 `Path.is_file()` | 1 | 锁目录不可 stat → 返回 True 那条 |

**改动后 live canary**（真实 CLI，与 §1 同一条命令）：

```
$ claim --path docs/plans/3y-bet-ledger.yaml                    # 无 force
agent-workflow: A2A Path Lock Collision: path '…' overlaps with active claim '…' in run 20261104T115230Z-project-code-change-d825f60f
  lock object for path:docs/plans/3y-bet-ledger.yaml is absent — no live holder, 该 claim 只剩历史记录;
  确认对方已不在此路径上工作时用 --force 显式接管 (不删对方 run 记录)。

$ claim --path docs/plans/3y-bet-ledger.yaml --force-lock
claimed 20261107T035147Z-project-code-change-f057f578
- path:docs/plans/3y-bet-ledger.yaml
```

两句话的差别就是本轮的全部交付：**拒绝仍在（宽度未变），但缺席这一成因与它的退出路径现在被说出来了**。

接管副作用面（只读复核）：自己的锁 payload `run_id = 20261107T035147Z-project-code-change-f057f578`、
`expires_at: 2026-11-08T04:08:56Z`；对方 run 记录 mtime 仍 `2026-11-04T11:54:48Z`、
sha256 前缀 `b98677b1b163`（逐字节未动）；其另两条 claim 路径（`projects/agora`、
`protocols/port-registry.yaml`）的锁文件未被触碰。**本轮不拆别人锁、不改别人 run 记录。**

**独立性与 T10-292 面不共享失效模式**：`lock_scopes_past_expiry` 与 `lock_scope_object_present`
两个 callable 同时在场，且过期集合对本次缺席 scope 不命中（台账 `verify[2]` 的 `T292_SURFACE_PRESENT True`）。

**台账 `verify[]` 三条在合入后的树上逐条复算**（基线 `bd5afa2e6`，`projects/omo` gitlink 已指 `81185dfc1`）：

```
verify[0]  cd projects/omo && <hermetic pytest>      → 65 passed in 2.18s
verify[1]  ABSENT_PROBE                              → ABSENT_PROBE False 1 True
verify[2]  T292_SURFACE_PRESENT                      → T292_SURFACE_PRESENT True
```

`ABSENT_PROBE False 1 True` 三段的含义：空目录探不到 ⇒ `False`；`acquire_locks()` 造出 1 把；
再造完立刻能探到 ⇒ `True`。这一段是「判据面与写者同源」（同一个 `_bounded_lock_name`）的最小复现，
不是对某个具体锁文件名的记忆。

## 5. 回滚

- 代码面：revert omo `81185dfc1`（走 omo PR），根仓 gitlink 回 `97fae96e9`；或整份 revert 根 `bd5afa2e6`。
  回滚后退回本轮改动前的行为（缺席 ⇒ 永久拒绝），不会破坏 T10-292 的过期豁免。
- 机器面：本轮新增的只有本 run 自己的 3 把 scope 锁（ledger / spec / `projects/omo`），
  随 `agent-workflow.py closeout` 的 `release_locks()` 自行 unlink，未过期时也会在 24h TTL 后被 prune 正常回收；
  对方记录与锁零改动，故无需机器侧回滚动作。

## 6. 残留与如实披露

- **幽灵引用一次（自伤，已订正）**：omo `67114a3` 的用例 docstring 写了 `PITFALL-COO-009`，
  而 `coordination` 注册表实测只有 COO-002…COO-008（`rg -c` 命中 0）。注册表不在本 BET 的
  `write_surfaces` 内，所以按 COO-008 的 `solution`（「该形状另立 BET」）把它认成同一条缺口的第三形，
  以 `ac20a93` 订正引用，而不是新建登记。
- **standalone clone 的根深度红（预存，非本轮引入）**：
  `projects/omo/tests/test_workflow_claims_authority_bridge.py::test_hard_run_digest_unchanged_by_binding_record`
  在非 `projects/omo` 嵌套位置的检出里必红 —— `omo.workflow.core` 用 `parents[5]` 反推 workspace 根，
  独立克隆时落到 `/Users`，于是 `.omo/_delivery/agent-workflows/locks` 解析为 `/Users/.omo/…`。
  基线复算（三个改动文件退回后同装置重跑）读数一字不差 ⇒ 装置缺陷而非回归。处置需要把根交给 env，
  超出本轮范围，已按 report-only 上报。
- **新文档 frontmatter 照抄邻居，抄到的是「已基线的例外」而不是「绿」（自伤，已订正）**：
  收口腿的 retro 初版按 `BET-Y2Q4-T10-341.md` 抄 `status: completed` + `lifecycle: record`。
  同一份内容在 T10-341 的路径上读到 `warnings: 0`，在新文件上读到 2 条未基线告警
  （`doc-governance-check.py --scope workspace --files <路径> --json`），而 CI 用的是 `--no-new-warnings`。
  仓内惯例实测：637 份 retro 中 `lifecycle: history` 623 份、`status: active|archived` 613 份，
  `completed`/`record` 仅 3 份离群。已改为 `active`/`history`，复跑读数 `errors: 0 warnings: 0`。
- **未做（按非目标）**：不引入新的 `--force` 语义层级（如按 run 批量接管）、不改 `prune-locks` 的心跳阈值、
  不动 T10-292 契约 1–5。COO-008 的注册表措辞也未刷新（写面未授权）。
- **清理面**：`ws-a2a-lock-selfcollision`（T10-341 收口腿，内容已逐字节在 main）已 release；
  `ws-a2a-claim-absent-lock-t342` 与 `.omo/_delivery/branch-claims/a2a-claim-absent-lock-t342.json`
  随本收据合入后释放。`runtime/affected/` 的一次性 affected-graph receipt 未进入任何 commit。

## 7. 复核锚点

- spec：`docs/superpowers/specs/2026-11-07-a2a-claim-absent-lock-takeover.md`（契约 1–5 + 非目标）
- retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-342.md`
- omo PR：starlink-awaken/omostation-omo#241 → `81185dfc1`
- 根 PR：starlink-awaken/omostation#5115 → `bd5afa2e6`
- governed run：`20261107T035147Z-project-code-change-f057f578`

## 8. 收口腿读数（2026-11-07，与 §4 分列）

| 动作 | 命令 | 读数 |
|------|------|------|
| 协调面建桥 | `delivery_anchor.ensure_delivery_anchor(Path(worktree))` | `/Users/xiamingxing/Workspace/.omo/_delivery/agent-workflows`，run 面 410 条可见，本 run 记录 `present=True` |
| 补 claim | `agent-workflow.py claim <run> --path <retro> --path <receipt> --affected-hash runtime/affected/t342-closeout-receipt.json` | `claimed`，两把新锁落盘；台账路径由本 run 早先那次 claim 续期，未重复请求 |
| evidence 写回 | 按字段路径替换 `completion_evidence` 子块（`bets` 块尾边界取「顶格 `- `」与「顶格 `key:`」的较早者） | `+30/-6` 行，删除行 6 条全在旧子块内；写回断言：6 位 receipt 摘要 + 1 位 retro 摘要 == 磁盘字节、`content_digest` 仍等于 spec 摘要、顶层键序列不变、其余 589 条 bet 逐字未变、`len(bets)==meta.total_bets==590` |
| 置 done | `bet-ledger.py complete BET-Y2Q4-T10-342` | `✅ → done`，binding / matrix / `write_surfaces` tracked / chain 四道一次通过；台账 `status: done` `done_at: 2026-11-07` `overall_state: delivery_accepted` |

装置面一条如实记录：本 worktree 的 claim 是在 `gac-worktree.sh claim` 子模块 init 超时（300s）后
手工补齐的 —— `projects/omo` 与 `projects/ecos` 各按 pin 从本机 canonical 检出 `git fetch --depth 1 <本地路径> <sha>`
后 checkout（无网络、不改 remote URL），否则 `_work_packet_compiler()` 因 `projects/ecos/src` 缺席报
`WORK_PACKET_COMPILER_UNAVAILABLE`，`import omo` 因 `projects/omo` HEAD unborn 报 `ModuleNotFoundError`。
补齐后 `git submodule status projects/omo` 前缀为空格（与 pin 一致）。
