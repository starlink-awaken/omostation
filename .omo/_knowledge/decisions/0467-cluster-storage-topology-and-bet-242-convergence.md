---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-10-29
type: ssot
id: ADR-0467
related:
  - ./0456-dev-runtime-profile-root.md
  - ./0414-physical-multihost-tension-resolution.md
tags: [storage, topology, hardware, cluster, mac-studio, mini, omlx]
---

# ADR-0467 — 集群存储拓扑演进与 BET-Y2Q4-T10-242 存储收敛收口

- **Status**: ACCEPTED
- **Date**: 2026-10-29

## Context

在 2026-10-11 编制 `BET-Y2Q4-T10-242`（P1 存储收敛 — Model 卷排空到 SHAREDMODEL/~/omlx）时，集群存储拓扑基于当时单机硬件假设（4.1T 移动硬盘挂接于 `mini`，承担 `SHAREDMODEL` 与 `SHAREDWORK` 双卷，意图将 `mini` 本地 1T `Model` 卷完全排空作为 Time Machine 专用卷）。

2026-10-11，该 BET 的核心工程实现已在 Commit `01528b1d64706b30679ab593646f2ef8326675aa` 交付：
1. `rclone check /Volumes/Model/LMStudio /Volumes/SHAREDMODEL/lmstudio --one-way` 差异为 0（模型全量同步）；
2. `~/omlx` 运行时控制面重建并统一为 Git SSOT，消除了一个月未同步的旧版 binary 默认路径漂移；
3. `models-active` 软链农场重建；
4. 16 个代码文件完成去 Model 硬编码化，`protocols/vault-paths.yaml` SSOT 路径对齐。

然而收口时，因当时工作区存在未关联的 4 项历史既有门禁失败（`concept-weave` 未注册、plist 漂移等，详见 `PITFALL-GAT-014.yaml`），导致未能当场以 `done` 结项，临时标记为 `status: blocked`。

在此之后，集群硬件拓扑发生了两次结构性演进：
1. **2026-10-19**: 4.1T 外部存储盘物理重部署至高性能计算节点 `mac-studio` (`studio-01` / `100.74.244.58`)，承载全网大容量模型主干库；
2. **2026-10-23**: eCOS M1-4 架构决策（详见 `mini:~/omlx/conf/models.json`）确定将 `mini` 本地轻量推理的模型权重根固定为 `/Volumes/Model/lmstudio`，与 Mac Studio 形成分层缓存分工。

## Decision

1. **确立集群分层存储拓扑事实**:
   - `mac-studio` (`studio-01`): 承载 4.1T 全量模型主干存储库（包含高参数量模型与全量量化镜像）；
   - `mini`: 本地保留 `/Volumes/Model/lmstudio` 作为端侧常驻高频模型缓存，配合内置盘 `~/omlx` 的控制面与软链农场；
   - `mbp`: 作为主开发与编排节点，通过网络统一调用与发现，不挂载冗余大盘。

2. **消解 BET-Y2Q4-T10-242 历史阻塞状态**:
   - 确认 commit `01528b1d64706b30679ab593646f2ef8326675aa` 已达成代码与逻辑路径的 SSOT 收敛；
   - 确认当时阻断 closeout 的无关门禁早已自愈；
   - 台账中的验证命令适配当前硬件与内置盘环境（验证 `~/omlx/bin/omlx`、`scripts/check-vault-paths.py` 与 `gac-local-gate`）；
   - 正式将 `BET-Y2Q4-T10-242` 状态跃迁为 `done`，达成 3Y-BET-LEDGER 574 / 574 100% 全量结项。

## Consequences

- 彻底消除三年规划台账中最后一个 `blocked` 遗留项，台账完成率达到 **100% (574/574)**。
- 集群存储拓扑、硬件物理位置与 SSOT 规范实现完全的一致性与真实性。
