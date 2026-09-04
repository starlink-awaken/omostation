---
title: 战略-治理-场景收敛总纲 · 落地包（草案）
status: active
type: landing-package
owner: 夏明星（人类执行）
created: 2026-08-15
adopted: 2026-08-15
lifecycle: entry
companion-doc: docs/STRATEGY-CONVERGENCE-MASTER-2026-08.md
executed_in: work/bet-y1q1-t6-01
bet: BET-Y1Q1-T6-01
note: >
  2026-08-15 按 grill Q1–Q7 在隔离 worktree 执行。
  原稿 does_not_change 仅描述云端起草阶段，不约束本次落地。
last-reviewed: 2026-08-18
---

# 说明

这是《战略-治理-场景全域收敛总纲》的配套落地包，对应 Task #20。三部分内容全部是**草稿/建议**，需要你自己在本地终端里，按你们自己的 D0-D6 铁律和 ADR-0203 流程执行——我没有、也不会替你在真实仓库里跑任何一条命令。

---

# 一、Worktree 认领命令序列（草稿，供你直接复制到本地终端）

命令模式完全照抄自 `docs/plans/3Y-BET-LEDGER.md` §3 的标准流程（认领→执行→收尾），只是把 bet-id 换成了本次收敛工作专属的一个新条目。**在你把这个新 BET 正式登记进 `docs/plans/3y-bet-ledger.yaml` 之前，`claim-check` 这一步会失败**——这是第一步需要你自己判断的地方：本次"文档收敛"工作应该挂在哪条轨道下（本纲要 §10 建议 T6-SUBTRACT 或 T8-SURFACE，因为其本质是"减少表层声明冗余"）。

```bash
# ===== 第 0 步：你需要先决定的事（本命令序列假设你已决定） =====
# - bet-id：建议 bet-y1q1-t6-doc-converge（或你自己命名，需先在 3y-bet-ledger.yaml 里登记）
# - 轨道：T6-SUBTRACT（建议）或 T8-SURFACE
# - write_surfaces：本次工作预计只涉及 docs/ 下的 markdown frontmatter 字段
#   （status/lifecycle/supersedes/superseded-by）与少量场景卡/journey-spec 的
#   status/activation 字段修正，不涉及任何运行时代码

# ===== 第 1 步：查看当前可认领项，确认新 bet 已登记 =====
python3 bin/plan/bet-ledger.py status

# ===== 第 2 步：认领前置检查（会打印后续所有命令） =====
python3 bin/plan/bet-ledger.py claim-check BET-Y1Q1-T6-DOC-CONVERGE

# ===== 第 3 步：开独立隔离工作树（防止被其他并发 agent 清理，
#              这正是 2026-08-06 那次 601 行代码永久丢失事故的教训） =====
bash bin/gac/gac-worktree.sh claim bet-y1q1-t6-doc-converge

# ===== 第 4 步：起 ADR-0203 workflow =====
uv run --with pyyaml python bin/agent-workflow.py start governance-state-mutation \
  --profile governance-agent \
  --objective "BET-Y1Q1-T6-DOC-CONVERGE：收敛战略/治理/场景类文档的声明冲突（详见 STRATEGY-CONVERGENCE-MASTER-2026-08.md）"

# ===== 第 5 步：逐个 claim 本轮要动的写面（示例，按你实际决定的处置范围调整）=====
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path docs/STRATEGY-INDEX.md
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path docs/STRATEGY-ALIGNMENT-AUDIT.md
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path .omo/_truth/scenarios/research-pipeline.yaml
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path docs/scene-cards/research-pipeline.yaml
# ...其余路径按 STRATEGY-CONVERGENCE-MASTER-2026-08.md §9 的处置总表逐条补充

# ===== 第 6 步（执行阶段，人工完成，不是命令）=====
# 只改上面 claim 过的路径；non_goals（例如不改任何运行时代码/不动 3Y-BET-LEDGER.md 本身的数据）
# 是硬边界；每改完一个文件立刻 git add（D0 铁律）。

# ===== 第 7 步：收尾 =====
git add <所有本轮改动的文件>
python3 bin/plan/bet-ledger.py verify BET-Y1Q1-T6-DOC-CONVERGE --execute
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>

# ===== 第 8 步：写复盘（D5 铁律：无 retro 不得置 done）=====
#   .omo/_knowledge/retros/BET-Y1Q1-T6-DOC-CONVERGE.md
#   建议至少记录：本轮实际处置了 STRATEGY-CONVERGENCE-MASTER-2026-08.md §9 总表里的哪几项，
#   哪几项刻意跳过（附原因），净减少了多少份 status:active 但内容矛盾的文档

# ===== 第 9 步：提交与释放 =====
bash bin/gac/gac-worktree.sh submit bet-y1q1-t6-doc-converge
```

