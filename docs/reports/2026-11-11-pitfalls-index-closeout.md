---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-11
type: report
bet_id: BET-Y2Q4-T10-346
title: BET-Y2Q4-T10-346 closeout — §7 索引条首短语的字面可命中门禁
---

# BET-Y2Q4-T10-346 收口收据

工程腿 = PR #5286 squash `519d0fc514018eb725084df54c4e1260bcf49107`（入 main，9 件）。
准入腿 = PR #5257 系列的铸单 BET 本体（台账条目 + spec 绑定），与本收据同 base 判读。
前置 PR #5285（同一 BET 的第一次交付）与上游 #5284 在 `AGENTS.md` 上 `CONFLICTING`，
按本仓纪律不 rebase/不 merge 吸收上游，改在新 base `b97281171` 上重新 claim 交付 ⇒ #5286。

本文件是 `completion-evidence-matrix/v1` 的 diff / rollback / tests / fresh_receipt /
live_canary / replay / cleanup 七项载体。**全部读数在合并后的 main 上重取**（base
`519d0fc51`，隔离工作树 `ws-t10346-closeout`），不引用工程窗口里的历史笔记。

## 交付

| 件 | 内容 |
|---|---|
| `bin/gac/check-pitfalls-index.py` | 门禁本体。stdlib-only；判据 = §7 表行内 `「…」` 短语在 `docs/pitfalls.md` 正文里的字面存在；`ENFORCE_AFTER = 2026-12-12` 前 `dead>0` 恒 exit 0（advisory），`--strict` 为提前转阻断的变异证明开关；JSON 十字段 |
| `AGENTS.md` | §7 速查表内 16 条索引短语改写为正文可字面命中的原文片段（`git diff --stat` = 4 插 4 删，全部落在表行内） |
| `docs/pitfalls.md` | **未改动**（字节数两侧同 = 191252）；本 BET 的边界是不动正文 |
| `tests/unit/test_check_pitfalls_index.py` | 6 条用例，全部 tmp_path 内构造 AGENTS.md/pitfalls.md，不读 canonical 真文件 |
| `.omo/_truth/registry/governance-checks.yaml` | `CR-X2-PITFALLS-INDEX-INTEGRITY`（`source_ref` 指脚本、`executor: [ci_gate, gac_local_gate]`、`review_before: 2026-12-12`）；`gac.subtraction_quota.script_baseline` 741→742 |
| `.omo/_truth/registry/ci-surfaces.yaml` | 一条 `tool: bin/gac/check-pitfalls-index.py`（`workflow: gac-gate.yml`、`gate: false` 到限期） |
| `bin/gac/gac-local-gate.py` | root-owned append 段新增 gate `pitfalls-index`（**不是** `DEFAULT_POLICY`，见「判读要点」第 1 条） |
| `bin/_registry/scripts/governance/check-pitfalls-index.yaml` | 第二处登记面（`script-registry/v1`），缺它则 `script-registry-validate` 红 |
| `docs/superpowers/specs/2026-11-10-pitfalls-index-integrity.md` | spec；台账以 `sha256:57de51c0…` 绑定 |

## done_when 逐条对账

| # | 判据 | 实测（合并后 main，base `519d0fc51`） |
|---|---|---|
| AC-01 | gate 在修复前的 main（`b97281171`）读出 `total=45 dead=16` | 用 `git show b97281171:AGENTS.md` + `git show b97281171:docs/pitfalls.md` 造沙箱、以同一脚本 `check()` 复现：`total=45 dead=16 hittable=29 body_entries=125 ok=False`；死指针含 `重复判据的 $HOME 盲区`、`YAML 日期字段的装载类型才是契约`（正文条首实为 `YAML 日期字段的「装载类型」才是契约`） |
| AC-02 | 修复后 `dead=0` 且 `docs/pitfalls.md` 字节数不变 | 同沙箱 post：`total=45 dead=0 hittable=45 body_entries=125 ok=True`；`wc -c docs/pitfalls.md` = **191252**（与 pre 一致，只动 `AGENTS.md`） |
| AC-03 | 限期前 advisory 恒 exit 0；近义改写后 `--strict` 立即 rc≠0；还原后字节一致 | 沙箱内把 `未初始化子模块 \`git -C\` 向上解析` 改成近义句 ⇒ advisory `rc=0, dead=1, blocking=false` ⇒ `--strict` `rc=1, dead=1, blocking=true` ⇒ 由 `git show origin/main:AGENTS.md` 还原后 `sha256` 与变异前相同（`ecfbb202cbd97c47…`）、`--strict` 回到 `rc=0`。全程未触碰交付树；沙箱已删 |
| AC-04 | 6 条用例全绿、全在 tmp_path 内 | `uv run --with pytest --with pytest-timeout python -m pytest tests/unit/test_check_pitfalls_index.py -q` ⇒ **6 passed in 0.03s** |
| AC-05 | 规则有 `source_ref` 且 ci-surfaces 有执行接线 | `source_ref = bin/gac/check-pitfalls-index.py`、`executor = [ci_gate, gac_local_gate]`；`ci-surfaces.yaml:45` 该面 `workflow: gac-gate.yml` / `status: active` |

