---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
---
# AGENTS.md — .agents

## Scope

.agents 存放智能体运行说明、技能与治理相关文档，是能力与组织的入口层。

## Rules

- 阅读根仓的 AGENTS.md 后再编辑。
- 保持技能文档与文档索引同步。
- 未经确认，不新增持久化状态文件到该目录。
- 需求变更按 ADR-0203 工作流闭环提交。

## 自动化与技能约定（2026-10-25）

- 新增或修改 skill、workflow、定时任务时遵守根仓 `AGENTS.md` §13：步骤标出参照 / 判断 / 执行 / 人工审批四类，审批是阻塞步；一次运行落一条结构化记录（`inputs` / `basis` / `approver` / `result` / `duration_ms` / `model_usage`）；领域实体与判准引用共享语义层文档，不写进 SKILL.md 的 prompt 正文。
- 治理层单独做成产品层、多级或按额度分级审批、审计记录导出到合规系统、FDE 式驻场交付四项不做；技能文档不得把上述四项写成本目录的待办或能力承诺。
