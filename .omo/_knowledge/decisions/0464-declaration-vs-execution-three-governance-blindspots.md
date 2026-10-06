---
schema: md/v1
status: PROPOSED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-10-06
type: ssot
id: ADR-0464
related:
  - ./0453-declaration-execution-gap-multiscale-signal.md
  - ./0195-architecture-convergence-isc2.md
  - ./0372-memory-os-control-plane.md
  - ./0203-requirement-iteration-workflow-mandatory.md
  - ./0204-requirement-iteration-enforcement.md
tags: [governance, blind-spot, declaration-vs-execution, default-config, factual-currency, gitlink, submodule]
---

# ADR-0464 — 声明已达但执行未达：三类治理盲区与判据

- **Status**: PROPOSED（三类盲区均经 BET-Y2Q4-T3-04 交付链实测；本 ADR 只记录判据，
  不改任何门禁实现，实施属后续独立工作）
- **Date**: 2026-10-06
- **Traceability**: 实例全程可追溯 —— `BET-Y2Q4-T3-04`（KOS/MOS P0 fixes）、
  omostation PR #4653、kairon PR #97、follow-up `BET-Y2Q4-T10-231`；
  复盘见 `.omo/_knowledge/retros/BET-Y2Q4-T3-04.md`
  （Q3 打假同时记录 D3 偏差与盲区三的 gitlink hazard）。

## Context

本仓的治理门禁按"结构合规"设计：frontmatter 齐不齐、链接断不断、owner 在不在、
review 日期新不新、锚点在可执行语料里叫不叫得应。BET-Y2Q4-T3-04 的交付链暴露了
**三类结构合规但事实失效的盲区**，每一类都有可复现的证据、一个"为什么现有门禁
抓不到"的机制、一个可落地的判据。三条分开记录，避免把不同失效模式塞成一条大而
无当的规则。

---

## 盲区一：锚点已接线但默认配置使其惰性（inert-by-default）

**现象**：一个能力/组件可以在 registry 里完整登记、相位全绿、锚点可解析，但默认配置
下从不真正执行 —— 于是所有"已验证"的读数都是文档或空跑，不是该能力在其真实默认
形态下的行为。

**证据**：`projects/knowledge/kairon/packages/mos/` —— Memory OS 控制面在
`.omo/_truth/registry/memory-os.yaml` 登记为 `status: phase10`（phase0-10 全部 done），
`bos://memory/mos/*` 六条意图路由齐全，ADR-0372 ACCEPTED；但其生产后端**默认关闭**：
`MOS_LIVE_KOS=0`、`MOS_LIVE_GBRAIN=0`，neo4j 由未设置的 `NEO4J_URI` 门控；
`mos/src/mos/service.py` 默认装配 InMemory/Shadow 后端。因此默认 recall 返回的是
fixture/stub 数据 —— 修复前 `data_mode` 字段不存在，调用方无法区分。

**为什么现有门禁抓不到**：`CLAUDE.md` §6.6 类锚点检查验证的是"锚点名字可达"
（在可执行语料/registry 里能解析到）。本类失效的锚点**可达** —— 它只是不在默认
配置下被到达。结构门禁看不到"默认未执行"。

**新判据**：一项声明为可用的能力（`status` 非 stub/partial/disabled）必须满足
**默认配置下至少真实执行过一次**。可检查形式建议（实施时再定，不在本 ADR 改门禁）：
断言一个可机读信号 —— 例如"最后一次在**默认 env**（无 live 覆盖）下的真实调用
产生的可观测事件/结果"必须存在且新鲜；对 MOS 具体化为默认 `data_mode != fixture`
或 `status.adapters` 中至少一个生产后端在默认 env 下有真实成功调用记录。任何
"仅文档/仅 registry 全绿"的能力不得作为已验证宣称。

---

## 盲区二：结构合规但事实失效（structurally-compliant but factually-stale）

**现象**：文档面上的"数字事实"（数量、计数）相互矛盾，且与真源不符，而整套文档
门禁仍全绿。

**证据**：知识系统标题级文档计数在三处权威面不一致 —— `README.md` 声称 6,691，
`ARCHITECTURE.md` 声称 31,944，而真源 `data/kos/kos-index.sqlite` 实测为 13,782。
与此同时 `bin/ssot/doc-ssot-lint.py`、`doc-governance-check.py`、`make gac-local-gate`
全部 PASS。

**为什么现有门禁抓不到**：文档门禁检查的是**结构**：frontmatter 有效性、链接解析、
owner 存在性、review 日期新鲜度（见 `doc-governance-check.py` / `doc-ssot-lint` 的
职责边界）。它们**不校验**一个已写下的数字是否仍等于其拥有的 registry/真源。

**新判据**：对数字类事实引入**事实时效检查**：文档中的可计数数字必须能从其 owner
注册表/真源**当场复算**一致，或显式改为指针（"去写死 → 引用 registry"）。
成本说明（诚实的边界）：不能全面机械化 —— 需要注册"数字 → 真源查询"映射，
且某些数字（如里程碑快照）语义上允许过期并带时间戳。建议从**最高价值数字类**
起步（文档数、测试数、健康分、端口、地址），由 owner 逐字段声明真源查询；
未知映射的数字至少要求**不带数字或带 `as-of` 时间戳**，禁止无源裸数字。
可行性判据：若某数字无注册映射且非 `as-of` 标注，`doc-governance-check` 应报
`UNSOURCED_NUMERIC_FACT`。

