# 2026-08-25 常驻事件源与 Phase 7 架构演进设计规范

> 对应 BET: `BET-Y1Q3-T10-12`  
> 状态: In Progress  
> 关联 ADR: ADR-0425, ADR-0426

## 1. 目标与背景

将常驻事件源全面接入 Agora 2.0 守护总线与生命周期重放闭环，提供：
1. `cockpit daemon install-service` 系统级自愈托管；
2. `bin/gac/daemon-stress-test.py` 50-Agent 混沌压测套件（P99 < 5ms）；
3. `bin/gac/ast-merge-mesh.py` AST 语义级三路合并驱动。

## 2. 核心架构与契约

* **总线端口**: `:7432` WebSocket / FastAPI
* **Git 自定义 Merge Driver**: `merge=ast-mesh` 在 `.gitattributes` 中声明
* **压测吞吐**: 1,000 QPS，0 丢包
