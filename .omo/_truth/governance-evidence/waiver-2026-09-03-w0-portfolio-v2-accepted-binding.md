---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: history
created: 2026-09-03
last_updated: 2026-09-03
value_indicator_policy: false
title: W0 Portfolio/BET v2 accepted binding bootstrap waiver
type: doc
---

# W0 Portfolio/BET v2 Accepted-Binding Bootstrap Waiver

## Principal response

> 批准 W0 Portfolio/BET v2 accepted-binding proposal SHA-256 `26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100` 第4—15节及第16节完整授权原文。

## Approved Section 16 authorization, verbatim

> 本次 W0 Portfolio/BET v2 accepted-binding 自举跳过 workflow start，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；权威书面设计为 `/Users/xiamingxing/Documents/学习进化/基建架构/2026-09-03-vision-to-bet-portfolio-v2-design.md`，SHA-256 `cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b`，并批准 `/Users/xiamingxing/Documents/学习进化/基建架构/2026-09-03-w0-portfolio-v2-accepted-binding-proposal.md` 第 4—15 节原文；仅限新建第 4 节列明的八份 repository accepted Spec、`docs/plans/3y-bet-ledger.yaml` 仅新增 `BET-Y1Q4-T1-03`、`BET-Y1Q4-T1-04`、`BET-Y1Q4-T1-05`、`BET-Y1Q4-T1-06`、`BET-Y1Q4-T1-07`、`BET-Y1Q4-T1-08`、`BET-Y1Q4-T8-04`、`BET-Y1Q4-T1-09` 八个 candidate 条目，以及 `.omo/_truth/governance-evidence/waiver-2026-09-03-w0-portfolio-v2-accepted-binding.md` 记录本句；八份 Spec 均为 `spec_version: 1.0.0`、`status: accepted`、绑定各自唯一 BET、`implementation_authorized: false`，每个 BET 恰好一个四键 accepted binding，初始 engineering=`NOT_STARTED`、operational/value=`NOT_PROVEN`、overall=`evaluating`、`value_indicator_policy=false`、`human_gate=true`；首次 binding 允许使用第 7 节 `portfolio_binding.schema_state: bootstrap_unenforced`，但不得宣称 Portfolio v2 enforcement 已启用；不得修改任何既有 BET、status、depends_on、accepted binding、completion/value evidence、W1–W6、实现计划、代码、测试、projection、gitlink、任何既有 PR、workflow、lock、运行态或用户配置；#2950 未 settled、main guarded double-read 不一致、ID/path writer 冲突、既有 BET 对象发生变化或 required check 不全绿时必须停止；从当时最新 main 建唯一 independent-clone PR，完成 full recursive checkout、十路径精确 diff、八份 Spec digest、Ledger 零既有对象变化、DAG、必要 gate、独立 review、required checks 与 exact-SHA post-merge 验证后合并并合规退役 clone；合并后停止，不进入 writing-plans 或 implementation。

## Principal amendment response, verbatim

> 批准 W0 Portfolio/BET v2 binding consistency amendment SHA-256 `5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409` 第2—10节及第11节完整授权原文。

## Approved amendment Section 11 authorization, verbatim

> 批准 W0 Portfolio/BET v2 binding consistency amendment 第2—10节原文：W0 required Milestones 明确为 Contract、Migration、Product、Canary 四个；bootstrap Objective/KR 仅限 `OBJ-TRUST`、`OBJ-HOLDABILITY`、`KR-TRUST-CHAIN-COVERAGE`、`KR-HOLDABILITY-ORPHAN-BETS` 及第3节映射；所有 accepted Spec 仅建立 binding identity，不授权 writing-plans 或 implementation；waiver 本地检查只记为 non-durable observations；八份 Spec 补齐第6节要求的反指标和 Decision Log；Parent 按第7节移除活动文档中的易漂移计数；T1-04 按第8节采用 compatibility→单字段 `meta.total_bets` 修复→strict 的顺序，并仅把该单字段加入其未来 write-surface；允许在原十路径未提交 diff 内更新对应 Spec、八个新 BET contract/binding/digest 与原 waiver，不增加本次 repo 路径，不修改既有 BET、W1–W6、实现代码、测试、projection、gitlink、任何既有 PR 或运行态；#2963 或任何 Ledger writer 未 settled、latest-main 或授权摘要漂移、required check 不全绿时继续等待或停止，不得扩大范围。

Approved amendment source:
`/Users/xiamingxing/Documents/学习进化/基建架构/2026-09-03-w0-portfolio-v2-binding-consistency-amendment-proposal.md`.

The approved Decisions A–F are applied within the original ten-path scope:
four required W0 Milestones; the bounded Objective/KR vocabulary and mapping;
binding-only authority; non-durable local observations; explicit anti-metrics
and Decision Logs; removal of volatile Parent counts; and T1-04's staged
compatibility → separately claimed `meta.total_bets` repair → strict contract.

## Principal T8 ID collision amendment response, verbatim

