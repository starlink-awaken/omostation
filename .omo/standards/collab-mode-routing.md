---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-28
review-state: metadata-only
metadata-migrated-at: 2026-07-31
type: ssot
---

# 协作模式路由标准（P84 · ADR-0253）

> SSOT 决策: `.omo/_knowledge/decisions/0253-p84-collab-mode-routing-after-k4.md`  
> 证据: `.omo/_knowledge/audits/2026-07-28-p84-k4-batch2-control-experiment.md`

## 何时用协作管线

- 多文件 **无共享写冲突** 的批量修复
- 可 fan-out 的独立子任务（墙钟 ≈ max(worker)，且 max 不会被木桶拖垮）
- 场景库批量生成 / 对抗集补跑（能力轨）

## 何时用单 agent

- 归因 / 分类 / 简单分析 / 顺序审查
- 强依赖链（A→B→C）且未验证协作分解收益
- 预计单 worker 即可在 << 协作 launch overhead 内完成
- **细粒度微任务 / 纯 CPU 场景 fan-out**（K4 批次3/4: 协作墙钟 0.3–0.7× 单 agent — ADR-0255）
- 冲突消解与失败注入的默认路径：先跑 **机制检测**（ADR-0254），勿默认多 worker 并行

## 执行检查清单（agent）

1. 任务是否可拆成 **≥3 个真正独立** 子任务？否 → 单 agent  
2. 子任务是否会争同一 claim path / 同一文件？是 → 单 agent 或串行 claim  
3. 是否对照实验中已证明该类型协作劣？是 → 单 agent（K4 批次2 类）  
4. 协作 run 必须：dispatch 数 = 完成 + 显式失败（静默丢失 = 0）

## 红线

- 掩盖协作负收益 = 违规  
- 构造场景不计产能轨  
