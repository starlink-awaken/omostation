---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-06
type: report
---

# BET-Y2Q4-T10-232 closeout receipt (2026-10-06)

Completion evidence receipt for BET-Y2Q4-T10-232 — ADR-0456 B1 残留：`bin/` 写面常量由 import 时求值
改为调用时刻解析（14 处：8 ledger + 6 state_root）。

## Delivery

- **omostation PR #4651** — `fix(repo-root): B1 残留 — 14 处 import 时冻结的写面常量改调用时刻解析`,
  merged 2026-10-06T09:44:17Z by **squash** as `317bc031541076b286b16bf6dd1049da8ab27564` (main).
  21 files, +1,065 / −71. CI at merge: 30 pass / 2 skipping / 0 fail（`governance-verify`、`gac-gate`、
  `evidence-gate`、`interface-check`、`meta-doctor`、`doc-freshness` 全绿）。
- **本 receipt + retro + 台账 evidence 回填** 走第二个 docs PR（无代码面变更）。
- 契约：`docs/superpowers/specs/2026-10-05-b1-import-time-ledger-constants-call-time.md`
  （`content_digest = sha256:179df14371177d7c…`，与 main 上的字节逐位复核一致）。
- 改号：交付原登记为 `BET-Y2Q4-T10-231`，与并发 agent 的同名条目相撞（对方已 `done`）。
  按 `docs/SOPs/ledger-closeout-sop.md` §3.6 把**自己的**交付整体改号为 232（9 处自引用 + digest 重算 +
  retro 改名），对方条目逐字节存活。squash 之后 commit message 里的 231 是历史文本，不可再改（见 Deviations）。

## Verification (real)

全部读数取自 **合并后的 main 检出**（HEAD = `317bc0315`），不是分支自测：

| # | 判据 | 读数 |
|---|------|------|
| verify-1 | `pytest tests/unit/test_b1_ledger_call_time.py tests/test_evidence_smoke_paths.py tests/unit/test_repo_root_profile.py` | **916 passed**，exit 0 |
| verify-2 | `/usr/bin/grep -rE "DEFAULT_(EVENT_)?LEDGER[[:space:]]*=" bin/ \| wc -l`（方案 line 138 字面判据，不经第二段管道） | **0** |
| verify-3 | `pytest tests/unit -k "north_star or weekly_value or episode_source or compound_attribution or resident_orchestrator or health_check or evidence_smoke or task_inventory or generate_brief"` | **20 passed, 1962 deselected**，exit 0 |
| verify-4 | `make gac-local-gate` | **PASS（68 checks executed, 1 SOFT WARN）**，exit 0 |
| canary | 独立于 pytest 的 live canary：先 import 模块，**之后**声明 `OMO_EVENT_LEDGER_DB` 与 `OMOSTATION_STATE_ROOT`，无参调用 14 个 resolver | **expect=14 got=14**（全部落在声明位置） |
| rollback | `git show 317bc0315 \| git apply -R --check` | exit **0**（104,962 字节补丁，sha256 `9b90a0cc59cf61462ae0bb97a7686dfa8db2c1695b56725e3eb0b4f08220b49f`） |

台账面：`bet-ledger.py lint` 无 ERROR；`meta.total_bets = 528 = len(bets) = len(set(ids))`（唯一性 0 重复）。

## done_when 逐条落点

1. **时机**（0 命中 + 不再模块级求值）— verify-2 = 0 + canary 14/14 双向坐实。
2. **正向落点**（import 之后声明 env 仍生效，且断言来自真实运行）— canary 是**运行**产物，
   14 个 resolver 全数覆盖；用例侧由 `test_b1_ledger_call_time.py` 的 `LedgerBroker.connect` 路径记录钉住。
3. **等价**（未声明 profile 时逐字节同历史布局）— `tests/unit/test_repo_root_profile.py` 断言（含在 verify-1 的 916 内）。
4. **自证**（detector 先按合成违规点名，再断言真实扫描为空 + 17 处 code 面反向不被命中 + 基线读数 14）— 用例内断言，
   本轮反基线读数：`git checkout origin/main -- bin` 后同一门禁 **35 failed / 9 passed**，还原后 44 passed。
