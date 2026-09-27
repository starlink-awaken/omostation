---
schema: md/v1
status: draft
lifecycle: plan
owner: portfolio-steward
last-reviewed: 2026-09-26
type: ephemeral
bet_id: BET-Y2Q4-T4-01
---

# 真实业务首单候选盘点

本文件是 [BET-Y2Q4-T4-01](./3y-bet-ledger.yaml) 的**决策输入**，不构成对首单的选择、正式新 BET、真实业务运行或价值证明。盘点时间为 2026-09-26 UTC。评估依据是 [三年战略](../STRATEGY-3YEAR-PLAN-2026H2-2029.md)、[场景优先愿景](../VISION-ROADMAP.md)、[三年全景](../STRATEGY-3YEAR-PANORAMA.md)、[组合视图](./3Y-BET-PORTFOLIO.md)、[首场景路线](./scenario-phase1-roadmap.md)、当前 Ledger、4 张下述场景 YAML 及 [当前 goals](../../.omo/goals/current.yaml)。`current.yaml` 自称 `entry_gate: deprecated-use-bet-ledger`，本次仅作历史需求线索，进度和授权以 Ledger/OMO 为准。

## 首单选择原则

优先让一个真实输入变成主人愿意确认、采用或签发的**业务产物**；复用已交付能力，不先建基础设施。候选交付实施预计均不超过 3 个工作日，这只是初步 appetite 假设，选定并取得真实输入后需由正式 BET/Spec 重估。成功必须有原始输入、人工基线、产物、独立回执、人工裁决和后续实际消费记录；仅生成文件、PR 或任务不算业务价值。没有样本时标 `UNPROVABLE`，不填假基线。

| 排序 | 候选业务交付 | 草案目标与 ≤3 天范围 | 可度量 done_when / 价值判据 | 主要风险与停止条件 |
|---|---|---|---|---|
| **1** | **一份真实会议纪要 → 决议行动包** | 1–2 天。使用一份主人有权处理的真实纪要，复用会议督办/收件箱能力，提炼决议、责任人、期限、待确认问题，交给主人修订并决定是否发送或派发。只产出一个可审阅行动包，不自动外发。依据：[会议督办场景卡](../scene-cards/meeting-supervision.yaml)、[第一波场景](../VISION-ROADMAP.md)。 | 至少一份真实纪要的逐条决议映射、主人确认/修改/拒绝记录；产物被实际打开、采用、派发或引用。记录决议捕获率、漏项/错配数、人工修订分钟数、随访任务完成/逾期，和纯人工基线比对。若没有真实输入和人工裁决，结果 `UNPROVABLE`。 | 会议内容可能受限，责任人与时限抽取易错；缺授权输入或错误责任归属时停在人工审阅，不派发。与已 `done` 的会议/收件箱 BET 做功能去重，首单只验证真实消费残差。 |
| **2** | **一周真实工作记录 → 可提交周期报告与证据包** | 1–3 天。用一个实际周期内的 PR、文档、事项和结果，输出给主人可签发的周报/阶段报与逐项来源。依据：[周期报送场景卡](../scene-cards/periodic-reporting.yaml)、[第二波场景](../VISION-ROADMAP.md)。 | 一份真实报告，每条完成/阻塞声明都有来源；记录人工编制基线分钟数、核对/修订分钟数、证据完整率、最终采用/签发与否。未被主人采用不能记为已创造价值。 | 已有工程记录不等于业务结果；跨系统来源可能陈旧或误归因。若来源不足以支撑关键声明，删去该声明或停为草稿，不自动提交。 |
| **3** | **一个真实项目 → 监督健康与干预简报** | 2–3 天。选一个本人负责的真实项目，汇入现有进度、会议行动和交付记录，输出风险、待决策项与可选择的干预建议。依据：[项目监督场景卡](../scene-cards/project-supervision.yaml)、[第二波场景](../VISION-ROADMAP.md)。 | 每个风险有原始事实、影响、建议与反证；记录主人采纳/驳回的风险项、从发现到决策的时间、实际干预及后续结果。只报“红黄绿”或静态健康分不算完成。 | 项目数据不全时误报成本高；若状态、责任或影响不能由真实源证明，则不出确定性判断，不代主人承诺干预。 |
| **备选** | **真实调研问题 → 引用型洞察备忘录** | 2–3 天。为一个已明确的政策/技术问题生成可引用的短备忘录。依据：[研究场景卡](../scene-cards/research-pipeline.yaml)。 | 主人审阅并采用/修改结论，逐条引用可核验，记录节省时间和修订量。 | 场景卡目前存在 `draft/inactive` 与后续 `active/assisted` 的状态/审批字段矛盾；未澄清准入前不优先启动。 |

**排序理由**：候选 1 是愿景第一波，任务可被真人逐条确认，副作用可保持为零；候选 2 的交付物可以直接署名消费，但证据映射成本更高；候选 3 依赖前两类信号，输入不足会产生高误报风险。备选调研卡状态矛盾，暂不作为首单。排序是建议，不是 Principal 决定。

## 当前证据缺口与去重

[场景路线](./scenario-phase1-roadmap.md) 仍把持续真实输入、稳定标注集和生产启用决策列为缺口；4 张场景卡的 `sample_refs` 使用 `vault://redacted/...`，本次无法独立验证其内容或主人可使用权。Ledger 中已有会议、收件箱、公文与信号处理能力 BET 标记 `done`；这些是**工程状态**，不能替代本次真实输入→人类裁决→实际消费。首单应复用能力，只补结果链，不重建解析器、Dashboard、Mesh 或第二任务队列。

主人在 [决策卡](../../.omo/tasks/planned/BET-Y2Q4-T4-01-DECISION.yaml) 选择后，另由合法流程起正式交付 BET。选择前只读收集：真实输入的存在/权限、纯人工耗时、期望产物与签发者、允许的输出渠道、可观察消费事件、停机/撤回办法。未取得这些事实时，不将任一候选标为已可执行或已证明正净值。

**复核方法**：`python3 bin/plan/bet-ledger.py show BET-Y2Q4-T4-01`、`python3 bin/plan/bet-ledger.py claim-check BET-Y2Q4-T4-01`、逐张读取 `docs/scene-cards/{meeting-supervision,periodic-reporting,project-supervision,research-pipeline}.yaml`、核对 `docs/VISION-ROADMAP.md` 与 `docs/plans/scenario-phase1-roadmap.md`。本次未调用外部系统或查看任何真实私有样本。
