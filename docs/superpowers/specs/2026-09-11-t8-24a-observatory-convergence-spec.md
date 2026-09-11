---
schema_version: specification/v1
spec_version: 1.0.0
title: Observatory 统一数据面收敛与增量流式投影服务规范 (BET-Y1Q4-T8-24A)
bet_id: BET-Y1Q4-T8-24A
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-11
---

# Observatory 统一数据面收敛与增量流式投影服务规范 (BET-Y1Q4-T8-24A)

## 1. 目标与背景
将 43191 端口全景观测站经过实战检验的高保真采集与投影内核（`catalog_sources`, `strategy_sources`, `observatory_query`）完整收敛并入 `projects/cockpit/src/cockpit/observatory/`，提供 REST 与 SSE 增量推送接口，并引入六大主权平面本体论元模型、多跳因果拓扑穿透与本地 AetherForge 主权 Hybrid RAG 检索支持。

## 2. 核心架构约束
1. **本体论六大主权平面元模型**：
   - 包含 Control, Knowledge, Business, Evolution, Swarm, Delivery 6 大正交平面；
   - 声明 8 对双向语义谓词与四大形式化公理（AXIOM-01 只读单向流动、AXIOM-02 三维凭证闭环、AXIOM-03 主权算力物理隔离、AXIOM-04 工作树物理隔离）。
2. **多跳因果穿透引擎**：
   - 在 128KB 视窗响应预算内，支持双向 BFS 拓扑遍历（`trace_lineage`），提供紧凑实体投影与阶层折叠。
3. **本地主权 Hybrid RAG**：
   - 100% 依托本机 AetherForge（端口 8000），使用 BM25 词法检索 + BGE-M3 向量检索 + BGE-Reranker-v2 交叉重排，杜绝公网流量外泄。
4. **单向只读与保真度对账**：
   - 数据面严格作为大设备真值的增量投影视窗，严禁包含任何直接写回主仓的操作。

## 3. 验收与验证准则
- `projects/cockpit/tests/test_observatory_unified.py` 全量通过；
- 与 43191 live 观测站实现 10 大操作语义对齐；
- 本地治理门禁 `make gac-local-gate` 保持 100% 绿灯。
