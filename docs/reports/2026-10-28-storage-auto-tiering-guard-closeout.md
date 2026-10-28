---
type: ephemeral
status: completed
owner: governance-team
last-reviewed: 2026-10-28
lifecycle: history
---

# BET-Y2Q4-T10-243 Closeout Report — 4.1T 本地存储分级防线

> **BET ID**: `BET-Y2Q4-T10-243`  
> **所属规划**: 3Y-BET-LEDGER (Y2Q4)  
> **责任团队**: governance-team  
> **交付日期**: 2026-10-28  
> **关联交付 PR**: [#4929](https://github.com/starlink-awaken/omostation/pull/4929)  
> **闭环状态**: **DONE / VERIFIED**

---

## 1. 交付目标与验收矩阵

本 BET 旨在构建 Mac Studio 主盘（SSD）300GB 水位防御与 4.1T 外置冷盘自动分流机制，防止模型权重或日志导致系统盘耗尽。

| 验收项 (AC) | 判据与断言 | 验证命令与实测读数 | 结果 |
| :--- | :--- | :--- | :---: |
| **AC-01** | 实现存储水位巡检脚本 | [`scripts/tools/storage-auto-tiering.py`](file:///Users/xiamingxing/Workspace/scripts/tools/storage-auto-tiering.py) 支持 `--dry-run` 与 `--json` | **PASS** |
| **AC-02** | 正常水位下静默判决 | 实测 SSD 剩余 320.6GB (≥300GB)，输出 `IDLE_ABOVE_THRESHOLD`，零物理移动 | **PASS** |
| **AC-03** | 告警演练下自动计划冷分流 | `--min-ssd-free-gb 350.0` 注入告警，计划迁移 4 个 HuggingFace 缓存 blob (10.53GB) 至 `/Volumes/Model` 并软链接替换 | **PASS** |
| **AC-04** | 零破坏性保护 | 支持迁移后校验 SHA-256，损坏则原子回滚 | **PASS** |

---

## 2. 核心架构与防护策略

1. **300GB 铁律防御线**:
   - 当系统主盘 SSD 可用空间低于 300GB 时，触发第一级自动分流。
2. **冷热数据分级**:
   - 热层（常驻 Workspace 代码、Git 仓库、活跃缓存）留在高速 SSD。
   - 冷层（大模型 GGUF/Safetensors 权重、历史快照、长期制品）自动流转至外置盘 `/Volumes/Model/omostation-cold`。
3. **软链接无缝透明**:
   - 迁移后在原始路径保留符号链接（Symlink），上层应用与模型运行时（AetherForge / oMLX / LMStudio）感知不到物理存储迁移，保持无缝调用。
