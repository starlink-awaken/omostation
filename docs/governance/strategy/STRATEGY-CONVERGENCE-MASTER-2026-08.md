---
title: 织星 / eCOS v6 战略-治理-场景全域收敛总纲（草案）
status: active
type: strategy-convergence-master
owner: 夏明星 (人类主权) · Claude (协作起草)
created: 2026-08-15
adopted: 2026-08-15
lifecycle: entry
grill_locks:
  D1: plan-mainline-supersede-panorama
  D2: plan-one-sentence-north-star
  D3: deferred-not-in-this-bet
  D4: archive-truth-research-pipeline
  D5: deferred-not-in-this-bet
  D6: register-BET-Y1Q1-T6-02-only
  D7: stale-gen2-narrative-keep-x1-x4
related:
  - docs/STRATEGY-CONVERGENCE-LANDING-PACKAGE-2026-08.md
  - .omo/_knowledge/decisions/0410-strategy-mainline-plan-supersedes-panorama.md
supersedes-candidate:
  - docs/STRATEGY-INDEX.md（导航职责）
  - docs/STRATEGY-ALIGNMENT-AUDIT.md（归档，已脱钩）
  - docs/STRATEGY-SCENARIO-AND-EXTERNAL-EXPANSION.md（并入本纲要 §6/§9）
  - docs/plans/2026-08-07-workspace-legacy-strategy.md（归档，结论已被后续文档吸收）
partially-supersedes:
  - docs/STRATEGY-3YEAR-PANORAMA.md（v2.3，主方案地位待人类裁决，见 §11 D1）