> 批准 W0 Portfolio/BET v2 T8 ID collision amendment proposal SHA-256 `1a6a63d4fc20b6d3f385b27518018fdb633e5cd38ee9c171db1c08773eecd992` 第2—7节及第8节完整授权原文

## Approved T8 ID collision amendment Section 8 authorization, verbatim

> 批准 W0 Portfolio/BET v2 T8 ID collision amendment：因 main 已由 #2977 占用 `BET-Y1Q4-T8-04`，仅将尚未提交的 W0 Cockpit Portfolio child 改为当前未占用的 `BET-Y1Q4-T8-05`；允许在原十路径内更新 Parent/Cockpit Spec 的该 child 引用与 collision-amendment SHA、八个新 W0 Ledger 对象中的对应 ID、decision/depends_on/done_when/retro 引用及受影响 digest，并在原 waiver 追加本批准句、第8节完整原文、有效 ID 与 digest；原 §16 和 consistency amendment §11 引文保持原文，main 既有 `BET-Y1Q4-T8-04` 及其他既有 BET/顶层 Ledger 字段不得修改；其余七个 W0 ID、DAG 语义、四 Milestone、Objective/KR mapping、十路径、candidate/evaluating/NOT_STARTED/NOT_PROVEN、human gate、value policy 与 binding-only 边界保持不变；所有 writer settled、latest-main 双读、ID/path collision、结构/digest/WorkPacket/gate/review/required-check/exact-SHA/retirement 条件仍必须满足，本句不授权 writing-plans、implementation、W1-W6、代码、测试、projection、gitlink 或运行态。

## Canonical workflow waiver evidence

waiver: user-explicit

when: 2026-09-03T06:15:02Z

who: xiamingxing

quote: "批准 W0 Portfolio/BET v2 accepted-binding proposal SHA-256 `26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100` 第4—15节及第16节完整授权原文。"

approved_full_authorization: see the verbatim Section 16 block above

gate_bypass: 1

no-run-id: true

reason: The W0 parent and seven child BETs do not exist before this atomic
  binding, so a BET-bound requirement workflow cannot start without the
  approved self-bootstrap.

risk: The bootstrap has no workflow run, claim, or lock. Exact paths, immutable
  source-design/proposal digests, eight frozen Spec digests, structural
  existing-BET equality, independent clone provenance/readiness, review, and
  required checks are the compensating controls.

residual: The resulting BETs remain candidate/evaluating with engineering
  NOT_STARTED and operational/value NOT_PROVEN. Portfolio v2 enforcement,
  writing-plans, implementation, migration, projections, W1-W6, completion,
  and personal value remain unauthorized by this binding.

## Approved source identity

- Documents design SHA-256:
  `cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b`.
- Documents accepted-binding proposal SHA-256:
  `26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100`.
- Documents binding consistency amendment SHA-256:
  `5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409`.
- Documents T8 ID collision amendment SHA-256:
  `1a6a63d4fc20b6d3f385b27518018fdb633e5cd38ee9c171db1c08773eecd992`.
- Delivery root main:
  `15cf2b62001e64d34a5acca79d6e58872c4e765d`.
- Actor: `portfolio-v2-governance`.
- Delivery attempt: `w0-accepted-binding-20260903-04`.
- Clone:
  `/Users/xiamingxing/agents/portfolio-v2-governance/attempts/w0-accepted-binding-20260903-04/ws`.
- Lifecycle profile: `full`; recursive checkout completed.
- Provenance status/digest:
  `ready` /
  `67727dc08fbb94e80c2a93262cb1f97c559ffc159440b3b5f8f3f9b4986c529e`.
- Readiness status/digest:
  `ready` /
  `576b1ae0bb2f9b50e64da4c03f09ad75e9b31b4784baf4da86526ad4cac20599`.

## Exact repository scope

1. `docs/superpowers/specs/2026-09-03-vision-to-bet-portfolio-v2-design.md`
2. `docs/superpowers/specs/2026-09-03-w0-portfolio-v2-schema-compatibility-design.md`
3. `docs/superpowers/specs/2026-09-03-w0-portfolio-coverage-graph-critical-path-design.md`
4. `docs/superpowers/specs/2026-09-03-w0-portfolio-milestone-vision-gates-design.md`
5. `docs/superpowers/specs/2026-09-03-w0-portfolio-legacy-bet-migration-design.md`
6. `docs/superpowers/specs/2026-09-03-w0-portfolio-projections-design.md`
7. `docs/superpowers/specs/2026-09-03-w0-cockpit-portfolio-view-design.md`
8. `docs/superpowers/specs/2026-09-03-w0-portfolio-dogfood-canary-design.md`
9. `docs/plans/3y-bet-ledger.yaml`, limited to adding exactly eight W0 BET objects
10. this waiver evidence file

No other repository or external path is authorized.

## Effective T8 child identity override

The original approved §16 quote above is retained verbatim as historical
authorization. The later approved collision amendment supersedes only its
planned W0 Cockpit child identity:

- occupied existing main identity, immutable and out of scope:
  `BET-Y1Q4-T8-04`;
- effective new W0 Cockpit Portfolio child: `BET-Y1Q4-T8-05`.

