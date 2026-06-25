---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# OPC M1.5 Gate B2 收口 (Cross-repo governance baseline)

> **状态**: ✅ Gate B2 收口 (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P1.5 跨仓治理基线 = 本 session §19 R45-R56 + E1-E4 实质化对账
> **目的**: 关闭 OPC M1.5 评审关 (Gate B2), 推进到 P2 (Memory spine)
> **链接**: OPC-PHASE-PLAN.yaml OPC-P1.5 / OPC-P15-T1-T5 / §19 路线图

---

## §1.0 一句话总结

**OPC-P1.5 (Cross-repo governance baseline) Gate B2 收口！** 本 session 实质化的 14 项跨仓治理债工作（§19 R45-R56 + R50 gbrain + B-1 kairon + B-2 metaos + E2 dispatcher + E4 SSOT 文档）1:1 命中 OPC-P1.5 acceptance criteria，跨仓治理基线就绪。

## §1.1 OPC-P15 5 任务 vs 本 session 实质化对账

| OPC-P15 任务 | R# | 实质化产出 | 验收状态 |
|--------------|----|-----------|---------|
| **OPC-P15-T1**: r46-metrics-baseline | R46 | `omo audit-rollout --include-metrics` 跨仓聚合 §17 R0 | ✅ done |
| **OPC-P15-T2**: r47-trend-baseline | R47 | ci-lint.yml artifact + `scripts/plot-metrics.py` (3 张 ASCII bar chart) | ✅ done |
| **OPC-P15-T3**: r48-kairon-probe-actions | B-1 | `kairon-utils/append_only_log.py` + ContentVersionTracker + eidos_to_bos 迁移 | ✅ done |
| **OPC-P15-T4**: r49-metaos-probe-actions | B-2 | `metaos/audit.py` + D Layer + A2A audit trail | ✅ done |
| **OPC-P15-T5**: r50-gbrain-probe-actions | R50 | `gbrain/src/core/append-only-log.ts` + 6 个 appendFileSync 迁移 | ✅ done |

**5/5 任务实质化完成**。

## §1.2 OPC-P1.5 Gate B2 acceptance 对账

| Gate 条目 | 命中 |
|----------|------|
| R46-R50 findings referenced from the OPC task plan | ✅ §19 路线图 + 战报 + OPC-P1.5 tasks T1-T5 全部 listed |
| kairon classified as real multi-package workspace | ✅ B-1 探路报告 + 接入实施 (16 live packages) + audit.sh + cron |
| metaos + gbrain missing .omo planes explicit debt/tasks | ✅ B-2 audit.py + R50 append-only-log.ts 新增 |
| Cross-repo metrics expectations attached to later phase gates | ✅ R47 ci-lint monthly trend + E2 dispatcher (5 仓 worst=R0) |

**4/4 acceptance criteria 命中**。

## §1.3 跨仓债 E1-E4 收口进度

| 债 | 状态 | 详情 |
|----|------|------|
| **E1** omo → gbrain 跨仓链接 | 🔄 探路 | OMO 仓内 `bos_metrics` 是否加 eidos/gbrain 数据源 (R57+) |
| **E2** metaos D Layer 接入 omo audit-rollout | ✅ done | E2 P0 dispatcher 跑通 5 仓 worst=R0 |
| **E3** kairon async 适配 (ContentVersionTracker) | ⚠️ 半完成 | B-1 用同步 AppendOnlyLog 包 async, fcntl 阻塞 event loop 风险未解 |
| **E4** AppendOnlyLog 跨仓 SSOT 收口 | ✅ done | 5 仓对比表 + §17 schema 文档化 |

**E2/E4 已收口 (2/4)**, E1/E3 待 R57+ 探路。

## §1.4 累计债密度 (R0 优秀)

| 仓 | 接入 | 债密度 | 健康度 |
|----|------|--------|--------|
| omo | ✅ 原生 | 0.0 | R0 |
| runtime | ✅ R51-R53 | 0.0 | R0 |
| gbrain | ✅ R50 | 0.0 | R0 |
| kairon | ✅ B-1 | 0.0 | R0 |
| metaos | ✅ B-2 | 0.0 | R0 |

**5 仓累计债密度 0.0% (R0 优秀)** — §17 健康度跨仓 100% 收敛。

## §1.5 双轨制对账 (§19 + X-Plane)

| 轨 | 范畴 | 当前状态 |
|----|------|----------|
| **§19 跨仓债** | 5 仓债密度 + §17 健康度 | ✅ R0 优秀 (5/5 仓) |
| **X-Plane 治理** | X1-X4 探活覆盖 | ⚠️ 0.775 (待 R57+ `omo x-axis check` 定位) |

**§19 债清零** ≠ X-Plane 0.775——后者是 X-Plane 探活设计产物，**不人为校准**（G1 让失控可见）。

## §1.6 R57+ 候选 (OPC-P2 Memory spine)

OPC-P1.5 Gate B2 收口后，自然进入 **OPC-P2 (Memory spine)** — 记忆脊柱：

| 任务 | 描述 | 工作量 |
|------|------|--------|
| **OPC-P2-T0** | persistence-prerequisites (K2 持久化风险收口 — E1/E3) | 1 Round |
| **OPC-P2-T1** | memory-boundary (gbrain / KOS / cockpit local DB / 外部文档边界) | 1 Round |
| **OPC-P2-T2** | memory-uri (`bos://memory/**` 路由策略) | 1 Round |
| **OPC-P2-T3** | recall-flow (collect → ingest → search → output → archive) | 2 Round |
| **OPC-P2-T4** | source-map (source / timestamp / owner / freshness) | 1 Round |
| **OPC-P2-T5** | memory-metrics (recall precision / attribution coverage) | 1 Round |

---

**OPC M1.5 Gate B2 收口。** §19 R45-R56 + R50 + B-1 + B-2 + E2 + E4 全部命中 OPC-P1.5 acceptance。R57+ 推进 OPC-P2 Memory spine 候选已列。
