---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-07
type: report
bet_id: BET-Y2Q4-T10-292
title: BET-Y2Q4-T10-292 收口收据 — A2A 路径冲突谓词补锁过期判据（PITFALL-COO-008 承接）
---

# BET-Y2Q4-T10-292 · 收口收据

> 对象：`claim_run()` Phase 3 的 A2A Path Lock Collision 谓词补「锁过期」判据。
> 规格：`docs/superpowers/specs/2026-11-06-a2a-collision-lock-expiry.md`（sha256 `61ea3f8a941d8d1e9426a2db196011abc714b603dd342ab364b6494bb2e7548f`，与台账 `accepted_specifications[0].content_digest` 逐字节一致，本轮未改动规格正文）。
> 关联：PITFALL-COO-008；前置条目 BET-Y2Q4-T10-291。

## 1. done_when 逐条对账

| # | 条款 | 读数 | 判定 |
|---|------|------|------|
| 1 | 正例成立 + 同一装置改成未过期当场红 | 正例 `test_claim_admits_foreign_active_run_whose_lock_expired` 绿；反例 `test_claim_still_blocks_foreign_active_run_whose_lock_is_live` 绿；变异 M1（只查 status）→ **2 failed** | 成立 |
| 2 | 心跳宽度成立 + 复用 `_classify_existing_lock()` 当场红 | `test_claim_blocks_on_stale_heartbeat_with_live_expiry` 绿（且断言该锁分类为 `zombie_stale_heartbeat`，即「心跳已过但锁未过期」这一形状被正面点名）；变异 M3 → **3 failed** | 成立 |
| 3 | fail-closed 四面 + 改成放行当场红 | 交付面为 8 个而不是 4 个（补 `expires_at: null`、naive 时间戳、payload 非 mapping、无 `scope`）：`test_claim_fail_closed_when_expiry_cannot_be_proven[*]` 8 例全绿；变异 M2（fail-open）→ **11 failed** | 成立 |
| 4 | 零回归：既有 38 条在同一 hermetic 装置下仍全绿 | 改动前基线复算 **38 passed**；改动后 **54 passed**（38 既有 + 16 新增） | 成立 |
| 5 | 实机 canary：交付后真实共享协调面 claim 成功，且该记录逐字节未动 | RC=2 → RC=0；他主记录 sha256 前后均 `b98677b1b1632d9b7f09848c199904b58b2c63a285515f6c03beb5b89a4fa7b8`（见 §3 原文与勘误） | 成立 |

## 2. hermetic 装置与读数

装置（`projects/omo` 目录内）：

```
env HOME=$(mktemp -d) UV_CACHE_DIR=$(mktemp -d) GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
  uv run --no-project --with pytest --with pytest-asyncio --with pyyaml \
  python -m pytest tests/test_workflow_locks.py -q -p no:randomly
```

- 改动前基线（`projects/omo` @ `3f52c6b`）：**38 passed**
- 码面交付后（`af4ebdd`）：**54 passed**
- 根侧 pin 复算（`6605647`，即本 PR 携带的 gitlink，含另一条 resident 修复）：**54 passed**

全量面（深检出、四个 path 源齐全，`uv run --frozen python -m pytest tests`）：**3182 passed**。
同批 claim 相关三文件 **226 passed**。

`tests/unit/test_observability.py` 在 `HOME=$(mktemp -d)` 隔离下 4 failed（KEI 审计数据缺失类断言），
用宿主 env 复跑同文件 **6 passed** ⇒ 属 AGENTS.md §7「用例断言 host 运行态」类的预存非 hermetic 用例，
不是本 BET 引入的回归；本 BET 未触碰该面。

## 3. 缺陷原文的复现与放行（实机 canary）

