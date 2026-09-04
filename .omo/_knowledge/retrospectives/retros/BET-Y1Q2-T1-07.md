---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-07 复盘
type: retro
---
# BET-Y1Q2-T1-07 复盘

## Q1 实际耗时 vs appetite？超出比例？

约 1 个工作日内完成，核心实现、返工和验收约 2 小时，低于 2 days appetite，未超出。主要等待来自外部 Agent 的分析超时、模型切换、子仓持久化及跨仓真实验证。

## Q2 done_when 是否全部通过？哪条没过，为什么？

按可信本地单用户的冻结范围，5/5 通过：OMO 从真实 Ledger 重放 Episode M2；重复构建保持确定性且 Ledger count/hash 不变；Role Portfolio 按 principal 隔离；Inbox 仅输出 FYI/Approval/Decision 卡片；Cockpit GET API 已通过真实跨仓调用。

证据：OMO Episode/Role/Ledger 定向回归 185 passed；Cockpit API 定向回归 20 passed；真实 FastAPI GET 返回 `200 / ok=true / status=live`，得到 1 个 Episode、6 个成员事件和 1 张 Inbox 卡片，Alice/Bob 隔离且 Ledger count/hash/control 均不变；独立 reviewer 最终给出 APPROVE。

家庭成员、多租户、跨组织、极端并发、分布式精确一次、完整 UI 与审批写回继续作为 non_goals，不计为本 BET 未通过。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. OpenCode 的低成本模型在实现前长时间过度分析，超过窄任务时限后被停止并切换 CodeBuddy；便宜额度不等于低监督成本。
2. 本机没有可直接调用的 Kilo CLI，不能把“工具名可用”当成“运行入口已就绪”。
3. Cockpit 单测通过不等于跨仓集成通过：早期测试 monkeypatch 了 OMO builder，根仓 OMO gitlink 未同步时真实 import 仍失败。
4. 子仓 commit/tag/push 后还必须更新根仓 gitlink，并从根仓只读锚点运行一次非 mock GET，才能证明实际组合可用。
5. 投影不需要新增数据库、事件协议或顶级服务；复用 LedgerBroker、Episode M2、RoleAssignment 和现有 Workflow Mesh API 已足够完成个人版闭环。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）

两个子仓合计新增 4 个文件、1,045 行：OMO 2 个文件 781 行，Cockpit 2 个文件 264 行。根仓仅更新两个 gitlink、BET 台账和本复盘；GaC 规则 +0、ADR +0、脚本 +0、顶级项目 +0、Ledger DDL +0。

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. W2-04 是个人版只读投影，不是完整 Digital Twin：不要顺手扩成多租户、审批系统、通知中心或新前端。
2. 跨子仓交付必须先 push 子仓分支/tag，再 bump root pointer；最终验收必须从根仓锚点真实 import 和调用，mock 测试只能证明包装层。
3. 下一阶段应优先选一个真实个人角色与 Episode 旅程做端到端 dogfood，以 outcome 验证价值，不再继续堆治理抽象。
4. 家庭角色仍在长期模型内，但短期应先复用同一 principal/role/episode 结构，以第二个低风险场景验证，不另起家庭专用架构。
