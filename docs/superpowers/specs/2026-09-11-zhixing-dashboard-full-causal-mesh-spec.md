---
id: SPEC-2026-09-11-ZHIXING-DASHBOARD-FULL-CAUSAL-MESH
title: 43191 主权控制面全要素因果图谱串联与六面动态闭环规范
status: accepted
version: 1.0.0
owner: governance-team
created: 2026-09-11
last_updated: 2026-09-11
binding_bet: BET-Y1Q4-T8-25
---

# 43191 主权控制面全要素因果图谱串联与六面动态闭环规范

## 1. 规范目标与边界

本规范定义 43191 织星主权控制面 (Zhixing Dashboard) 的核心数据流与交互拓扑协议，确立：
1. **数据真值单向流动原则**：43191 作为只读视窗，所有数据必须从大设备底层（Git main、OMO Event Ledger、AetherForge 算力池、3Y-BET-LEDGER、受管文档库）单向采集与安全投影，严禁直接执行写操作或外部网络逃逸；
2. **六面正交投影协议 (Six-Planes Orthogonal Projection Protocol)**：将系统所有运行状态与静态资产严格归入控制面、知识面、业务面、进化面、协作面、交付面六大独立维度；
3. **主权模型驱动与约束协议**：显式度量 AetherForge 本地 8000 算力池吞吐、显存水位与推测解码，同时在任务视窗中强加 GaC 57 项门禁与工作树沙箱防腐膜。

## 2. 六面维度契约

| 维度 | 英文标识 | 核心实体 (Entity Kinds) | 关键数据源 | 退出门/检验标准 |
|---|---|---|---|---|
| **控制面** | `control` | `gate`, `gate_evidence`, `policy`, `daemon` | `governance-checks.yaml`, launchd, resident daemon | 57 项 GaC 门禁全绿，A1~A9 状态保真 |
| **知识面** | `know` | `document`, `memory_type`, `memory_route`, `adr` | 49 份受管文档库, `memory-os.yaml` | SHA-256 校验通过，与 BET 双向反向链接 |
| **业务面** | `business` | `scene_card`, `journey`, `work_case` | `scene-cards/`, `work-cases.yaml` | 具备人类主权负责人 (夏明星) 署名确认 |
| **进化面** | `evolution` | `retro`, `sema_crystallization`, `metric` | `.omo/_knowledge/retros/`, SEMA 结晶 | 每次交付有踩坑反思沉淀与自学习反馈 |
| **协作面** | `swarm` | `agent_observation`, `bos_service`, `compute_telemetry` | AetherForge 8000 探针, Multica, OMO workflow | 显存与模型池动态可见，多 Agent 身份统一 |
| **交付面** | `delivery` | `bet`, `campaign`, `milestone`, `spec`, `evidence` | `3y-bet-ledger.yaml`, PR commit tree | 真实排期动态甘特图，DoD 与三维凭证完整 |

## 3. 全要素双向因果拓扑定义

在 `strategy_projection.py` 中，定义如下正交关联边：
- `accepts_spec`: `bet` -> `spec`
- `guided_by_document`: `bet` -> `document`
- `implemented_by_bet`: `document` -> `bet`
- `driven_by_model`: `agent_observation` -> `compute_telemetry`
- `governed_by_policy`: `compute_telemetry` / `agent_observation` -> `policy`
- `satisfies_gate`: `bet` -> `gate`
- `adjudicated_by`: `work_case` -> `human_principal`
- `crystallized_from`: `sema_crystallization` -> `retro`

## 4. 验证与验收准则

1. `refresh.py` 15 个数据源全部以 `OK` 状态返回，退出码为 0；
2. 43191 前端六大主权平面结构完整呈现，无旧版写死日期（2026-09-08 等）；
3. 交付面甘特图随 `3y-bet-ledger.yaml` 动态更新；
4. 协作面实时上报 AetherForge 16 模型池与显存使用。