对象：真实共享协调面 `.omo/_delivery/agent-workflows/`（经 symlink 桥与 canonical 同一 inode）。
他主记录 `20261104T115230Z-project-code-change-d825f60f`：`status: active`、
`created_at 2026-11-04T11:52:30Z`、`claims[0].paths` 含 `docs/plans/3y-bet-ledger.yaml`、
**`last_heartbeat` 字段缺失（null）** —— 这一点单独值得记：旧谓词只看 `status`，而该记录连心跳都
没有可比的值，所以「用心跳替代锁 TTL」在这里连退路都没有。
该 scope 上的锁按缺省 `runner.lock_ttl_hours = 24` 计算，到期于 `2026-11-05T11:54:48Z`，
canary 时刻（`2026-11-07T00:04:39Z`）已过期约 **36 h**（条目文本写的「35 h」是更早的诊断时刻读数）。

BEFORE（同一装置，临时摘掉放行分支 = 变异 M1，跑完立即还原并断言与 HEAD 逐字节一致）：

```
$ uv run --with pyyaml python bin/agent-workflow.py claim \
    20261106T234649Z-project-code-change-426df72d \
    --path docs/plans/3y-bet-ledger.yaml \
    --affected-receipt runtime/affected/t292-receipt.json
agent-workflow: A2A Path Lock Collision: path 'docs/plans/3y-bet-ledger.yaml' overlaps with active claim 'docs/plans/3y-bet-ledger.yaml' in run 20261104T115230Z-project-code-change-d825f60f
RC=2
```

AFTER（交付代码，同命令同装置）：`RC=0`，claim 返回的 `paths == ["docs/plans/3y-bet-ledger.yaml"]`、
`scopes` 含 `path:docs/plans/3y-bet-ledger.yaml`；锁 `run_id` 易主为本 run，
`created_at 2026-11-07T00:04:39Z`、`expires_at 2026-11-08T00:04:39Z`。

他主记录未被触碰的证据：`shasum -a 256` 在 canary 前、后各测一次，
同为 `b98677b1b1632d9b7f09848c199904b58b2c63a285515f6c03beb5b89a4fa7b8`（与 `/tmp/t292-before-runsha.txt`、`/tmp/t292-after-runsha-before.txt` 两份存档一致）。

## 4. 变异对照（三次分别记读数）

| 变异 | 改法 | 读数 | 解释 |
|------|------|------|------|
| M1 | 删掉 `if f"path:{op}" in expired_lock_scopes: continue`（回到「只看 status」） | **2 failed, 52 passed** | 红的是两条正例（直接放行 + 父锁过期的层次方向），其余全绿 ⇒ 放行分支只由这两条承重 |
| M2 | 谓词改成 fail-open（不可证明即放行） | **11 failed, 43 passed** | 8 个 fail-closed 面 + 未过期活锁反例 + 心跳宽度 + 层次方向。其中若干条实际由 `acquire_locks()` 的 `lock HELD (live)` 拦下 ⇒ 锁层是第二道网，run 记录层的保守性不能因此省掉 |
| M3 | 判据复用 `_classify_existing_lock()` 的分类结果 | **3 failed, 51 passed** | 含该尺自身在 `lifecycle_locks.py:88` 抛 `TypeError: can't compare offset-naive and offset-aware datetimes` ⇒ 「不复用心跳规则」不是偏好，是有实测故障模式 |

三次「改法 → 读数」都不同，说明断言不是按构造就绿（AGENTS.md §7③ 的反面要求）。

## 5. 独立尺 `observe --json`

| 时刻 | 读数 |
|------|------|
| 基线 `4c662cdbb`（交付前） | `expired_lock = 7`、`lock_count = 7`，含 `path_docs_plans_3y-bet-ledger.yaml.lock.yaml` |
| canary 后（交付后） | `run_count = 408`、`lock_count = 9`、`expired_lock = 6`、`ok = false`、`decision = escalate` |

