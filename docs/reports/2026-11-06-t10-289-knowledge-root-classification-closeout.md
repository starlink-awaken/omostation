---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-06
type: report
bet_id: BET-Y2Q4-T10-289
title: BET-Y2Q4-T10-289 收口收据 —— `.omo/_knowledge` 根归类裁决与两把尺的族闭合性
---

# BET-Y2Q4-T10-289 收口收据

工程腿 = PR #5074 squash `e2357d7e7d5f66b82cb12d2ff06ec57e5e34b7f7`（`2026-11-06T05:40:04Z` 入 main，4 件：
`.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`、`docs/plans/3y-bet-ledger.yaml`、
`tests/unit/test_resident_write_plane_split.py`、`tests/unit/test_writeplane_root_pin.py`；
`git diff --stat 8f04e272d e2357d7e7` = 568 insertions(+), 12 deletions(-)）。
分支 base = `8f04e272d51eb177b9d28f5e804c2bac56da0b4d`（起手时 `origin/main` tip，上游对本次 4 个路径零漂移），
交付按 lane 门禁（ADR-0122 §46）在分支上拆 4 个 commit：code `10ec4410b`、governance_state `1fbd5d1a7` +
测量面补正 `465116640`、docs_data `9029d7f95` —— squash 后这 4 个 sha 不在 `origin/main` 祖先图内，
只在交付分支上，引用时按「分支上的 lane 拆分」读。
契约：`docs/superpowers/specs/2026-11-05-knowledge-plane-root-classification.md`
（`content_digest sha256:c9ddcfd9bd260533a664a82eea22281a12088d2ed868cfa54224290851c782fd`，本轮未改正文）。
除 §2 最后一条外，所有读数由 base `8f04e272d` 产出（AGENTS.md §7「门禁的尺本身会随 base 变」）。

## 1. 交付内容（对照 done_when 四条）

| done_when | 落点 | 状态 |
|-----------|------|------|
| ① 按 §3 判别量逐面给结论（3 冲突面 + 容器 + 5 纯生成面 + 6 纯跟踪读面） | ADR-0456 addendum §1–§2（15 个面的裁决表） | 达成，并**超出** spec：判别量三行不闭合，补第四行（`hitl-proposals`）；`signals` 取**反处置** |
| ② pin-gate 排除面改按族，13 处入账、44 处保持「可见不计」 | 尺 B `_family_of`/`GATEABLE_FAMILIES`/`is_gated`/`knowledge_bucket`，`STATE_FAMILIES` 由尺 A 单源派生 | 达成，读数见 §2 |
| ③ 容器 5 站点裁决写明「改走具名面常量」或「显式声明双面」二者择一并给理由 | addendum §3：择「双面 + 按具名面枚举」，理由 = 同一 `rglob("*.md")` 同时跨跟踪文档与生成 `sediment/`，挂任一单根都必错 | 达成 |
| ④ 族表闭合性显式声明适用范围 + 后续判据 | addendum §6 + 尺 A `state_root_planes_without_family()`、登记面 `UNREGISTERED_STATE_ROOT_PLANES` 与三条用例 | 达成 |

## 2. 判据与读数

- **verify[0]（台账原文，hermetic）**：`HOME=$(mktemp -d) GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
  env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB uv run --no-project --with pytest
  --with pytest-timeout --with pyyaml python -m pytest tests/unit/test_writeplane_root_pin.py
  tests/unit/test_resident_write_plane_split.py -q -p no:randomly` ⇒ **51 passed，rc=0**（base `8f04e272d`）。
- **verify[1]（冲突面跟踪性）**：`/usr/bin/git ls-tree -r --name-only origin/main -- .omo/_knowledge/signals
  | /usr/bin/wc -l` ⇒ **7**，与 `git check-ignore --no-index -v` 命中 `.gitignore:424` 同时成立 ⇒
  「既跟踪又忽略」三面之一成立。
- **族门是承重的（不是加了就绿）**：同一份扫描（`scan_checkout_pinned_sites`，`sites_total=456`）分别在
  旧谓词（`marker in GATED_MARKERS`）与新谓词（`is_gated` = marker ∪ 族）下取数 ——
  **153/143/95 → 173/163/107**（sites/pairs/files），新增站点来自三个 marker
  （`.omo/_knowledge` 13、`.omo/_delivery` 6、`.omo/_truth` 1）。这条把 addendum §5 的「20 处不是新债，
  是既有站点第一次被计账」钉成可复跑读数。
- **「可见不计」未退化成「不可见」**：`knowledge_bucket` 三桶读数 **13 / 5 / 44**（`_knowledge` 62 站点全额），
  与 spec §2 定稿逐项相同；`GATEABLE_FAMILIES=39`（`STATE_FAMILIES=42` 摘掉两个通配与容器）。
- **闭合性判据的真实缺口**：`state_root_planes_without_family(OMO_SRC)` 返回 **2 面 3 站点**
  （`workflow-mesh/journey-states` 2 处 `root_state`、`.omo/debt/gap-items` 1 处），登记面与之**双向相等**。
  同一判据把入参换成仓库根得 **16 面**，多出的 14 面按档说明见 addendum §6 末表（`bin/` 生产 3 /
  根仓测试 4 / `projects/omo` 测试 7），本 BET 一条都没并进来 —— 范围边界见 §3。
- **治理门禁**：`doc-governance-check.py --no-new-warnings --scope tracked` PASS（4773 files，45 warnings）；
  `make gac-local-gate` PASS（69 checks，2 SOFT WARN）；PR #5074 CI 全绿（`bet-done-transition` 通过）。