## 判读要点（本 BET 的三条真实收获）

1. **`DEFAULT_POLICY` 不是执行面**。`gac-local-gate.py` 的 `POLICY = load_sgf_policy() or DEFAULT_POLICY`
   实际策略来自 ecos 子模块的 `sgf-policy.yaml`（78 gates）；`DEFAULT_POLICY`（L38–370）是永不生效的回退副本。
   把 gate 写进它是「注册了但没人执行」的成因，不是接线。本次写进 root-owned append 段（L537–542）。
   运行时自证：`importlib` 加载执行器后 `RUNTIME_GATES = 90`，`check-pitfalls-index.py` 在其中 ⇒ 本地门禁真的执行它。
   同形状的两条既有规则 `CR-X2-GATE-DETAIL-CONTRACT`、`CR-X2-CRON-INTERP-EXECUTABILITY` 仍只在 `DEFAULT_POLICY`
   字面量里（分别 L251、L243），**未**进运行时 `GATES_LIST` —— 见「残留」。
2. **新增 `bin/` 脚本有两处登记面**：`script_baseline`（741→742）与 `bin/_registry/scripts/**`。
   互证读数：`script-registry.py validate` ⇒ `VALIDATION PASSED: 742 scripts registered`，与 baseline 同值。
3. **判据口径要写清「命中」是什么**。脚本判 `phrase not in body_text`（正文任意位置的字面子串），
   而契约名叫「条首短语」。两者不等价，实测差额见「已知限制」第 1 条。

## CI 与合并

`gh pr checks 5286`：`gac-gate`、`gac-gate-aux`、`governance-verify`、`integration (3.13)`、`meta-doctor`、
`interface-check`、`evidence-gate`、`bet-done-transition`、`documents-changes`、`doc-index`、`debt-audit`、
`ai-review`、`omo governance audit`、`phase-gate`、`guard`、`check` 全 pass；`doc-freshness` /
`Documents domain projects` 为 skipping（本 PR 只动文档与治理面）；`mergeable=MERGEABLE`、
`mergeStateStatus=CLEAN` 后 squash 合并。

## operational 轴

- `live_canary`：在**新 claim 的隔离工作树**（`519d0fc51` base，与工程腿不同检出）上跑门禁与执行器导入，读数同上 ⇒ 合并态在干净检出上可复现，不是只在工程树里成立。
- `fresh_receipt`：本文件（在合入后的 base 上重取全部读数）。
- `replay`：AC-01/AC-02 的 pre/post 对照由 `git show <rev>:<path>` 的 blob 构造，尺与工程腿同一把（同一脚本、同一 `check()`）。
- `cleanup`：变异/回放沙箱 `/tmp/gdc/replay346/mut` 已删；工作树内无残留（`git status --short` 除子模块 gitlink 与 `.subtrees/` 外为空）。

## 已知限制与残留（不在本 BET 范围，如实登记）

1. **条首锚定率 25/45**：门禁判「正文任意位置字面存在」，实测 45 条短语中 **20 条不是任何条目头（`^\s*- \*\*`）的前缀**——
   人按索引 `rg` 会落在正文中段而非条首。这正是本仓 2026-11-10 刚固化的形状
   「判据描述的是『代码属性』，实现却打在文件全文上」，门禁自身复发。收敛需另案（改判据即触
   `circuit_breaker`：不得为让 gate 绿而放宽判据，反之加严也要新 BET 承接）。
2. `CR-X2-GATE-DETAIL-CONTRACT` / `CR-X2-CRON-INTERP-EXECUTABILITY`：注册且声明 `gac_local_gate`，
   但只在 `DEFAULT_POLICY` 文本里 ⇒ 长期零执行；且 `check-ci-surfaces.py:121` 的正则把整个
   `gac-local-gate.py` 文本里的 `bin/*.py` 字面量当「本地门禁工具」（实测 87 条），把这两条判成已接线 = 假绿。
3. `bin/gac/check-rule-wiring-coverage.py` 的判据是「规则 id 出现在执行语料的**文本**中」
   （`declared=94 / wired=76 / unreferenced=0`），因此对第 2 条这类「文本提到但不执行」结构性失明。
4. `CR-X1-GOD-MODULE-LIMIT` / `CR-X2-GOD-MODULE-EDIT` 的 `source_ref` 写 `bin/gac/check-god-module.py`，
   真实文件在 `bin/ssot/check-god-module.py`（目录写错，且该文件在 workflow/hook/sgf-policy 三处均未接线）。
5. 4 条 `CR-SEC-*` 声明 `bin/ssot/check-*.py` 不存在，实现内联在 `bin/gac/gac-hook-pre-edit.py`（`hook_pre_edit` 生效，`source_ref` 陈旧）。
6. PR #5285 仍 OPEN（已被 #5286 取代，已挂「请勿合并」评注），关单在本收据合并后执行。
7. 本机 `make gac-local-gate` 在本工作树另有两项 host/worktree 态读数不参与本对账：
   `current-state-coherence`（缺 `.omo/state/system.yaml`，运行态产物，WARN）与
   `check-evidence-freshness`（`import_failed`）——与本交付面零交集，且后者在 canonical 为 PASS。