5. **显式优先**（显式传参时解析器不被调用，计数断言）— 用例内断言。
6. **读面不动**（GOV_LOG/EVENTS_LOG/REGISTRY/WORKSPACE 类绑定留检出侧，一个移 + 一个不移）— 既有成对断言。
7. **判据可红**（管道每段匹配词须在真实文本命中一次；`grep -c` 后不接 `|| true`）— 已写入 AGENTS.md §7（随 #4651 合并）。

## Deviations

- **D1 · 改号的历史文本残留**：squash commit message 仍写 `BET-Y2Q4-T10-231`（5 条原始 commit 的正文被
  squash 拼接，改号 commit 只改文件不改前人已成的 message）。台账/spec/用例/workflow 注释/retro 五处
  活跃引用已全部为 232；commit message 属不可改历史，在此记账而非静默。
- **D2 · docs 面未 claim**：本 receipt、retro 与台账 evidence 回填未走 WorkPacket claim
  （BET 的 `write_surfaces` 只列 19 条代码面，`claim` 对这三条路径报 `WORK_PACKET_SCOPE_MISMATCH`）。
  依据：packet 校验只 gate `claim` 与子 run 继承，`status`/`done_at`/`completion_evidence` 不在投影里；
  同 BET 的 #4651 已在未 claim `docs/plans/3y-bet-ledger.yaml` 与 spec 的情况下通过 pre-commit 与 CI。
  ADR-0203 的「编辑前必须有 active run」由 run
  `20261006T043431Z-project-code-change-215cbf60`（code）与 `20261006T095145Z-project-doc-change-6bf85743`（docs）满足。

## Residuals（实测后登记，非遗漏）

- **写/读分裂（本轮新测）**：`bin/gac/check-evidence-freshness.py:21-22` 的 `EVIDENCE_DIR` 由 `__file__`
  反推（检出侧），而它检查的 receipt 现在由 `evidence-smoke._output_dir()` 写到 **state 根**。
  实测同一 profile 下两侧路径：`SPLIT = True`（writer → `<state>/.omo/_delivery/evidence-smoke`，
  reader → `<checkout>/.omo/_delivery/evidence-smoke`）。该分裂**先于本 BET 存在**
  （改前 `OUTPUT_DIR = runtime_state_root() / …` 已在 main 上，只是被 import 时冻结），
  本轮解冻让「profile 晚声明」真正生效，因而把它变成可达缺陷：门禁可能拿检出侧陈旧 receipt 判「新鲜」。
  与已知项 G9「freshness 检查首跑必绿」同族 ⇒ 需独立 BET（reader 侧改 `state_file_read` 语义 + 正向落点断言）。
- **omo 仓同类缺陷**：`projects/omo/src/omo/resident/daemon.py` 的 `DEFAULT_LEDGER` /
  `DEFAULT_EVENTS_JSONL` / `PID_FILE` / `LOG_FILE` 仍是 import 时求值，且根由
  `projects/omo/src/omo/resident/__init__.py` 的 `__file__` 反推；`omo_paths.STATE_ROOT` 同形。
  需 root+omo 双仓交付 + `OMOSTATION_PROFILE=dev` 实跑 `resident daemon --once` 验证只写 dev state 根。
- `bin/panorama/panorama-collect.py` 的 `EVENT_LEDGER` 由外部 dashboard 契约（`PANORAMA_ROOT` /
  `ZHIXING_DASHBOARD_CODE_ROOT`）驱动，残余风险仅在「只声明 `OMOSTATION_STATE_ROOT`」时指向检出侧。
- 17 处 code 面模块级绑定按 ADR-0456 保持检出侧（反向断言已钉住不被本门禁命中）；
  `bin/*/install-watch-agent.py` 的 `LOGS_DIR` 属 B4b 批次 2+ 改道面，**需逐批授权**。