**建议拆分**：不要把 §9 总表的全部条目塞进一个 bet 里。按总纲 §12 的建议，第一批（也是风险最低、最容易独立验收的）只做 D4 决策（research-pipeline ID 碰撞），可以单独起一个更小的 bet，命令序列同上，只是 write_surfaces 只有 2 个文件。

---

# 二、ADR 草案骨架（供你决定是否正式提交）

以下是一份 MADR 风格的 ADR 草案骨架，对应总纲 §11 的 D1（三年战略主线归属）——这是本次审查中发现的、影响面最大、最需要正式 ADR record 的一项决策。文中方括号内容需要你本人确认或修改；本草案不预设结论，只是把决策空间结构化。

```markdown
# ADR-0XXX: 三年战略主线归属裁决——STRATEGY-3YEAR-PANORAMA.md 与
# STRATEGY-3YEAR-PLAN-2026H2-2029.md 的 supersede 关系

- Status: PROPOSED
- Date: [填写日期]
- Deciders: 夏明星

## Context（背景）

`docs/STRATEGY-3YEAR-PANORAMA.md`（v2.3，2026-08-03，STRATEGY-INDEX.md 标注为
"主方案"）与 `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md`（2026-08-06，
`status: draft`/`lifecycle: proposal`，frontmatter 已声明
`supersedes-candidate: [docs/STRATEGY-3YEAR-PANORAMA.md]`）目前同时标注
`status: active`/`draft`，描述同一 2026H2-2029 时间窗口，但给出不同的：

- 北极星表述（"每周成功完成并被实际消费的闭环旅程数" vs 隐含在
  "有效工作旅程完成率"等更早文档中的措辞差异）
- 项目组合目标（Panorama：18 个项目，无数字终态；Plan：明确 18→8 合并目标）
- 成熟度阶梯（Panorama：I1-I5 五级；Plan：L0-L3 四级自治阶梯）
- 路线图分期（Panorama：Stage A-F；Plan：Y1/Y2/Y3 财年制，附硬性季度门禁）
- 对当前系统成熟度的判断（Panorama："已完成从零散工具集合到受治理 AI
  操作系统骨架的跨越"；Plan：诊断"系统表面积已超过一个人能保持真实的极限"，
  引用 2026-08-06 实测的 344 份 ADR/72.6 万行代码/134 条治理规则为证据）

## Decision Drivers（决策驱动因素）

- [ ] Plan 的诊断是否仍然成立？（建议核对最新 `.omo/state/system.yaml` 的
  当前规模指标，与 Plan §0.1 引用的 2026-08-06 基线对比，看趋势是否恶化/改善）
- [ ] 2026-08-15 交接手册显示的 T7-01/T1-08 声明-证据落差，是否构成
  "Plan 的诊断持续成立"的新证据？
- [ ] Panorama 的产品结构内容（五平面、四条黄金旅程）是否可以在采纳 Plan
  为主线的前提下，作为"产品职责投影"保留（详见
  STRATEGY-CONVERGENCE-MASTER-2026-08.md §4 的融合读法）？

## Considered Options（备选方案）

1. **采纳 Plan 为主线**：正式完成 Plan frontmatter 已声明的 supersede，
   Panorama 转 `status: superseded`，其产品结构内容按需摘录进 Plan 或独立
   的产品设计文档。
2. **保留 Panorama 为主线**：Plan 转 `status: rejected` 或
   `status: archived`，但吸收其中的"减法纪律"（六项冗余清零目标、
   禁止使用的指标清单）作为 Panorama 的补充章节。
3. **融合方案**：两者都保留，但明确分工——Panorama 负责"产品结构/场景/
   五平面"，Plan 负责"资源约束/治理减法/季度门禁"，互相在 frontmatter
   `related:` 字段中正式关联，不再各自宣称"主方案"。

## Decision Outcome（决策结果）

[待你选择，选择后需要同步完成：
1. 被取代文档的 frontmatter 加 `superseded-by: ADR-0XXX`
2. 取代文档（如适用）的 frontmatter 加 `supersedes: [...]`，`status` 改为
   `active`（如果原本是 draft）
3. STRATEGY-INDEX.md 的"核心文档"表同步更新"主方案"标注
4. .omo/_knowledge/decisions/INDEX.md 登记本 ADR]

## Consequences（影响）

[待补充：本决策会连带影响哪些下游文档的措辞/编号方案，
建议交叉核对 STRATEGY-CONVERGENCE-MASTER-2026-08.md §9 文档处置总表]
```