No ninth W0 object is added and no existing `BET-Y1Q4-T8-04` byte is changed.

## Frozen accepted Spec identities

- `BET-Y1Q4-T1-03`:
  `sha256:21edafde541cde6473c27bbc330ffb9beda072e1fd7952cb7f7f21df40b4fc52`
- `BET-Y1Q4-T1-04`:
  `sha256:208898d141fe920882a426b76b32d148734fe87c734acaf59fecc9c5df330cb5`
- `BET-Y1Q4-T1-05`:
  `sha256:27b93936399c3d7ff895c82ffe85855bd3b1ce895af43737b92ab9e922b35806`
- `BET-Y1Q4-T1-06`:
  `sha256:3f3eb26334abf51949c2f259876b22741ae4aafad2b0c89f62b5ff26b2e66ce7`
- `BET-Y1Q4-T1-07`:
  `sha256:a9d0986b151f031ea4ebf2762d309623a7cf718f59076693391ae6caeaeae009`
- `BET-Y1Q4-T1-08`:
  `sha256:1233f50db2aeeac24619653a4b501cfa0fe231c240e8d5ba52737f13c840047e`
- `BET-Y1Q4-T8-05`:
  `sha256:cf5ffa9eabedbe7eb1152906627b86e344c8cfd064479c9652f7529d2138fb3c`
- `BET-Y1Q4-T1-09`:
  `sha256:740d5a36d1506fde38ef0f95b2aa2a3aad47c9924d9494bec7a54fb08b936992`

## Initial truth boundary

Every new BET is:

- `status: candidate`;
- engineering `NOT_STARTED`;
- operational/value `NOT_PROVEN`;
- overall `evaluating`;
- `value_indicator_policy: false`;
- `human_gate: true`;
- without start/done/completed timestamps or positive evidence.

The first `portfolio_binding.schema_state=bootstrap_unenforced` declaration is
not evidence that Portfolio v2 exists or is enforced.

## Explicit prohibitions

This binding does not authorize:

- modifying any existing BET object, status, dependency, accepted binding,
  completion/value evidence, timestamp, or retro;
- adding W1-W6 BETs or top-level Portfolio v2 data;
- implementation plans, code, tests, projections, gitlinks, CI, branch
  protection, workflow runs, claims, locks, runtime, services, databases, or
  user configuration;
- completing any W0 BET or recording personal value;
- modifying any existing PR, including the already merged PR #2950;
- manually deleting the retained legacy clone or fabricating its missing
  identity/provenance/readiness.

## Non-durable pre-commit observations

The following are executor-observed working-tree results, not immutable
receipts and not completion evidence. The approved ten-path scope does not
permit a separate local validation artifact. These observations must be
independently reproduced before commit and repeated against the committed
tree, required PR checks, and the exact post-merge tree. Until then, they do
not prove delivery.

- Clone lifecycle onboard returned `profile=full`, provenance/readiness
  `ready`; recursive checkout completed and every root/nested repository was
  clean before editing.
- Structural comparison found exactly the eight approved W0 IDs added, zero
  removed IDs, zero changed existing BET objects, and byte/semantic equality
  for every top-level Ledger field outside `bets`.
- The W0 dependency graph is acyclic and equals the approved dependency
  matrix. Parent ownership is not encoded as a child execution dependency.
- All eight BETs are candidate/evaluating with engineering `NOT_STARTED`,
  operational/value `NOT_PROVEN`, `value_indicator_policy=false`,
  `human_gate=true`, and no start/done/completed timestamp or positive
  evidence.
- All eight frozen Spec SHA-256 values recomputed exactly to their unique
  four-key accepted bindings; each Spec frontmatter binds the same BET and
  keeps `implementation_authorized=false`.
- All eight canonical WorkPackets compiled successfully against the current
  instruction pack and each emitted `authority.human_gate=true`, matching the
  corresponding source BET.
- Ledger lint comparison: immutable base `0` errors, working tree `0` errors,
  zero added/removed findings.
- Nine single-file document SSOT checks passed; file-scoped document
  governance passed for the eight Specs plus this waiver with zero warnings.
- Agent-workflow lint passed with only the existing optional `gstack` warning.
- GaC registry validation passed with an advisory pre-existing script-baseline
  hint (`580` active vs `571` baseline); no rule or baseline is changed here.
- Exact change-lane validation passed for only
  `docs`, `docs_data`, and `governance_state`; `git diff --check` passed.

Independent review, committed-tree verification, required PR checks, merge,
exact-SHA post-merge verification, and canonical clone retirement remain the
durable delivery gates and are not represented as completed here. Once this
waiver is committed, this section preserves only the reported pre-commit
observations; Git commit identity and GitHub check URLs provide the immutable
evidence for later stages.

## Rollback

Before merge, close the unique PR and preserve the branch/tag for audit. After
merge, any failure caused by these ten paths requires a separate exact-scope
revert PR removing only the eight new Specs, eight new BET objects, and this
waiver. Rollback never modifies existing BET truth, code, runtime, W1-W6, or
personal-value evidence.
