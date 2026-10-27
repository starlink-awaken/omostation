---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-27
bet_id: BET-Y2Q4-T10-273
---

# BET-Y2Q4-T10-273 收口 receipt —— 把已经改对的写面钉进 B1 的两个既有名单

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-273`
规格：`docs/superpowers/specs/2026-10-27-bet-273-agent-brief-call-time-write-root.md`
工程腿：PR #4916 → squash `c2255b477b6e61dbf2ac88ea31d06a89190bfbbb`（分支 commit `31255305d` + `bb3284e0f` + `54b2a6680` + `65e9c6313`，3 文件 +226/−1）
收口腿：分支 `agent/governance-agent/t273-closeout`，run `20261027T033001Z-project-code-change-af216fe8`

## 0 归属先说清：本轮交付的不是根因

三件事分属三个 lane，顺序与证据如下 —— 本轮不认领前两件。

| 事 | 交付者 | 落点 | 实测读数 |
|---|---|---|---|
| 删除 `bin/panorama/materialize-agent-brief.py` 的 import 期写根常量（`OUT_DIR` / `AGENT_BRIEF_JSON`），改 `default_target()` 现算 | 并发 lane **PR #4913** | `4858eb530` | 检测器命中 **2 → 0** |
| 把 `bin/**` 补进 `governance-check.yml` 的 `on.push.paths` 与 `on.pull_request.paths`，并同步 `ci-surfaces.yaml` 的 `workflow_triggers` | 并发 lane **PR #4915** | `1917c669b` | 该 push 的 main run `40442337806` 结论 `success` |
| 把 `default_target` 登记进 `STATE_ENTRIES` 与 `LEGACY_SUFFIXES`（即该文件写根**方向**的尺） | **本轮** PR #4916 | `c2255b477` | 变异对照由「零红灯」变「当场红」 |

本轮原计划做第一件。发现 `4858eb530` 已在 main 上之后，把自己的等价改法**撤下**（PR #4914 标 superseded 关闭），
不拿一份拼写不同的实现去覆盖已定型的上游实现 —— 那是不增加任何门禁价值的 churn。

## 1 残余缺口及其规模

源码扫描只保证「没有 import 期常量」，不保证「落点在 profile 写根」。后者由 `STATE_ENTRIES` ×
`LEGACY_SUFFIXES` 两个既有名单驱动 I5（晚声明 profile 必须生效）与 I3（未声明时逐字节等于 legacy 落点）
两层参数化。`4858eb530` 没有登记这个 callable：

```
git show 4858eb530:tests/unit/test_b1_ledger_call_time.py | grep -c materialize-agent-brief  →  0
```

同一变异（把 `default_target()` 改成 `Path(__file__).resolve().parents[2] / …`，即退回检出根）在两个 base 各跑一次：

| base | 读数 |
|---|---|
| 未登记 `4858eb530` | `19 passed`（全绿；源码扫描也仍为 0 —— 没有任何尺会发现写面回到了检出根） |
| 已登记（本 head） | `1 failed, 6 passed`，失败 id 正是 `test_state_write_target_follows_profile_declared_after_import[bin/panorama/materialize-agent-brief.py-default_target]` |

⇒ **没有这两行登记，把一个已改对的写面重新改回检出根是零成本、零红灯的。**

## 2 交付面（承重只有 2 行）

```
2 0	tests/unit/test_b1_ledger_call_time.py          ← 承重：两条名单各一项（:59 与 :77）
86 1	docs/plans/3y-bet-ledger.yaml                   ← 台账开条（in_progress → done 于本收口腿）
138 0	docs/superpowers/specs/…bet-273-….md           ← 契约
```

- `STATE_ENTRIES` 追加 `("bin/panorama/materialize-agent-brief.py", "default_target")`
- `LEGACY_SUFFIXES` 追加同一键 → `"runtime/dashboard/agent-brief.json"`
- **未新建**任何平行清单或只扫本文件的用例；**未放宽**检测器、名单语义、`== set()` 三条既有判据。

## 3 验证读数（每行**自己标注**产出它的 base —— 工程腿 `4858eb530`，收口腿 `c2255b477`）

| 判据 | 读数 |
|---|---|
| `_frozen_write_targets(CHECKOUT/"bin", _profile_resolvers())` | `set()`（改前 base 为 2 条命中） |
| `pytest tests/unit/test_b1_ledger_call_time.py -q -p no:randomly` | `46 passed`；合并后在 `c2255b477` 上复跑仍 `46 passed` |
| 三条相关套件（B1 + `tests/unit/test_panorama_agent_brief.py` + `tests/bin/test_materialize_agent_brief.py`） | `76 passed` |
| `default_target()` 落点（未声明 profile） | `True` ⇒ `<检出>/runtime/dashboard/agent-brief.json`（I3 逐字节不变） |
| `make gac-local-gate`（**工程腿** base `4858eb530` + 本轮 staged） | `PASS (68 checks executed, 2 SOFT WARN)` |
| `gac-local-gate.py --scope staged --json`（**收口腿** base `c2255b477` + 本轮 staged） | `ok=False`，69 checks，3 条 failing —— 逐条诊断见 §5 第 6–8 项 |
| `bet-ledger.py lint` 中本 BET 条目 | `0` ERROR（改前该位是 `SPEC_DIGEST_MISMATCH`） |
| CI：本 PR run `40443945045` job `governance-verify` | `pass`；**step 7「ADR-0456 B1 call-time write-plane gate」= success** |
| CI：`gac-gate` / `interface-check` / `meta-doctor` | 全 `pass`（16 pass / 0 fail） |

台账 lint 一律按 BET id 分组数 ERROR 行，不 `tail -6`（见 §5 第 1–2 项）。合并后 main 上仍余 **5 条** ERROR，
全部点名 `BET-Y2Q4-T10-272` —— 那是 #4911 合入的既成事实，属它自己的收口腿，本轮不夹带。

## 4 done_when 六项对账

| # | 判据 | 状态 |
|---|---|---|
| 1 | `default_target` 进两个既有名单各一条，不新建平行清单 | ✅ `:59` / `:77`，diff 恰 2 行 |
| 2 | 变异对照：已登记当场红、未登记全绿（缺口规模） | ✅ `1 failed, 6 passed` / `19 passed` |
| 3 | 写面语义未变，落点仍 `state_root()/runtime/dashboard/agent-brief.json` | ✅ `True`（I3） |
| 4 | 该文件全文件在 base + 本轮改动上全绿 | ✅ `46 passed`（合并后复跑同值） |
| 5 | 本 PR 的 `governance-verify` B1 步为 pass 且不复红 | ✅ step 7 success（不靠 `--no-verify`／放宽判据／admin merge） |
| 6 | spec 落 canonical 位；本 BET 条目 lint 零 ERROR | ✅ `docs/superpowers/specs/…`；0 条（整体余 5 条属 T10-272） |

## 5 如实登记（共 8 项：3 次自伤 + 2 处装置限制 + 收口腿 gate 的 3 条读数诊断）

1. **开条模板抄了 lint 必红的形状**。首版 `status: PENDING` × 3 + `overall_state: in_progress` 是从台账里
   `BET-Y2Q4-T10-272` 抄来的，而 `bin/plan/bet-ledger.py:437` 的 `COMPLETION_AXIS_STATUSES` 不含 `PENDING`，
   `:1948-1971` 在这种三面组合下派生 `evaluating`。正确开条形 = `evaluating` + `IN_PROGRESS/NOT_PROVEN/NOT_PROVEN`
   + 三面 `evidence: {}`。**插条目工具拦不住它**：`bin/gac/ledger-safe-insert.py` 只校验 axes **键集**与
   `overall_state` 非空，**不校验 status 枚举** —— 这是一个独立的门禁缺口，已登记为本 BET 之外的候选固化 lane。
2. **把 lint 读数读反了**：第一次用 `tail -6` 看输出，据此在台账里写下「warnings only / no errors」，
   而实际有 5 条 `^ERROR`。判据改为按 BET id 分组计数，两处被否证的文案已在本轮改掉。
3. **抢跑了一次 closeout 并写错归属**：run `20261027T023631Z-project-code-change-8b7c5b38` 于 `03:14:38Z`
   被 `close --status ok` 且 evidence 写成 `["PR #4911 merged to main"]` —— #4911 是 **T10-272** 的工程腿，
   不是本 BET 的；它绑定的 spec 摘要 `0ba78916…` 也已被后续两次改版否证。该记录已闭合，**不改写**，
   此处按事实登记错标，并以本收口腿的 run `af216fe8` 作为 T10-273 的实际闭合凭证。
4. **装置限制一**：`gh api .../runs/<id>/jobs` 在本机对 run `40442337806` 连续 `EOF`，因此 #4915 那次
   复评的结论由两条合成（run 整体 `success` + 该步在 `governance-check.yml:265-268` 无 `continue-on-error`）。
   本 PR 自己的 run 则取到了逐 step 读数（step 7 success），不需要这层合成。
5. **装置限制二**：最小 `git archive <sha> bin tests/…` 对照树**不能**当 CI 替身 —— 该树按构造没有
   `docs/plans/3y-bet-ledger.yaml`，两条 ledger-db 用例因此与改动无关地红（实测 `3 failed`）。
   反基线读数必须在完整检出里产出。
6. **收口腿 gate 读数一（真缺陷，本轮已修）**：`change-lane-check --staged` FAIL
   `mixed lanes=docs,docs_data,governance_state` —— retro 属 `governance_state`，而
   `bin/change-lane-check.py:207` 对它做的是**硬隔离**（`len(lanes) > 1` 即拒），
   `{docs, docs_data}` 则在 `:19` 的允许组合里。处置：拆两个 commit（receipt+台账 / retro 单独），
   拆分后同一把尺读数 `PASS (2 files, lanes=docs,docs_data)`。
   **顺带测出的一条装置事实**：`:47-51` 的 `PUSH_RANGE` 分支在 `.githooks/` 里**没有任何导出点**
   （`/usr/bin/grep -rn PUSH_RANGE .githooks/` = 0 命中），所以「pre-push 按 commit 范围查 lane」这条
   ADR-4443 v9 机制当前是**未接线的**；也就是说 squash-merge 到 main 的那一个 commit 里三 lane 并存，
   没有任何尺会拦 —— 这与本条要防的形状正是同一件事的两面。
7. **收口腿 gate 读数二（host 面既成事实，本轮不修，需 principal 裁定）**：
   `service-config-drift` = `bin/mof/gen-service-configs.py --check` 报
   `com.omostation.agent-brief-materialize: plist 与 services.yaml 不一致 (drift)`。
   逐字节定位：注册表条目由 **`f4ab53dd0`（#4905，即本 BET 源码扫描命中的那两个 import 期常量的引入点）**
   加入且未声明 `generate: false`，而 `~/Library/LaunchAgents/com.omostation.agent-brief-materialize.plist`
   **不存在**（实测 `No such file or directory`）⇒ `:1061` 拿 `existing=""` 与渲染串比对，按构造必 drift。
   即**注册在案、机器上从未安装** —— 与台账外待办「morning-brief 注册在案但机器上从未安装」同形。
   本轮不夹带修复：两条出路都不在文档 lane 的授权面内 —— 要么 `--write` 往宿主 `~/Library/LaunchAgents`
   写 plist + `bootstrap`（本 BET `non_goals` 明令禁止，属署名准入），要么把注册表改成 `generate: false`
   （先例 #4796/#4798 与 T10-253 说明这类翻转走自己的 BET）。**判据**：该服务该不该在这台机器上活，
   是署名裁定；本轮只把读数与出处钉下来。
8. **收口腿 gate 读数三（T10-235 摘库的下游缺口，本轮不修）**：`current-state-coherence` rc=2
   `missing input: <worktree>/.omo/state/system.yaml`。对照实测：同一把尺在 canonical `~/Workspace`
   **rc=0**（那份文件存在，今日 11:27 由写者刷新），在**本 worktree 红** —— 因为 `.omo/state/system.yaml`
   自 T10-235 起被 `.gitignore` 正向忽略，新检出按构造没有它（AGENTS.md §7 已把「干净检出里没有这份文件」
   定为常态）。所以红的是**门禁读者的根**：它按 worktree 相对路径读，而不是按 `state_root()` /
   canonical 读。处置同第 7 项 —— 不在文档 lane 夹带；它属固化 lane 的一条具体候选（与
   `ledger-safe-insert.py` 不校验 status 枚举并列）。

## 6 rollback

本轮改动是**纯登记面**（2 行名单 + 文档），回滚即撤销对 main 的保护，不会改变任何运行态：

```bash
git revert --no-edit c2255b477     # 恢复：写根方向重新无尺；default_target 仍由 #4913 的实现现算
```

回滚后的预期读数：`git show <revert>:tests/unit/test_b1_ledger_call_time.py | grep -c materialize-agent-brief` = `0`，
`§1` 的变异对照重新落到「未登记」那一列（`19 passed`）。运行面零影响：不涉 plist / launchd / crontab / `services.yaml`。

## 7 遗留与边界

- `BET-Y2Q4-T10-272` 的 5 条 lint ERROR（`PENDING` × 3 + `in_progress` + policy 违规）留给它自己的收口腿。
- `ledger-safe-insert.py` 不校验 status 枚举 = 门禁缺口，另立固化 lane。
- 「本地 FAIL / CI PASS」的环境类分歧（`test_measure_value_truth_run_uses_the_db_declared_after_import`）
  已在**不含本轮改动**的检出上复现，不夹带修复。
- **合并前本 BET 有一条非阻断 WARN**（不是本轮引入的缺陷，是时间顺序的必然）：
  `PHANTOM_REPORT_PATH docs/reports/2026-10-27-bet-273-agent-brief-call-time-write-root-closeout.md`
  —— 判据是把 `write_surfaces` 与 `origin/main` 比对，而这份 receipt 正是在本次收口腿里才进仓的，
  所以合并前**按构造**不在 origin/main。判据读数因此分两段：本轮实测 `ERROR 5 条（全部点名 BET-Y2Q4-T10-272）
  + WARN 30 条`，其中指向本 BET 的只有这一条；合并后它应自动消失。同形先例 `BET-Y1Q4-T6-18` 至今挂着同一条 WARN。
- 本 BET 不判定 Agent Brief 物化器该不该活/该不该装；**不宣布 ADR-0456 B1/B3/B4/B4b/B5 或整个 plan 完成**。