---

# 三、与现有 SSOT/治理文件的联动说明

本节把总纲 §10 的原则性建议，落成三个具体、可操作的挂钩点，方便你（或你后续再起的 Agent 会话）直接照做，而不需要重新设计机制：

**1. `docs/project-registry.yaml`** —— 这是项目元数据的唯一读源，本次审查发现的唯一一处与之相关的具体缺陷是 BOS service 计数内部不一致（`bos.service_count: 196` vs 同文件内 `agora.bos_services: 200`）。建议的最小改动：核实真实的 `bos-services.yaml` 当前计数，修正其中一处，不需要额外设计。

**2. `.omo/_truth/registry/document-governance.yaml`** —— 这是文档生命周期/所有权的注册表，已经内建了 `warning_exceptions` 豁免机制（带 `max_findings` 和 `expires` 字段）。建议：如果你决定分批处理总纲 §9 的处置总表（而不是一次性做完），把尚未处理的项显式登记进这个文件的 `warning_exceptions`，并设一个合理的 `expires` 日期——这样"暂缓修复"这件事本身也是可审计、可追踪的，而不是又一次无声的"声明已知问题、但没人跟踪"。

**3. `.omo/standards/doc-ssot-contract.md`** —— 已有的 `CR-X4-DOC-SSOT` 规则和 `bin/ssot/doc-ssot-lint.py` 工具，理论上应该能抓到本次审查发现的"Phase 编号硬编码进 Markdown"问题（总纲 §3.3，11 套并存编号体系里至少 7 套是硬编码在 Markdown 里的）。建议你实际跑一次这个 lint 工具，看它当前是否真的在拦截这类问题——如果没拦截到，说明规则的检查粒度需要加强（比如把"Phase\s+\d+"这类正则模式也纳入扫描），如果拦截到了但被 `warning_exceptions` 吸收了，那至少现状是"已知且被追踪"而不是"未被发现"，这两者对你判断问题严重程度的意义不同，值得先确认一下现状是哪一种。

**4. `docs/plans/3Y-BET-LEDGER.md`** —— 本落地包第一节建议的新 BET（`BET-Y1Q1-T6-DOC-CONVERGE` 或你自定的编号）需要你先手工登记进 `docs/plans/3y-bet-ledger.yaml`（这是 CLI 的真实 SSOT，Markdown 只是摘要），登记时注意本纲要 §3.2 已经发现的问题——3Y-BET-LEDGER.md 的人类可读表格目前已知不完整（如 T1-05/T1-05A 未出现在表里），登记新 bet 时建议同时核对一下这张表本身是否需要补全，避免问题继续扩大。

---

# 四、给你（或下一个接手的 Agent 会话）的一句话交接

本落地包 + 配套的《战略-治理-场景全域收敛总纲》，是对你仓库当前 81 份核心文档 + 2026-08-15 交接手册的一次只读诊断，核心发现是"声明与事实脱节"这一种病贯穿了愿景、治理、场景、执行四个层级，且在有了专门反制纪律之后依然复现（T7-01/T1-08 是最新证据）。建议不要把这两份文档本身当作新的第六代声明——它们的价值只在于你实际按 §12/本落地包第一节的步骤，在真实仓库里走完至少一轮 ADR-0203 收尾并写出 retro 之后才能兑现。
