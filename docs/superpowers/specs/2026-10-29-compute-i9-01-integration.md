---
title: "compute-i9-01 Integration"
status: accepted
version: 1.0.0
decision_ref: decision://accepted/BET-Y2Q4-T10-279
accepted_by: user
accepted_at: 2026-10-29
---

# 目标

将 `compute-i9-01` 纳入现有 OMOStation 数字大脑体系，作为受治理的高性能 CPU 执行节点；不建立第二套任务控制面，不把该节点变成独立调度器或权威任务库。

# 范围与阶段

## Phase 0：Discovery（只读）

- 核实节点硬件、固件、微码、操作系统、网络位置、所有权与授权边界。
- 核实 OMOStation、Work-Agent、Fleet-Ops、Local-Ops 的真实注册、Runtime 接口、Worker admission 与 Claim/Lease 语义。
- 输出事实矩阵、阻断项、变更申请；证据不足时保持 `HOLD`。

## Phase 1：Provisioning Proposal（提案，不执行）

- 提出 Ubuntu Server、rootless 容器、Tailscale、受限工作目录、监控与恢复方案。
- 定义 `compute-i9-01` 身份、CPU/内存/存储预算、网络白名单与恢复边界。
- 未获独立明确授权，不重装系统、不格式化磁盘、不改 BIOS、不改防火墙、不部署远端服务。

## Phase 2：Worker Integration（仅在 Phase 1 获批后）

- 复用 OMO TaskEnvelope、Claim、Lease、Runtime Adapter 与 Harness。
- 仅提供受限 Code/Test/Batch Worker；首批总运行 Worker ≤ 2，同一仓库写入并发 ≤ 1。
- 使用隔离 worktree、最小权限、网络白名单、资源预算、独立验证与人工审批。
- 禁止新建持久任务数据库、第二 Dispatcher/Broker、未授权 Multica/Orca 权威 Task、自动 merge/push main。

## Phase 3：Verification（部署授权后）

必须分别留下可复核回执：

1. 节点上线、断网与重连；
2. OMO 授权任务启动、完成与独立报告；
3. Worker 超时与 Lease 回收；
4. 并发写入冲突阻断；
5. CPU/内存超额限制；
6. 未授权宿主机及外部访问拒绝；
7. 独立测试报告与人工审批；
8. 失败恢复、清理与回滚。

# 安全与停止条件

- 默认只读；任何写入仅限批准的工作目录和原生授权路径。
- 不使用家庭/单位之间的敏感数据，不扫描未授权网段，不把节点事实扩写成部署成功。
- Agent 自报成功不等于 `WorkflowVerified`。
- 遇到证据不足、权限冲突、重复失败、资源超限、控制面不明或回收不完整，立即 `HOLD`。
- 现有 `services/lb-worker` 的 rootful systemd + SQLite 方案不作为本 BET 的最终集成实现；不得在其上直接开通生产流量。

# 当前已知前置阻断

- 节点现场为 Windows 11 Pro；用户目标的 Ubuntu/rootless 方案尚未获重装授权。
- 现场报告记录 CPU 为 i9-14900HX，与目标文字“i9-14900”不一致，需保留型号差异并由人确认。
- V34 unit-zone native spec 仍为 DRAFT，Linux isolation backend、Worker admission、Runtime 接线与网络边界尚未接受。
- OMO 当前 Worker registry 没有 `compute-i9-01` 的 admitted/enabled/resource/capability 定义。
- 现有 `lb-worker` 默认使用持久 SQLite 状态库且以 root 运行，不满足本 BET 的最终约束。
- Unit/family 网络位置、设备所有权与部署授权尚未形成独立证据闭环。

# 交付面

- `reports/COMPUTE-I9-01-INTEGRATION-DISCOVERY-20261029.md`
- `reports/COMPUTE-I9-01-PHASE0-PHASE1-20261029.md`
- `tasks/PROGRESS.md`
- 本规范与对应 BET ledger binding
- 后续仅在授权后新增隔离后端、Worker registry、部署脚本、监控与验证回执；不提前创建伪实现或安装脚本。

# 完成判据

本 BET 只有在 Phase 0 事实矩阵、Phase 1 提案、人类授权、Phase 2 受限 Worker 接入、Phase 3 八项回执、独立报告、回滚证据与人工 Golden Slice 验收全部可追溯时，才可进入 `delivery_accepted`。当前只完成 Discovery 与提案阻断登记，不宣称节点已接入。