---

## 盲区三：子模块 pin 的可达性语义（gitlink reachability semantics）

**现象**：先合并子模块 PR、再合并父仓 PR 的"直观"顺序，会静默产生一个**父仓 CI
无法解析自己 pin** 的状态。

**证据**：kairon PR #97 以 **squash** 合并后，kairon main 新 tip 为 `35f2ab77`；
原 commit `86c485c9`（父仓 gitlink 所指向）不再是 kairon `origin/main` 的祖先。
`bin/ssot/submodule-reachability-gate.py` **只接受 `refs/remotes/origin/main` 的祖先**
（显式不认 feature 分支："只认远端跟踪 ref，不认 refs/heads/main"）。GitHub 的
"rebase and merge" **不是 fast-forward**，它总是重写 SHA；kairon main 又
`required_linear_history`（merge commit 被禁）。因此该失效是**结构性的**，不是
偶发。实测 `git merge-base --is-ancestor 86c485c9 origin/main` 退出码为 1；
修复为根 gitlink re-point（commit `bf2fbdac1` → `35f2ab77`）后 root CI 才绿。

**为什么现有门禁抓不到**：父仓的 pre-push `submodule-reachability` hook 在**交付时**
就拦 —— 但那是在"已经踩进错误顺序、且被单独一次 push 拦下"时才显现；门禁看的是
"pin 当前是否可达"，不指导**顺序**。CI 的 `governance-verify` 在合并前可绿（pin 还
指向旧分支）、合并后复检才红 —— 若先合子模块，等于把"父 PR 必然红"预埋进去。

**新判据**：对任何"子模块 PR + 父仓 gitlink bump"的交付，把**顺序**立为显式前置：
子模块合并 → 验证新 pin 是 `origin/main` 的祖先（`merge-base --is-ancestor`，
或等价的 `branch --contains`）→ **re-point 父仓 pin** 到新的子模块 main tip →
等待父仓 CI（`submodule-reachability` / `governance-verify`）绿 → 才合并父 PR。
任何跳过 re-point 的"先子后父"顺序视为 deliverable 级错误（可进流程 checklist /
closeout 模板，而非等 hook 打脸）。

---

## Decision

记录并批准以下判据方向（**不实施**）：

1. **inert-by-default 判据**：声明可用的能力必须默认配置下真实执行过一次；以
   "默认 env 下的真实调用/可观测事件"为信号。
2. **factual-staleness 判据**：裸数字必须可复算或带 `as-of`；`readme`/架构文档的
   计数类数字一律指针化（指向 owner registry）。
3. **gitlink order 判据**：子模块合并 → pin 祖先验证 → 父仓 re-point → CI 绿 →
   父 PR 合并，作为显式前置顺序。

实施各自独立成项（BET/门禁改动），本 ADR 只记录事实与判据，不改任何 gate 代码。

## Consequences

**得到**：
- 三处"结构绿但事实假"都有了名字与判据，后续可各自落为回归守卫。
- 新能力的验收标准不再只看 registry/锚点可达，而看默认配置下的真实执行。
- 子模块交付路径多一道顺序纪律，避免"父 PR 必红"的结构性坑。

**代价**：
- 判据一需要"默认执行"的观测面（最小化：默认 env 调用埋点/事件）；
- 判据二需要数字-真源映射的维护成本（已注明按价值分级 + `as-of` 兜底）；
- 判据三增加一次明确的 re-point 提交，属可接受交付步骤。

## Confirmation

- 判据一：对 `bos://memory/mos/*` 默认形态做一次探针，能产生 `data_mode !=
  fixture` 或等价"默认执行过"的事件即生效。
- 判据二：`doc-governance-check` 能对至少一个 `UNSOURCED_NUMERIC_FACT` 报出；README
  的文档计数从字面量改为指向 registry 后不再漂移。
- 判据三：下一次子模块交付按顺序执行后，父仓 CI 全程不红；`merge-base --is-ancestor
  <old-pin> origin/main` 的 exit=1 情形在 re-point 后不再出现。

## Links（不重复事实，只引用）

- 盲区一锚点检查语义：`CLAUDE.md` §6.6；registry：`.omo/_truth/registry/memory-os.yaml`；
  默认装配：`projects/knowledge/kairon/packages/mos/src/mos/service.py`；
  ADR-0372 `.omo/_knowledge/decisions/0372-memory-os-control-plane.md`。
- 盲区二门禁职责：`bin/ssot/doc-ssot-lint.py`、`bin/ssot/doc-governance-check.py`；
  真源：`data/kos/kos-index.sqlite`（runtime artifact，不入 git）。
- 盲区三门禁实现：`bin/ssot/submodule-reachability-gate.py`（`refs/remotes/origin/main`
  祖先判定）；kairon merge 记录：kairon PR #97 / squash `35f2ab77`；根 pin re-point：
  root commit `bf2fbdac1`；经验复盘：T3-04 retro Q3-4。