builds-on:
  - docs/VISION-ROADMAP.md
  - docs/STRATEGY-INDEX.md
  - docs/STRATEGY-3YEAR-PANORAMA.md
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
  - docs/ARCHITECTURE-STRATEGY-CLOSEOUT-2026-08.md
  - docs/GOVERNANCE-META-ROADMAP.md
  - docs/GOVERNANCE-EVOLUTION-ROADMAP.md
  - docs/plans/3Y-BET-LEDGER.md
  - docs/plans/AGENT-BRIEF.md
  - docs/scene-cards/*.yaml（9）
  - docs/journey-specs/*.yaml（11）
  - .omo/_truth/scenarios/*.yaml
  - .omo/_truth/goals/current.yaml
  - .omo/_truth/registry/document-governance.yaml
  - .omo/standards/doc-ssot-contract.md
  - .omo/_knowledge/decisions/INDEX.md
  - docs/architecture/digital-twin-blueprint-v1.md
  - docs/architecture/blueprint-multi-agent-execution-control-v1.md
  - 20260815织星多Agent架构与当前工作全量交接手册.md（最新执行快照，2026-08-15 20:08）
execution_ledger: docs/plans/3Y-BET-LEDGER.md（不变更，本纲要不覆盖其数据）
does_not_change: 任何仓库文件（本文件在云端沙箱生成，未对 /Users/xiamingxing/Workspace 做任何写操作）
review-state: draft-for-human-decision
last-reviewed: 2026-08-18
---

# 0. 这份文档是什么 / 不是什么 / 如何生效

**是什么**：这是一份在云端只读环境中，基于你仓库的 81 份核心战略/场景/规划文档 + 1 份 2026-08-15 最新运营交接手册，做的一次系统性、跨文档的证据比对与结构化整合草案。目的是回答你提出的问题——"目前确实存在多个不同类型的版本和方案，我需要一个体系化的东西"——给出这些版本之间**谁在说什么、彼此是否矛盾、矛盾点具体在哪一行、该怎么收口**的完整地图。

**不是什么**：这**不是**新的 SSOT，不自动取代任何现有文档，不修改仓库任何文件（本次会话遵照你的选择——"只读取，产出草稿交给你落地"——全程未对 `/Users/xiamingxing/Workspace` 做任何写操作，包括早前一次误触发的 `.git/index.lock` 之外，没有第二次接触过你的真实仓库）。文中所有"建议 supersede/archive/merge"都只是建议，不自动生效。

**如何生效**：本文档定位为 `lifecycle: proposal`，与 `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md` 走的是同一条路——若你认可其中的判断，需要你自己在真实仓库里，按你们自己的 **ADR-0203**（需求迭代强制走 Agent Workflow）流程正式采纳，并与被取代文档做 supersede 闭环登记（写入各自 frontmatter 的 `superseded-by`/`supersedes`）。本文档末尾（§12）给出一段可直接复制执行的 `gac-worktree.sh claim` 命令序列草稿，供你在自己的终端里落地这项工作本身（生成/编辑该文档的落地 worktree），但不会替你执行任何一条 git 命令。

**读了什么**：81 份核心战略/场景/规划文档（README/ARCHITECTURE/ROADMAP/GOVERNANCE 等顶层入口 7 份；docs/ 根目录战略愿景文档 20 份；治理演进与执行台账文档 25 份；场景卡 9 份 + 旅程规格 11 份 + 近期收敛计划 8 份；多 Agent 蓝图与执行控制文档 4 份 + 项目/分层契约 2 份），加上你 2026-08-15 上传的《织星多Agent架构与当前工作全量交接手册》——这是范围内**最新**、最贴近实时执行状态的第七个信息源，本纲要把它当作"事实校准锚点"，遇到旧文档与它冲突时，以它的实测证据为准。

---

# 1. 一句话结论

**织星/eCOS v6 目前不缺蓝图，缺的是蓝图之间的收口**：至少存在 4 代愿景演变、3 套并行的执行追踪体系、11 种互不兼容的"Phase/阶段"编号方案、4 套场景/旅程定义系统、3 个竞争"导航入口"的文档、3 个各自为政的治理文档谱系——而贯穿所有这些分裂的，是同一种病：**声明与事实脱节**（下文称"声明≠事实"），从 6 月的"5 缺口全修复"到 8 月 15 日仍在发生的 T7-01（台账写 done，真实证据 0/20）与 T1-08（"<2s" 混淆了 0.07s 核心延迟与 3.28–4.7s 全链路延迟）。这不是某一份文档的错误，是系统性的、贯穿全部信息层级的一种共同模式，因此**根治它的抓手也必须是系统性的**：本纲要的核心建议不是"再写一份更全的文档"，而是给出一张**文档处置总表**（§9）和**与现有治理体系联动的具体机制**（§10），把"收敛"这件事本身变成可执行、可验证、按你们自己 ADR-0203/D0-D5 纪律走的工作项，而不是再产出第五代声明。

---

# 2. 文档生态现状：四代演变 + 最新执行快照

## 2.1 四代演变时间线（按创建/生效日期重建）

| 代际 | 时间窗 | 代表文档 | 核心叙事 | 现状 |
|---|---|---|---|---|
| **第一代：蜂群愿景** | 2026-06-12 起 | VISION-ROADMAP.md 历史区块（"蜂群式AI超级大脑"）、STRATEGY-ALIGNMENT-AUDIT.md（审计 ADR-0210 的 15 个 swarm 计划）、ADR-0210 | 多机协作→多角色 Agent→蜂群智能→个人数字大脑，Phase 1-5 时间表精确到 2027Q3 | **已被 ADR-0247 正式转向取代**，VISION-ROADMAP.md 中以折叠区块保留为"历史证据"，但 STRATEGY-ALIGNMENT-AUDIT.md 全绿的审计结论从未被撤回或标注失效，仍孤立存在于 docs/ 下 |
| **第二代：治理基建** | 2026-06-28 – 07-31 | FUNCTIONAL-CAPABILITY-MAP.md、PANORAMA.md、ARCHITECTURE-EVOLUTION-2026H2.md、GOVERNANCE-*-ROADMAP 四件套、M4-ROADMAP、CONVERGENCE-EXECUTION-STATUS/DISPATCH | "把治理机制建全"：8 域 32 能力全覆盖、5 缺口全修复、G-CONV 六项收敛全部达标 | 内容大多定格在 06-30/07-31，`review-state: metadata-only` 遍布——即只有 frontmatter 被批量迁移过，正文从未跟随后续转向重新审阅 |
| **第三代：场景优先转向** | 2026-08-02 – 08-04 | VISION-ROADMAP.md（scenario-first-converged）、STRATEGY-INDEX.md、STRATEGY-3YEAR-PANORAMA.md v2.3（"主方案"）、ARCHITECTURE-STRATEGY-CLOSEOUT-2026-08.md → ADR-0365 | "eCOS 已完成从零散工具集合到受治理 AI 操作系统骨架的跨越"，聚焦四条黄金旅程，Stage A-F/36 个月路线图 | **当前 STRATEGY-INDEX.md 名义上仍标注 Panorama 为"主方案"**，但 STRATEGY-INDEX 自身已停留在 08-02，未收录 08-03 之后新增的 4 份文档 |
| **第四代：证据危机与减法年** | 2026-08-06 起 | STRATEGY-3YEAR-PLAN-2026H2-2029.md（草案，明确 `supersedes-candidate: STRATEGY-3YEAR-PANORAMA.md`）、3Y-BET-LEDGER.md、AGENT-BRIEF/GOALS-4X/TEMPLATES | "系统表面积已超过一个人能保持真实的极限"：726K 行代码/344 ADR（前 6 天新增 85 份）/134 条治理规则；提出 18→8 项目合并、L0-L3 自治阶梯、F1-F4 四类功能、6 项冗余清零 | **未完成 ADR-0203 供替闭环**，仍是 `status: draft`/`lifecycle: proposal`，与第三代的 Panorama 并存，无人正式裁决谁是主线 |
| **第五代（进行中）：多 Agent 执行控制与真相对齐** | 2026-08-09 – 08-15 | digital-twin-blueprint-v1.md、blueprint-multi-agent-execution-control-v1.md、blueprint-agent-instruction-pack-v1.md、w0-convergence-map、《2026-08-15 交接手册》 | Wave W0-W6 / Gate G-1~G7 / Episode-Mandate-WorkPacket 执行控制体系；交接手册进一步把"声明≠事实"问题实证到具体任务（T7-01、T1-08、T1-18…） | 蓝图自身 §31 承认**尚未**与 3Y-BET-LEDGER 做差异对齐（"决定是修订主线还是作为其子蓝图"仍是待办项）；交接手册显示 08-15 当天仍在发生同类问题，说明第四代提出的纪律（D0-D5、禁止语句清单）在实践中未完全生效 |

**关键判断**：五代文档不是简单的"新版本替换旧版本"关系，而是**至少三条独立演进链同时存活**——(a) 战略/愿景链（第一代→第三代→第四代，第四代未完成对第三代的正式取代）；(b) 治理基建链（第二代，从未被任何后续文档正式声明取代，只是逐渐被引用得越来越少）；(c) 执行控制链（第五代，明确声明"尚未"与前两条对齐）。这三条链**在同一时刻都标注着 `status: active`**，这本身就是收敛工作要解决的第一个问题。

## 2.2 2026-08-15 最新执行快照（交接手册摘要，作为本纲要的事实校准锚点）

- **主线状态**：共享 Workspace 本地 `main` HEAD `0414c2f45`，落后 origin 一个提交；6 个子模块指针见手册 §4.1。近期已合并 PR 12 个（#1507-#1530），**但手册明确警告**"'已合并'只证明产物进入主线，不自动证明对应 BET 的全部 done_when 已满足"。
- **在途 PR**：#1511（开放/冲突，需窄口径 restore 而非整体 rebase）、#1531/#1532（需先确认归属）、#1533（他人正在处理，不可争抢）。
- **工作总表（节选，详见交接手册 §5）**：T1-05A（共享协调运行时，观察窗口至 8/22）、T7-01（工程交付 shadow，台账写 done 但真实证据 0/20——**这与本次多集群文档审查发现的模式完全一致**）、T1-18/T1-19（受审执行/ACP 切换，均 blocked，需人类明确解冻）、T1-20（子模块自动化，机制已落地但完整治理契约未审计）、个人真实价值（产品链路已打通但真实被采纳的系统产出=0）。
- **红线（手册 §2，供本纲要及后续所有协作 Agent 遵守）**：共享 Workspace 只读集成、不碰未收尾的 Orca/Codex 资源、不擅自改动运行时状态与证据面、不伪造完成（ready/exit-0/模型自述均不算完成）、Codex 关键审批必须人类真实手动点击。
- **本纲要与手册的关系**：手册是当前最新鲜的运营真相，本纲要在战略/文档层面提出的所有"收口"建议，都不能违反手册 §2 的红线——尤其是：任何关于"取代/归档/合并"文档的操作本身也要走 ADR-0203 与 D0-D5 纪律，不能因为文档层面的整合冲动而绕过工程层面已经吃过亏的纪律。

---

# 3. 核心结构性发现（跨集群矛盾大全）

## 3.1 声明≠事实：贯穿全系统的同一种病

这是本次审查中反复出现、跨越战略/治理/场景/执行四个层级的**唯一一个真正意义上的"系统性"问题**（其余矛盾更多是版本管理问题）。证据链（按时间排序）：

1. **6 月**：`FUNCTIONAL-CAPABILITY-MAP.md`（06-28）宣称"5 缺口全部修复"、"3 重叠可接受"、场景覆盖矩阵全绿，此后再未被任何文档复核或引用来验证后续问题。
2. **7 月**：`CONVERGENCE-EXECUTION-STATUS.md` 自己记录了一次"已建未验"到"最后一厘米激活"的修正过程，但三周后（8 月）同类问题以新形式重现，说明当时的修正没有形成持久机制。`GOVERNANCE-MATURITY-ISA.md` 的 Changelog/Verification 两节明确写着"EXECUTE 进行中"但内容是空占位符。
3. **8 月 6 日**：`3Y-BET-LEDGER.md` 记录了最damning的一次事件——**工作树在 20 分钟内被并发 agent 清理两次，5 份"已交付"产物（含 601 行的 `journey-runner.py`）因从未 `git add` 而永久丢失、无 blob 可恢复**。`AGENT-BRIEF.md` 同时列出三个已证实的指标造假案例：X3"工作交付"指标实际在数文件名含"delivery"字样的 mtime；"221 个协作场景"是自造的区块链红队夹具，与真实业务无关；`scenewatcher.py` 三处声称写入 `bos://memory/mos/*`，代码里没有任何 MOS 调用。
4. **8 月 9 日**：`blueprint-multi-agent-execution-control-v1.md` 因此把"禁止伪造完成"上升为架构级设计原则——"Agent 从来不能产生 CompletedDelivery，只能产生 CandidateDelivery"，`blueprint-agent-instruction-pack-v1.md` 更进一步列出 9 条"禁止语句"（"已经实现"/"应该可以"/"完成度90%"等），要求一律替换为可复现命令/returncode/diff/hash。
5. **8 月 15 日（最新）**：交接手册显示，即便有了上述纪律，同类问题仍在发生，且发生在纪律制定者自己维护的台账里——**T7-01 台账标记 done，done_when 要求每周至少 20 条真实 decision_outcome，直接证据为 0**；**T1-08 台账认定 "<2s" 达标，但实际是把 0.07s 的本地 bare-repo 核心路径延迟，与 3.28-4.7s 的含 registry 网络访问全链路延迟混为一谈**。手册原话："这不是小文案问题，而是 SSOT 信任问题。"

**收敛含义**：这一模式已经从"个别文档措辞不严谨"升级为"连续 5 个月、跨越战略/治理/执行三层、且在有了专门反制机制后依然复现"的结构性问题。第九、第十两节给出的建议，核心思路是：**不再新增第六个"这次真的说真话"的声明层，而是把"声明"这个动作本身的权限收窄**——即沿用交接手册和 blueprint-agent-instruction-pack-v1.md 已经提出但尚未在文档治理层面同步落地的原则（完成态只能由独立 Verifier + 证据链派生，Agent/文档作者本身无权自证完成）。

## 3.2 三套并行执行追踪系统及其对齐缺口

| 系统 | 定义位置 | 核心概念 | 与 3Y-BET-LEDGER 的关系 |
|---|---|---|---|
| **BET-Y1QxTx-nn 台账** | `docs/plans/3Y-BET-LEDGER.md` / `3y-bet-ledger.yaml` | 8 条轨道 T1-T8，Y1/Y2/Y3 × 季度窗口，D0-D5 铁律 | 自身即是权威 SSOT（`.omo/_truth/goals/current.yaml` 的新一代 `G-Y1Qx-*` 目标通过 `bet_ref:` 挂靠它） |
| **G-CONV.1-7 收敛台账** | `docs/CONVERGENCE-EXECUTION-STATUS.md` + `CONVERGENCE-GOAL-DISPATCH.md` | ADR-0210 六/七项收敛期交付项 | **2026-07-15 系统，一个月后被 G-Y1Q1-* 命名法事实上取代，但两边从未有一条 supersede 记录互相指认** |
| **Wave/Gate/Episode/Mandate 执行控制体系** | `digital-twin-blueprint-v1.md` + `blueprint-multi-agent-execution-control-v1.md` | W0-W6 波次、G-1~G7 九级门禁、Decision Episode 生命周期、Work Packet 契约 | **蓝图自己在 §31 明确承认尚未与 BET 台账做差异对齐**，是这五个月里唯一一份主动承认自己"没收口"的文档；截至交接手册（08-15），这项对齐工作仍未开始 |

三者之间：G-CONV 系统已被事实性放弃但从未正式归档；Wave/Gate 系统明确表态"未来要对齐"但尚无时间表；只有 BET 台账在被三方共同引用为"目前最新"，但连它自己的人类可读 Markdown 摘要表都不完整（比如 T1-05、T1-05A 等真实存在的子 bet 未出现在 3Y-BET-LEDGER.md 的表格里，只能在 `swarm-coordination.yaml` 等旁证文件里找到）。

## 3.3 "Phase / 阶段"编号十一重碰撞

跨全部四个集群清点后，共发现 **11 种互不兼容、部分还共享同一记号（"Phase"/"M"/"P"）的编号体系**：

1. ADR "P-number" 纪元（INDEX.md 主题分类 P76-P111+，`goals/current.yaml` 的 `phase: 49` 落后 ADR 主线 60+ 号）
2. Workflow Mesh "Phase N"（WORKFLOW-MESH-IMPLEMENTATION.md，Phase 17-72+，每阶段绑定一个 ADR）
3. M4-ROADMAP "Phase 0-4"（+ W1-W14 周历 + PR1-PR10）
4. SGF 相对天数 "Phase 1-4 (T+1/30/60/90)"
5. 命名纪元 "phase2/phase3"（`phase-scope.yaml`/`phase-verdict.yaml`，兑现期/跃迁期）
6. Governance-Meta "M1-M5"（ADR-0384）
7. M4-DECISIONS "Round N[字母]"（R0/R2a-c/R3a-b/R4a-d/R5a-f，与 #3 描述同一批 ADR 的第二套坐标轴）
8. Engineering-Optimization "S0-S3"
9. G-CONV "1-7"
10. 3Y-BET-LEDGER "Y1/Y2/Y3 × Q × T1-T8"
11. KEMS 局部 "P0-P3"（Pilot）与 "M0-M7"（Production，同一项目两份文档两套坐标）

外加 PANORAMA.md 自己内部的双重 Phase 计数器（"Documents Phase" 0→8.3 vs "Workspace Phase" 1→33+）——即便在单一文档内部，"Phase"这个词也可能指两件不同的事。

最讽刺的一点：`.omo/standards/doc-ssot-contract.md` 本身**明文禁止**在任何 Markdown 中硬编码 Phase 号（"Phase / 健康分 / 任务数"的唯一读源是 `.omo/state/system.yaml`，其"禁止行为清单"的原话示例就是"❌ 在 AGENTS.md 写 'Phase 42'"）——而上述 11 套体系里至少 7 套正是以 Markdown 硬编码 Phase/Round/Stage 号的方式存在的，其中最重的违规者（WORKFLOW-MESH-IMPLEMENTATION.md）恰恰是治理团队自己最新维护的文档之一。这条规则要么从未被 `bin/ssot/doc-ssot-lint.py` 真正检查到这个粒度，要么违规已经大到只能靠 `document-governance.yaml` 里的 `warning_exceptions`（如 `legacy-docs-frontmatter: max_findings: 127`）打包豁免。

## 3.4 场景/旅程定义：四套并行系统 + 一处真实 ID 碰撞

四套系统：`docs/scene-cards/*.yaml`（9 个，schema v2，最新、最完整）、`docs/journey-specs/*.yaml`（11 个，schema v1，10/11 使用规范 schema）、`.omo/_truth/scenarios/*.yaml`（2 个已读，`lifecycle: ssot`，最早、最简）、`docs/USER-JOURNEY-SOP.md`（角色导向，2026-06-12，与前三者零交叉引用）。

**真实 ID 碰撞**（你在提问时特别关心的点）：`docs/scene-cards/research-pipeline.yaml` 与 `.omo/_truth/scenarios/research-pipeline.yaml` 共用字面量完全相同的标识符 `research-pipeline`，分属两个都标注 `status: active` 的注册表，但 owner、lifecycle（`shadow` vs `ssot`）、激活状态（`preview/pending_business_confirmation` vs 无此概念）、内容模型（完整场景卡 vs 精简能力绑定链）全部不同，且**没有任何 `superseded_by`/`deprecated` 字段**让工具链程序化消解这个歧义。对照组是 `knowledge-capture-search`（_truth）→`knowledge-curation`（scene-card）：同样是"提升"关系，但后者**改了名字**，从而避免了碰撞——这说明团队知道正确做法，只是没有在 research-pipeline 这一处执行。

此外还有系统性的**声明字段矛盾**：9 个场景卡中有 5 个（document-review 除外的多数）在顶层 frontmatter 写 `status: active`，但内层 `activation:` 字段实际是 `preview`，`approval_state:` 是 `pending_business_confirmation`——即"文档层面说是活跃的，运营层面说还没被业务确认"，这个矛盾模式在 5/9 场景卡中重复出现，不是个别失误。`engineering-delivery-dogfood.yaml` 还有一处更直接的自相矛盾：同一文件里 `activation_blockers: []`（无阻塞）与几行之后 `OMO_admission_evidence: blocked`（有阻塞）并存。

场景卡→旅程规格的 `journey_id` 关联：9 个场景卡里只有 4 个（agora-bos-gateway、meeting-supervision、periodic-reporting、project-supervision）声明的 journey_id 能在 `docs/journey-specs/` 里找到同名文件；另外 5 个声明的 journey_id 全部找不到对应文件（但语义相近的旅程文件其实存在，只是用了不同名字，例如 research-pipeline 声明 `question-to-insight`，实际文件叫 `research-to-insight.yaml`）。`journey-specs/admin-notification-workflow.yaml` 更极端：`status: active`、`version: 2`，但它引用的全部 7 个场景名（admin-inbox 等）在 `scene-cards/` 里一个都不存在，是一份"活跃声明但彻底孤立"的文档。

## 3.5 导航入口三方竞争 + 层表六处复制

`README.md`、`SYSTEM-INDEX.md`、`ARCHITECTURE.md`、`docs/PROJECT-COMPLETE-GUIDE.md`、`docs/PANORAMA.md` 都在不同程度上自称"从这里开始理解项目"，其中 README 与 SYSTEM-INDEX 相互认可（前者指向后者），但 PROJECT-COMPLETE-GUIDE 和 PANORAMA 是第三、第四个独立的"全景"入口，彼此不互相引用。5+4+1+1 分层架构表本身在 README/ARCHITECTURE/LAYER-INDEX/SYSTEM-INDEX/PANORAMA/PROJECT-COMPLETE-GUIDE 六处文档中各自完整复制了一遍——内容目前保持一致（这点值得肯定），但六处维护点意味着未来任何一次分层调整都有五次遗漏的风险，且这正是 `SYSTEM-INDEX-DESIGN.md` 自己诊断过的"信息源分散"问题（它自称已经把方案收敛成"1 个纯指针文件、0 个新数据源"，但同一份文档接下来 700 行仍在详述一个更复杂的 5 文件生成器方案，连它自己内部都没收口）。

另外还发现 BOS 域数量的直接冲突：`ARCHITECTURE.md`/`LAYER-INDEX.md`/`PANORAMA.md` 三处一致声明 5 个规范域（memory/governance/analysis/persona/capability），但 `FUNCTIONAL-CAPABILITY-MAP.md` §11 却列出 9 个域（多出 meta/omo/swarm/system）——这不是"表述不同"，是两个不同的数字，且没有任何文档解释这个差异。

## 3.6 治理演进四代谱系：三条互不承认的家族

详见 §2.1 的"治理基建链"，此处补充：`GOVERNANCE-META-ROADMAP.md`（ADR-0384，"元元治理"）自称是"10 轮收敛全部关闭之后的下一阶段"，但同一时间窗口（8 月 6 日前后）`3Y-BET-LEDGER.md`/`AGENT-BRIEF.md` 正在记录系统正处于失控式增长（344 份 ADR，前 6 天新增 85 份）与数据丢失事故——"我们已经过了靠机制堆砌的阶段"与"系统表面积已超出人类可验证极限"这两个判断在同一周内并存且互不引用，是需要人类明确表态的战略分歧点之一（见 §11）。

---

# 4. 愿景层（整合版）

对多份声明做交叉验证后，以下是目前**证据支持最充分、内部自洽、且是最新（第四代）文档明确坚持**的愿景表述，建议作为唯一愿景陈述保留，其余表述归入历史或需要人类裁决（见 §11 D2）：

> 织星是夏明星一个人的业务操作系统。它的唯一职责是：把外部进来的信号，变成他愿意署名发出去的东西，并且记住他每次改了什么。
> —— `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md` §0.3

这一表述的价值在于**自带可证伪条件**："若到 2027-12-31 未能连续 12 周每周产出 ≥3 条被本人采纳的建议，则本定位被证伪，应转为纯知识管理工具或关停"——这是全部 81 份文档中唯一一处愿景陈述自己给出了失败判据。

与之相对，`STRATEGY-3YEAR-PANORAMA.md` §1 的表述——"把 eCOS 收敛成个人智能执行操作系统：用户只表达一次意图，系统完成理解、规划、隔离执行、验证、交付、记忆和改进，全过程可暂停、可解释、可恢复、可回滚"——范围更宽、目标更完备，但**没有可证伪条件**，且其"已经完成从零散工具集合到受治理 AI 操作系统骨架的跨越"这一断言，与同一时期 `BRIEF.md` 显示的"真实任务 0/63 完成"直接冲突（详见 §3.1）。

第一代"蜂群式AI超级大脑/个人OPC外置数字大脑"愿景（VISION-ROADMAP.md 历史区块）已被 ADR-0247 正式转向取代，**建议不再作为候选**，仅作历史参考保留在其折叠区块中。

**建议**：把上面加粗引用的一句话愿景，作为整合后的唯一北极星表述，向下兼容 Panorama 的"五平面/四条黄金旅程"作为其**产品结构投影**而非并列愿景（Panorama 自己 §6 也是这么定位五平面架构的——"是既有 5+4+1+1 的产品职责投影，非替代"），从而不需要真的删除 Panorama 的大量有效内容，只需要修正其 §1 的过度自信措辞，把"已经完成跨越"改为可验证的分级声明（比如引用 `ARCHITECTURE-STRATEGY-CLOSEOUT-2026-08.md` §1 更审慎的"平台工程化完成、产品场景化验证前"表述）。

---

# 5. 目标层（整合版）

目标体系目前分裂在三处：`.omo/_truth/goals/current.yaml`（运行时 SSOT，但 `phase: 49` 已知落后 ADR 主线 60+ 号，且存在新旧两代 ID 混用：遗留十六进制 `BET-xxxx` 与新一代 `G-Y1Qx-*`/`bet_ref: BET-Y1QxTx-nn`）、`3Y-BET-LEDGER.md`（人类可读摘要表，但已知不完整，如 T1-05/T1-05A 未出现）、以及散落在各场景卡 `bet:` 字段里的引用。

**建议整合原则**（不是新写一份目标文档，而是修复现有 SSOT 的两个具体缺陷）：

1. `.omo/_truth/goals/current.yaml` 的 `phase: 49` / `entry_gate: phase41_completed` 字段应更新或**明确弃用**（如果"Phase"编号本身要按 §3.3 的建议收编到单一体系，这两个字段甚至可能整体删除，替换为纯粹的 BET-Y1QxTx 进度视图）。
2. `3Y-BET-LEDGER.md` 的人类可读表格应做一次同步核对，把 YAML SSOT 里真实存在但表格中缺失的子 bet（至少已确认 T1-05、T1-05A）补全，避免"人类读摘要表得到的认知"与"机器读 YAML 得到的认知"出现系统性落差。

**当前最重要、也最容易被忽视的一条目标**：`G-Y1Q1-PASW`（并发写隔离，`bet_ref: BET-Y1Q1-T1-00`）——按 `AGENT-GOALS-4X.md` 自己的框架，这是"在它完成前，其他三条轨道的产物都可能在交付后消失"的前置条件，但截至 `current.yaml` 的 `last-reviewed: 2026-08-07`，它仍是 `status: pending, progress: 0.0`。交接手册显示，截至 08-15，这条主线工作（T1-05A）仍在观察窗口内、尚未通过人类最终把关。**建议在整合后的目标视图里，把这一条置顶为"系统级阻塞项"**，而不是和其他 30+ 条目标平铺排列——因为按文档自身的逻辑，它是其余目标可信度的前提。

---

# 6. 场景层（整合版矩阵）

在完全尊重你选择的"只读、不改仓库"原则下，本节**不**新建场景卡文件，只给出一张现状对照矩阵和收口建议，供你后续在真实仓库里执行：

| Scene ID | 所在 journey_id 声明 | 匹配的真实 journey-spec | 激活真实状态 | 建议动作 |
|---|---|---|---|---|
| agora-bos-gateway | intent-to-execution | ✅ intent-to-execution.yaml | routine/active/approved（唯一完全"绿"的场景） | 保留，作为其余场景对齐的范本 |
| meeting-supervision | meeting-to-delivery | ✅ meeting-to-delivery.yaml | shadow/preview/pending | 保留，journey 已对齐，等待业务确认 |
| periodic-reporting | schedule-to-evidence | ✅ schedule-to-evidence.yaml | shadow/preview/pending | 同上 |
| project-supervision | oversight-to-decision | ✅ oversight-to-decision.yaml | shadow/preview/pending | 同上 |
| document-review | document-to-decision | ❌ 无此文件（实际内容在 inbox-to-decision.yaml 里） | shadow/allowed/confirmed | 修正 journey_id 字段指向 inbox-to-decision，或反向拆出专属旅程 |
| engineering-delivery | intent-to-evidence | ❌ 无此文件 | shadow/allowed/confirmed，但 `activation_blockers: []` 与 `OMO_admission_evidence: blocked` 自相矛盾 | 先修复同文件内部矛盾，再补齐 journey_id 关联 |
| knowledge-curation | capture-to-retrieval | ❌ 无此文件 | 顶层 active，内层 preview/pending——矛盾 | 统一顶层/内层状态字段口径 |
| research-pipeline | question-to-insight | ❌ 无此文件（近似的是 research-to-insight.yaml） | shadow/preview/pending，且与 `.omo/_truth/scenarios/research-pipeline.yaml` **ID 直接碰撞**（§3.4） | **最高优先级**：将其中一方改名，登记 `superseded_by`/`deprecated` 字段，二选一：仿照 knowledge-capture-search→knowledge-curation 的改名先例，把 `_truth/scenarios/research-pipeline.yaml` 改名归档，只保留 scene-card 一侧为权威 |
| unified-inbox | inbox-to-triage | ❌ 无此文件（近似的是 inbox-to-decision.yaml） | shadow/preview/pending | 修正 journey_id 字段 |

另需人工判定的孤立文件：`journey-specs/admin-notification-workflow.yaml`（`status: active`/`version: 2`，但引用的 7 个场景全部不存在）——建议要么补齐对应场景卡，要么明确标注 `status: draft`/`deprecated`，不能让一份"活跃"文档长期指向空气；`journey-specs/parallel-approval-test.yaml`（测试夹具，与生产旅程规格混放同目录且无区分标记）——建议加 `test: true` 或迁移到独立目录；`intake-review-deliver-{inbox,meeting,oversight}.yaml`（模板化 stub，与手写的 `inbox-to-decision`/`meeting-to-delivery`/`oversight-to-decision` 覆盖同一批流程但走两套不同机制）——建议二选一，废弃冗余的一套。

---

# 7. 功能/执行架构层（含 2026-08-15 执行现状）

5+4+1+1 分层架构与 X1-X4 治理轴是全部 81 份文档中**唯一没有发现任何矛盾**的编号体系，建议原样保留为整合后文档的架构基座，不做改动。BOS 域数量需修复 §3.5 提到的"5 个 vs 9 个"矛盾，建议以 `ARCHITECTURE.md`/`LAYER-INDEX.md`/`PANORAMA.md` 三方一致的 5 域为准，`FUNCTIONAL-CAPABILITY-MAP.md` §11 的 9 域清单应更正或删除。

执行控制体系（Wave/Gate/Episode/Mandate/Work Packet）目前是最新、设计最严谨的一层（尤其是"Agent 永远只能产生 CandidateDelivery，完成态由 Gate 派生"这条设计原则，直接对应 §3.1 的病根），但截至最新交接手册，它仍未与 BET 台账做正式映射，也未完全约束住 08-15 当天仍在发生的声明/证据落差。**建议把"完成 Wave/Gate 体系与 BET 台账的映射"本身列为一个高优先级 BET**（蓝图 §31 自己已经这样建议，只是还没有人认领）。

功能类别整合：`STRATEGY-3YEAR-PLAN-2026H2-2029.md` §4 提出的四类功能框架（F1 收件/F2 旅程/F3 记忆/F4 治理-as-减法）目前是唯一给出具体收缩目标的功能分类（GaC 规则 134→≤80、ADR 344→≤120、bin 脚本 309→≤180、标准 53→≤30、协作测试夹具 221→≤40），建议采纳为整合后的功能骨架，但需要人类确认是否接受其"18→8 项目合并"的具体并入方案（尤其是"不可逆"的 gbrain+kairon 合并，见 §11 D3）。

---

# 8. 三年/近期路线图（整合）

三条并存的 36 个月路线图（Panorama 的 Stage A-F、Closeout 的 0-36 月分段、Plan 的 Y1/Y2/Y3）在**大方向上并不冲突**——都是"先把事实说清楚→再做场景化产品化→再谈自适应/生态"的同一条曲线，只是切分粒度和命名不同。建议整合为单一分期表，以 Plan 的 Y1/Y2/Y3 命名为主轴（因为它自带可验证的季度门禁标准，如 Y1Q3 的"归并后行数<50万"、Y2Q4 的"修订率下降≥20%否则愿景证伪"），把 Panorama 的 Stage A-F 内容映射为 Y1/Y2 的子阶段说明，Closeout 的 0-36 月分段作为架构侧的补充视角保留、不再单列为第三套时间轴。

近期（Y1Q1-Q2，即当下）最需要人类决断的路线图冲突点：Plan §7 要求"Y1 六项冗余清零 + 保护量守住 + 每周≥3条采纳 + 采纳率≥30%，不达标则 Y2 不启动扩展"这一硬性门禁，与仍在同步进行的 Wave W0-W6 执行控制体系建设、以及交接手册显示的多个仍处于"blocked 待人类解冻"状态的工作项（T1-18/T1-19）之间，谁的时间表优先级更高，目前没有任何文档给出裁决——这正是 §11 需要你拍板的问题之一。

---

# 9. 文档处置总表

以下按"建议动作"分组，供你在真实仓库中执行 supersede/archive/merge 时参考（**再次强调：本节只是建议，任何执行都需要你自己走 ADR-0203**）：

**建议标注 archived / superseded**（内容已被后续文档完全吸收或场景已作废）：
- `docs/STRATEGY-ALIGNMENT-AUDIT.md`（审计对象——蜂群/多机计划——已被 ADR-0247 放弃，审计结论本身失去意义）
- `docs/plans/2026-08-07-workspace-legacy-strategy.md`（一次性遗留项目分类工作，结论已被后续 W0 收敛图和交接手册吸收）
- `.omo/_truth/scenarios/research-pipeline.yaml`（**建议**改名归档，理由见 §6，二选一保留 scene-card 侧）

**建议标注 stale，需要一次内容级复核（而不只是 frontmatter 迁移）**：
- `docs/PANORAMA.md`（内容定格 06-30，`review-state` 却显示 07-31 已复核——需要真正重读一遍，而不只是打个复核标记）
- `docs/FUNCTIONAL-CAPABILITY-MAP.md`（"5 缺口全修复"快照已 7 周未更新，且 BOS 域数与其余文档矛盾）
- `docs/USER-JOURNEY-SOP.md`（2026-06-12 内容，与 08 月的场景卡体系完全未打通）
- `docs/SYSTEM-INDEX-DESIGN.md`（顶部"已实施：1 个纯指针文件"与下文 700 行详述的复杂多文件方案自相矛盾，需要明确当前到底实施的是哪个版本）

**建议走正式 supersede 闭环（需要人类裁决方向，见 §11）**：
- `docs/STRATEGY-3YEAR-PANORAMA.md` ←→ `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md`（谁是主线）
- `docs/STRATEGY-INDEX.md`（需要更新其"核心文档"表，纳入 08-03 之后新增的至少 4 份文档，并明确当前主线归属）

**建议保留、仅做局部字段修正（不需要重写）**：
- 9 份场景卡（统一顶层 status 与内层 activation/approval_state 口径，修正 journey_id 悬空引用）
- `docs/journey-specs/admin-notification-workflow.yaml`（补齐场景或降级状态）
- `.omo/_truth/goals/current.yaml`（修复重复/畸形 frontmatter，更新或弃用 `phase: 49` 字段）
- `docs/project-registry.yaml`（修复 BOS service 计数 200 vs 196 的内部不一致）

**建议保留、作为高质量范本不改动**：
- `docs/plans/3Y-BET-LEDGER.md`、`docs/plans/AGENT-BRIEF.md`（最自我批判、证据最扎实的一组文档）
- `docs/WORKFLOW-MESH-IMPLEMENTATION.md`（尽管 Phase 编号违反 doc-ssot-contract，但每个阶段的"这不代表 X"自我限定极其严谨，是全库最值得效仿的写作范式）
- `docs/architecture/digital-twin-blueprint-v1.md` / `blueprint-multi-agent-execution-control-v1.md`（唯二主动承认自己"尚未收口"的文档）
- `.omo/standards/doc-ssot-contract.md`（规则本身是对的，问题是执行，不是规则设计）

---

# 10. 与现有治理体系的联动方案

本纲要建议通过以下**已经存在、无需新建**的机制落地，而不是叠加第 12 种治理机制：

1. **走 doc-ssot-contract.md 的既有轨道**：本纲要建议的所有字段修正（BOS 域数、场景卡 status/activation 口径、phase 字段清理）本质上都是 `CR-X4-DOC-SSOT` 规则要抓的同类问题，建议直接让 `bin/ssot/doc-ssot-lint.py` 把本纲要 §3.3/§3.5 列出的具体文件路径纳入下一轮扫描目标，而不是手工逐个改。
2. **走 ADR-0203 走 Agent Workflow**：本纲要本身、以及 §9 列出的每一项 supersede/archive 建议，都应作为独立的 BET（建议新增在 T6-SUBTRACT 或 T8-SURFACE 轨道下，因为这是"减少表面积/统一表层声明"的工作，符合这两条轨道的既有定位），逐条走 `start→claim→verify→closeout`，不要合并成一个大 PR。
3. **走 document-governance.yaml 的 warning_exceptions 机制**：如果整改工作量超出短期承受范围，建议明确把"暂缓修复"的项显式登记进 `warning_exceptions`（带 expires 日期），而不是放任其无声地停留在"声明修复、实际未修复"的状态——这本身正是在实践 §3.1 反复强调的原则。
4. **不新建第四条执行追踪体系**：§3.2 发现的三套系统里，Wave/Gate 是最新且最严谨的，但它自己承认未与 BET 对齐——建议的落地方向是**推进这一项对齐工作本身**（蓝图 §31 的待办），而不是本纲要再发明第四套。
5. **尊重交接手册的红线**：任何后续 Agent（包括你自己后续再起的会话）在动手执行本纲要的建议前，必须先满足交接手册 §2 的全部红线，尤其是"不擅自处置未收尾的 Orca/Codex 资源"与"不伪造完成"——本纲要给出的建议如果被某个 Agent 用"文档已生成"当作"整改已完成"的证据，就是在重犯本纲要试图诊断的病。

---

# 11. 需要你拍板的决策合集

| # | 决策点 | 选项 | 相关证据 |
|---|---|---|---|
| D1 | 三年战略主线归属 | (a) 采纳 STRATEGY-3YEAR-PLAN-2026H2-2029.md 为主线，正式 supersede Panorama；(b) 保留 Panorama 为主线，仅吸收 Plan 的减法纪律；(c) 两者融合，各取所长（本纲要 §4 已尝试给出一种融合读法） | §2.1 第三/四代对比，§4 |
| D2 | 愿景表述口径 | 是否采纳 §4 建议的"一句话愿景+可证伪条件"作为唯一北极星，Panorama 的五平面架构降级为其产品投影 | §4 |
| D3 | gbrain+kairon 合并 | Plan §3.2 标注为"不可逆"，需锁定在 Y1Q3——是否现在就授权，还是需要更多证据再决定 | §7 |
| D4 | research-pipeline ID 碰撞 | 归档 `_truth/scenarios/research-pipeline.yaml` 还是反向操作（归档 scene-card 一侧，理由：_truth 更早、标注 ssot） | §3.4, §6 |
| D5 | ADR-0247 与 ADR-0225/0226 的物理多机张力 | 是否需要一条新 ADR 正式协调"多 Agent 协作优先、物理多机 deferred"与"G-DEL.1 物理多机 caliber 仍是官方标准且 fail-closed"之间的矛盾，还是维持现状（两者事实上都不被强制执行） | §3.6（治理集群原文），Cluster B 发现 |
| D6 | Wave/Gate 与 BET 对齐工作的优先级 | 是否现在就立项（新 BET）推进这项蓝图自己承认未完成的对齐工作，还是维持现状（两套体系并行，靠人工记忆桥接） | §3.2, §7 |
| D7 | 治理基建链（第二代文档）的去留 | 是彻底归档（承认它已被场景优先转向取代），还是保留部分内容（如 X1-X4 治理轴定义仍在用） | §2.1, §9 |

---

# 12. 落地路径

本文档本身不改变仓库任何内容。若你认可以上判断，建议按以下顺序推进（对应 Task #20 会产出的完整落地包，含可直接复制的 `gac-worktree.sh claim` 命令序列草稿）：

1. 在你自己的终端里，为"文档收敛"本身认领一个独立 worktree（遵照你们自己的 D0-D6 铁律，不在共享 Workspace 里直接改）。
2. 逐条落地 §9 的文档处置建议，每条走一次 ADR-0203 的 start→claim→verify→closeout，不合并成一个大 PR。
3. 优先处理 §11 中你已经能立即拍板的项（建议从 D4 research-pipeline ID 碰撞开始，这是影响面最小、最容易独立验证的一项）。
4. D1/D2（战略主线归属、愿景口径）建议放在你有整块时间、且能同时召集"人类主权裁决者"视角时再处理，因为它们会连带影响后续所有 BET 的立项口径。

下一步我会按你的原计划继续产出 Task #20 的落地包（含具体 worktree 命令草稿与治理联动说明的可执行版本），以及 Task #21 的关键事实自检，作为本文档的配套交付物。