- **circuit_breaker 未触发**：`git diff --stat 8f04e272d origin/main -- .gitignore .omo/_knowledge` 为空，
  三个冲突面在本腿窗口内未被并发交付摘库或补规则 ⇒ 裁决清单不摘项。
- **合并后在交付内容上复跑 verify[0]**：同一条 hermetic 命令在工程腿工作树（head `465116640`）⇒
  **51 passed in 38.90s，rc=0**（2026-11-06T05:52Z）。该树与 `origin/main@e2357d7e7` **整棵逐字节相同**
  （`git diff --name-only 465116640 e2357d7e7` 为空），所以这次复跑就是合并后 main 的读数；
  子模块 `projects/omo` 在该工作树已 init，故 `OMO_SRC` 口径成立；收口腿工作树用 `SKIP_SUBMODULE_INIT=1` 建，
  **不能**作复跑现场。

## 3. 偏离与承接（两条，都不在本轮写面内）

1. **AC-03 交付了裁决，没交付迁移。** spec AC-03 第三列与台账 `goal` 末句要求「收敛 13 个具体族读者中的
   10 处模块级常量」改调用时刻解析，这些站点全在 `bin/**`；而本 BET 的 `write_surfaces` 不含任何 `bin/` 路径，
   `done_when` 四条也没有一条是这次迁移。WorkPacket 的 `scope.write_surfaces` 是授权边界（AGENTS.md §1.4），
   擅自扩面等于把 principal 的 gate 变成事后通知，所以本轮 `bin/` 侧一行未改。
   addendum §4 已把 18 处读者按修法分成三类（纯读 6 / 遍历读 1 / 写 3 + 函数内 3 + 容器 5），
   其中 3 处写者是最实的缺陷（往 ignored 面的检出副本写，而尺 A 早把同族登记在 state 根 ⇒ 声明 profile 的
   机器上同族产物分池，且没有任何测试会红）。**承接方式应是一条新 BET**，其 `write_surfaces` 必须含
   `bin/**`，且 done_when 按 §4 三类逐项写 —— 否则下一轮仍是裁而不改。
2. **AC-04 三个冲突面一条未动。** 两条处置（摘库并显式跑生成者 / 删 ignore 规则承认跟踪面）都改跟踪面，
   spec 自己要求另行授权。`signals` 的方向已裁明（删规则而非摘库，三条实测支撑），执行腿仍须拿授权再碰
   `.gitignore`。addendum §2 的两条判据（1065 份的读者依赖、`_delivery`/`_truth` 后续项）是授权包里必须
   **附在动手前**的证据。

另登记一条未裁分叉：`bin/gac/check-test-host-hygiene.py:94` 读 `.omo/_truth/task-center/dispatches`，
trackedness 说检出读面、尺 A 族表说 state 族。本 BET 不裁（不属 62 站点扫描面），理由与「两棵树在此不等价」
写在 addendum §5。

## 4. 回滚

本轮四件全部是**判据与裁决**，无生产代码、无 plist、无 `.gitignore` 变更，回滚 = 一次 revert
（`e2357d7e7` 是 squash 产物、单亲 `8f04e272d`，所以不带 `-m 1`）：

```
git revert e2357d7e7d5f66b82cb12d2ff06ec57e5e34b7f7
```

回滚后的影响面（如实）：尺 B 回到按 marker 排除（门禁读数 173/163/107 → 153/143/95，20 个既有站点重新
不被计账），尺 A 失去闭合性判据（`journey-states` 这类缺口重新隐身），ADR-0456 失去 §1–§7 的裁决记录 ⇒
四个来源对同一目录的矛盾回到未裁状态。`projects/agora` 子模块在交付 worktree 工作树里显示 dirty，
**不是本次交付内容**，gitlink 未动（`git diff --name-status 8f04e272d..HEAD` 四行全为 `M`，零 `D`）。

## 5. 限制三条

1. addendum §2 的裁决按**字节来源**取（`ls-tree` + `check-ignore`），只覆盖 `origin/main` 这一棵树；
   声明 profile 的机器上生成面的实际落点未逐面跑过，只有 §2 里 `signals`/`hitl-proposals`/三冲突面是逐条实测。
2. 尺 A 闭合性判据的覆盖面是 `OMO_SRC`（`projects/omo/src/omo`），不是全仓；整仓那 14 面需要各自的
   面 owner 决定是否入族，本 BET 只点名不裁定（见 §2 末条）。
3. `knowledge_bucket` 的 62 站点数与 `SPEC_MARKER_READINGS` 表由同一把尺（尺 B）产出，
   与 spec §8 否证掉的旧草稿读数（25 文件/37 站点、36/26 二分）**不可比** —— 引用时一律用本轮 base。

## 6. 证据位

| 轴 | 项 | 指向 |
|----|----|------|
| engineering | merged_reachable_commit | `git://origin/main@e2357d7e7d5f66b82cb12d2ff06ec57e5e34b7f7` |
| engineering | tests / diff / rollback | 本收据（§2、§2、§4） |
| operational | live_canary | 本收据 §2 族门新旧谓词对照读数（153/143/95 → 173/163/107）+ 三桶 13/5/44 未退化 |
| operational | fresh_receipt | 本收据（base `8f04e272d` 现场复跑 + §2 末条合并后复跑） |
| operational | replay | `.omo/_knowledge/retros/BET-Y2Q4-T10-289.md` |
| operational | cleanup | 本收据 §4 回滚路径 + `runtime/affected/t289-impl.json` 为 claim receipt，未入库 |
| value | — | NOT_PROVEN（`value_indicator_policy: false`，与同族 281/282/284/288 同判） |
