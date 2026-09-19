---
id: SPEC-2026-09-11-ZHIXING-DASHBOARD-FULL-CAUSAL-MESH
schema_version: specification/v1
spec_version: 1.0.0
title: 43191 主权控制面全要素因果图谱串联与六面动态闭环规范
status: accepted
lifecycle: spec
owner: governance-team
bet_id: BET-Y1Q4-T8-25
binding_bet: BET-Y1Q4-T8-25
created: 2026-09-11
last_updated: 2026-09-11
last-reviewed: 2026-09-11
---

# 43191 主权控制面全要素因果图谱串联与六面动态闭环规范

## 1. 规范目标与边界

本规范定义 43191 织星主权控制面 (Zhixing Dashboard) 的核心数据流与交互拓扑协议，确立：
1. **数据真值单向流动原则**：43191 作为只读视窗，所有数据必须从大设备底层（Git main、OMO Event Ledger、AetherForge 算力池、3Y-BET-LEDGER、受管文档库）单向采集与安全投影，严禁直接执行写操作或外部网络逃逸；
2. **六面正交投影协议 (Six-Planes Orthogonal Projection Protocol)**：将系统所有运行状态与静态资产严格归入控制面、知识面、业务面、进化面、协作面、交付面六大独立维度；
3. **主权模型驱动与约束协议**：显式度量 AetherForge 本地 8000 算力池吞吐、显存水位与推测解码，同时在任务视窗中强加 GaC 57 项门禁与工作树沙箱防腐膜。