exit 非 0 由剩余 **6 条他主过期锁**导致，那 6 条属别的 agent 的 run，本 BET 非目标明令不碰
（不替并发 agent 拆锁、不用 `prune-locks`）。因此放行判据不是 exit code，而是「helper 与
observe 对同一条台账锁给出同向读数」：交付前两边都判该锁过期（observe 列出它，helper 的集合
含 `path:docs/plans/3y-bet-ledger.yaml`，claim 因此放行）；交付后该锁由本 run 以新 TTL 接管，
两边都判它未过期。`verify[1].expect` 已按此口径订正（原措辞要求交付后仍是 7/7，按构造不可达），
只改 `expect`——`cmd` / `done_when` / `write_surfaces` 逐字节未动，WorkPacket hash 复算不变
（`sha256:777a3fbfe608fb377521b9e4b85c6d2b1bd7adaa883102a0b4f97f8be3a16958`，与 run 记录存值一致），
所以后续 claim 不会 `WORK_PACKET_SOURCE_DRIFT`。

## 6. 交付链

| 环节 | 标识 |
|------|------|
| omo 码面 PR | #238，squash 为 `af4ebdd1fe6323966c14dd78d59eb7f17731ba98`（lint / test / test-cov 全绿） |
| 根侧第一版 PR | #5096 —— base `4c662cdbb` 与上游 gitlink bump 冲突（`mergeable=CONFLICTING`），标注 superseded 关闭 |
| 根侧受控后继 PR | #5098 —— base `4eba1b9e4361baa0a73470e1f6ec3e9beb716fb3`，只带 ledger + spec；gitlink 已由上游 #5097 bump 到 `66056471e61d1dbc2a4e58270150f59d86c2215f`（`af4ebdd` 的后代），本 PR 不再改 gitlink |
| 根侧合并 SHA | `e7c4692d194e5da86766e5a9b020e79ed8b54bea`（2026-11-07T00:37:09Z squash；`statusCheckRollup` 实测 17 条 = 15 SUCCESS + 2 SKIPPED + 0 FAILURE，含 governance-verify / interface-check / meta-doctor / evidence-gate / bet-done-transition） |

## 7. 残余面（已测量，未处理）

**首次放行之后，重放同一条 claim 会被同一条陈旧记录再次挡住。** canary 之后我用同一装置复跑
`claim --path docs/plans/3y-bet-ledger.yaml`，读数 RC=2，报错原文与 BEFORE 一致。原因：他主记录
仍是 `status=active`，而该 scope 上的锁此刻由**我自己的 run** 以 24 h TTL 持有（不在「已证明过期」集合）。

- 这不是本轮引入的失效：改动前首次 claim 就被挡，重放同样被挡，本轮只把首次 claim 放开。
- 但本轮只消除了 PITFALL-COO-008 的一半：谓词承认「锁过期」，还不承认「锁在我手里」。
  按 A2A（agent-to-agent）语义，锁的持有者即发起方时冲突对象并不存在。
- 不在本轮处理的原因：规格摘要已绑定在 `accepted_specifications[0].content_digest`，
  扩语义要改契约；且根 CI 当时正对着具体 SHA 评审，中途换码面会使在途评审失效。
- 后续承接方向：判据补 `lock_scopes_held_by(lock_dir, run_id)`，fail-closed 口径同本轮
  （不可证明「是我的锁」即算冲突）。

## 8. 清理

- `runtime/affected/t292-receipt.json`（affected-graph receipt，claim 前置项）用毕删除，不入 commit。
- worktree `ws-t292-a2a-lock-expiry` 与分支在收口腿合并后释放。
- 变异实验的备份 `/tmp/t292-lifecycle.bak`、`/tmp/t292-live-lifecycle.py` 属本机临时件，
  码面在每次实验后都按 `git show HEAD:…` 逐字节断言还原，`git -C projects/omo status --short` 为空。
- 未动面：`acquire_locks()` / `_classify_existing_lock()` / `prune_stale_locks()` /
  `runner.lock_ttl_hours` 缺省 / 任何他人 run 记录与他人锁（6 条过期锁按非目标保留）。
