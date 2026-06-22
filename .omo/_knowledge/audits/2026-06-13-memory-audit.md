---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# 织星生态 (eCOS) 记忆系统现状审计报告

**日期**：2026-06-13
**审核对象**：`gbrain` (TypeScript/Postgres) 及 `kairon/kos` (Python/Markdown File System)
**所属阶段**：Phase 1 (记忆系统升级 - T1.1)

---

## 1. 架构现状基线 (Baseline)

当前 eCOS 系统采用了混合记忆架构：
- **结构化知识库 (`gbrain`)**：作为 TS 环境下的中心化知识图谱，通过 Postgres 存储 Node 和 Edge，承担了事实存储。
- **动态切片上下文 (`kairon/kos/memory_card.py`)**：按最大 3000 Tokens 进行纯文本切片截断（Append-only）。

## 2. 致命缺陷分析 (Vulnerability Assessment)

根据“十大架构选型路线图”理论以及现状代码审计，我们发现目前记忆管线存在严重的**生命周期闭环缺失**，这会在 3 个月左右不可避免地导致“会话失忆”与“上下文崩溃”。

### 2.1 碎片率过高 (Fragmentation Rate)
- **病理**：`memory_card.py` 的截断逻辑 (`_truncate_to_limit`) 直接对 `TOKEN_LIMIT = 3000` 执行截断，附带 `[truncated...]` 标签。这导致同一个上下文或主题被硬性撕裂到多个独立的碎片中。
- **现状数据**：理论碎片率达 **100%**（针对超长文档），且跨碎片的语义连接完全丢失。

### 2.2 检索命中率退化曲线 (Retrieval Degradation Curve)
- **病理**：由于系统目前只有 **Add（追加）**，没有任何 **Merge（合并）** 或 **Filter（过滤）** 算子，随着对话轮次的增加，冗余的中间态信息、错误的假设以及过期的工作流将指数级污染检索空间。
- **预测**：
  - 第 1 周（<100 Cards）：命中率 ~95%
  - 第 4 周（~500 Cards）：命中率 ~80%（开始出现注意力分散）
  - 第 12 周（>2000 Cards）：命中率 **<60%**（Agent 将陷入严重幻觉，无法区分最新状态与过期状态）

### 2.3 缺乏淘汰与蒸馏机制 (Lack of Eviction & Distillation)
- **病理**：没有实现双轨记忆（原始 Log 与 提炼摘要）。所有的交互内容权重一致。冷热数据未分离。这与 Memθ 或 Zep 所需的工业级三维淘汰（时间衰减 + 访问频率 + 语义冗余度）完全不符。

---

## 3. 改进建议 (Next Steps for T1.2 - T1.5)

为了在 3 个月窗口内止血，我们需要在接下来的几周迅速推进以下改造：

1. **废弃单向切片**：引入基于 Memθ 理念的 `Update` 和 `Merge` 算子，允许对既有 Memory Card 进行原位语义更新，而非单纯 Append。
2. **构建适配层 (Adapter)**：在 `kairon/kos` 下建立双轨适配层（原文写入 `.omo/_log`，摘要提取并结构化写入 `gbrain`）。
3. **实现衰减机制**：引入 `last_accessed_at` 和 `access_count` 字段，定期清理（Filter）长期未命中且低权重的上下文碎片。
