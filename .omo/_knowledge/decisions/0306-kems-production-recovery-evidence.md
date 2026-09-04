---
id: ADR-0306
title: KEMS 生产持久化恢复证据作为放行前置条件
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../docs/KEMS-PRODUCTION-PLAN.md
  - ../../../docs/KEMS-PILOT-ROADMAP.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../../projects/runtime/scripts/kems_production_preflight.py
  - ../../../projects/runtime/docs/KEMS-PRODUCTION-HANDOFF.md
---

# ADR-0306: KEMS 生产持久化恢复证据作为放行前置条件

## 背景

KEMS 的图谱工程能力已经覆盖 SQLite 本地开发和 PostgreSQL 生产目标，但本地测试通过不等于
生产数据可恢复。生产派发同时依赖真实标注集、企业连接器、OMO 批准和模型 acceptance；如果
持久化恢复没有独立证据，系统无法证明图谱在故障后仍可重建，也无法对 RPO/RTO 做出可审计承诺。
此前生产文档只把 PostgreSQL 备份/恢复演练列为部署事项，Runtime preflight 没有把它作为统一
放行门，存在工程完成状态与生产证据状态错位的风险。

## 决策

1. KEMS 生产 preflight 和 closeout 必须 fail-closed 地要求
   `kems.persistence-recovery-evidence.v1`。缺失、不可读、字段非法或状态不是 `passed` 时，
   生产状态只能是 `blocked`，不能执行真实派发。
2. 证据至少包含 PostgreSQL backend、backup/restore drill ID、演练时间、源图谱与恢复后图谱
   snapshot SHA-256、实际和目标 RPO/RTO，以及
   `logical_restore_and_hash_compare` 验证方法。实际 RPO/RTO 必须不超过目标，两个图谱快照 hash
   必须一致。
3. 证据只允许安全元数据和 `vault://evidence/` 引用。Runtime 拒绝 DSN、credential、raw
   document、raw graph content 等敏感或私有内容，并只把白名单字段写入 preflight evidence。
4. 该证据是 M3 持久化和 G2 生产恢复门的外部责任输入，不由 fixture、SQLite 测试或代码自动生成
   伪造。业务/运维完成真实演练后，必须把 artifact 路径、SHA-256、演练 ID 和 RPO/RTO 写入
   release sign-off record。
5. 本 ADR 不改变 OMO 的审批真相、不授予模型 promotion 权限，也不替代真实标注 adjudication、
   ReachBridge endpoint/token、OMO approved task 或 release reviewer 的独立职责。

## 不变量

- 没有有效 recovery evidence 时，preflight/closeout 不能返回生产 ready。
- 源图谱和恢复后图谱快照 hash 不一致时，状态保持 blocked，不允许人工用备注覆盖。
- Runtime 安全证据不含 DSN、凭据、原始文档、原始图谱或 provider 响应正文。
- 本地 SQLite、fixture 和合成测试只能证明工程契约，不能被标记为 PostgreSQL 生产恢复证据。
- 真实外部证据缺失时，系统可以继续做离线开发和预生产验证，但不能宣称 KEMS 生产放行。

## 验收

- Runtime KEMS preflight/closeout/e2e 专项测试通过，覆盖有效证据、缺失证据、hash 不一致和敏感字段拒绝。
- Runtime lint、根仓文档 SSOT、文档声明检查和 Agent Workflow verify/closeout 通过。
- Runtime 文档 PR 合并到子仓 main，根仓更新 submodule pointer、计划、路线图、Workflow Mesh
  实施文档和本 ADR。
- 真实 PostgreSQL 恢复演练、真实 adjudicated manifest、企业连接器和 OMO approved task 仍需由
  业务/运维在独立生产验收阶段提供；未提供前不得关闭生产阻塞项。
