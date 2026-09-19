---
status: active
lifecycle: plan
owner: governance-team
last-reviewed: 2026-08-13
last_updated: 2026-09-03
title: 编排器无关交付合同 MVP 实施计划
type: doc
---

# 编排器无关交付合同 MVP 实施计划

> 对执行者：严格按 TDD 推进；不得改 ECOS 既有 M2、Workflow Mesh 状态机或新增第二套任务真相。

**目标：** 复用 ECOS 已有 `WorkPacket`、`CompletionManifest`、`VerificationReceipt`，在 OMO 中补齐外部编排器候选交付到 `EvidenceRecorded`、独立验证和 `WorkflowVerified` 的真实运行链。

**架构：** ECOS 继续拥有合同、规范哈希和验证回执；OMO 只增加一个薄协调模块，负责身份链、范围、receipt 与事件顺序。外部编排器只实现 `dispatch / observe / interrupt / collect` 运输协议。本轮 Kandev 仅使用离线 JSON fixture，不启动服务、不联网。

**技术栈：** Python 3.13、Pydantic/ECOS generated models、OMO Workflow Mesh、pytest、Ruff。

---

## Task 1：登记 BET 与冻结设计边界

**文件：**

- 修改：`docs/plans/3y-bet-ledger.yaml`
- 新增：`docs/superpowers/specs/2026-08-13-orchestration-contract-mvp-design.md`
- 新增：`docs/superpowers/plans/2026-08-13-orchestration-contract-mvp.md`

**步骤：**

1. 登记 `BET-Y1Q2-T1-14`，依赖 `BET-Y1Q2-T1-13`，风险 L1，周期 1 天。
2. 将写面限制为本任务三份根文档、一个 OMO 生产模块、一个 OMO 测试模块和复盘。
3. 固定 non-goals：不启动 Kandev、不接第二 adapter、不改 Mesh 状态机/DDL/UI/CLI。
4. 运行：

   ```bash
   uv run --with pyyaml python bin/plan/bet-ledger.py lint
   git diff --check -- docs/plans/3y-bet-ledger.yaml docs/superpowers/specs/2026-08-13-orchestration-contract-mvp-design.md docs/superpowers/plans/2026-08-13-orchestration-contract-mvp.md
   ```

## Task 2：先写 OMO 合同接线负向测试

**文件：**

- 新增：`projects/omo/tests/test_orchestration_contract.py`

**步骤：**

1. 写 fixture：构造 schema-valid WorkPacket、CompletionManifest、Kandev transport payload 和 succeeded Workflow Mesh run。
2. 写 RED：adapter 元数据变化不得改变 `packet_hash`。
3. 写 RED：packet hash 被篡改时返回稳定 `packet_hash_mismatch`，事件数不变。
4. 写 RED：`changed_paths` 越出 `scope.write_surfaces` 时返回 `manifest_scope_violation`，无 evidence/verified。
5. 写 RED：transport failed/unavailable 时返回 `transport_failed`，不得生成 succeeded evidence。
6. 写 RED：同一 external task 或 manifest identity 的冲突重放返回 `manifest_conflict`。
7. 写 RED：verdict 为 `revise` / `reject` 时不得追加 `WorkflowVerified`；缺 evidence 返回 `evidence_missing`。
8. 运行并确认因生产模块不存在或行为缺失而失败：

   ```bash
   cd projects/omo
   uv run python -m pytest tests/test_orchestration_contract.py -q
   ```

## Task 3：实现单模块协调器与离线 Kandev mapper

**文件：**

- 新增：`projects/omo/src/omo/orchestration_contract.py`
- 修改：`projects/omo/tests/test_orchestration_contract.py`

**步骤：**

1. 定义 `OrchestrationContractError(reason, message)`，只使用设计中的稳定错误族。
2. 定义窄 `OrchestratorAdapter` protocol：`dispatch`、`observe`、`interrupt`、`collect`；本轮只提供纯函数式 Kandev fixture mapper，live 方法固定拒绝 `not_enabled`。
3. 用 ECOS `WorkPacket.model_validate` 与 `CompletionManifest.model_validate` 验证结构；用 `canonicalize` + `compute_packet_hash` 重算合同哈希。
4. 校验 identity chain：BET、workflow run、packet、assignment、external task、receipt 必须一致；adapter metadata 不进入 packet hash。
5. 用路径规范化实现 write surface 子集校验；拒绝绝对路径、`..` 越界与未声明路径。只支持精确文件或目录前缀，不实现 glob 引擎。
6. 将成功 transport 归一化为现有 `external-connection-receipt/v1`，调用 `record_external_receipt` 幂等追加 `EvidenceRecorded`。
7. 接收 ECOS `VerificationReceipt`；只有 `accept`、hash 一致、只读 direct measurement 且 evidence 已存在时，才幂等追加 `WorkflowVerified`。`revise/reject` 仅返回候选状态。
8. `WorkflowVerified` 的 event/idempotency identity 绑定 `workflow_run_id + receipt_hash`；重复相同回执不增事件，冲突由 Mesh fail closed。
9. 运行 GREEN：

   ```bash
   cd projects/omo
   uv run python -m pytest tests/test_orchestration_contract.py -q
   uv run ruff check src/omo/orchestration_contract.py tests/test_orchestration_contract.py
   ```

## Task 4：跨合同回归与独立验证

**文件：**

- 修改：`projects/omo/tests/test_orchestration_contract.py`

**步骤：**

1. 增加一条完整 golden path：Kandev fixture → CompletionManifest candidate → EvidenceRecorded → VerificationReceipt accept → WorkflowVerified。
2. 对三个观测同时断言：协调器返回值、Workflow Mesh 有序事件、最终 snapshot 状态。
3. 运行 OMO 定向与既有 Mesh/receipt 回归：

   ```bash
   cd projects/omo
   uv run python -m pytest \
     tests/test_orchestration_contract.py \
     tests/test_omo_external_receipt.py \
     tests/test_workflow_mesh.py \
     tests/test_workflow_operations.py -q
   ```

4. 运行 ECOS 既有合同回归，证明没有复制或破坏 M2：

   ```bash
   cd projects/ecos
   uv run python -m pytest \
     tests/test_mof_agent_execution_contracts.py \
     tests/test_work_packet_compiler.py \
     tests/test_sr06_rehearsal.py -q
   ```

5. 由非实现 Agent 只读复核：身份链、事件顺序、负向路径、测试真实性和范围。

## Task 5：复盘、治理验证与 D0 交付

**文件：**

- 新增：`.omo/_knowledge/retros/BET-Y1Q2-T1-14.md`
- 修改：`docs/plans/3y-bet-ledger.yaml`

**步骤：**

1. 复盘记录复用资产、误判纠正、真实证据、残余边界与后续 adapter 顺序。
2. 仅在全部定向测试和独立复核通过后，把 BET 更新为 `done` 并写可复现 evidence。
3. 执行 workflow verify/closeout；环境/基线失败与任务失败分开陈述。
4. OMO 子仓先 commit/push/tag，再更新根 gitlink；根仓按 lane 拆分文档/治理与 pointer commit。
5. 建 PR，等待平台 checks 全绿后合并；最后安全移除本 worktree。

## 断路器

- 需要修改 Workflow Mesh 状态机或 Ledger DDL：立即停止。
- 需要启动/联网调用 Kandev 或接入第二 adapter：拆新 BET。
- 生产模块超过两个或需要新顶级目录：缩回纯 OMO 协调器。
- 无法在同一 run 上证明 `EvidenceRecorded → WorkflowVerified`：不得宣称完成。
