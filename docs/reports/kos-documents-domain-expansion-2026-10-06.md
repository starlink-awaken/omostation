---
schema: md/v1
status: active
lifecycle: plan
owner: governance-agent
last-reviewed: 2026-10-06
type: ephemeral
title: "KOS Documents 域扩展摄入报告 — 规自委/国转中心/@公共/合同法规"
---

# KOS Documents 域扩展摄入报告（2026-10-06）

## 摄入结果

| 来源 | found | indexed |
|---|---|---|
| @工作文档/规自委/_knowledge/（12 业务子域） | 45 | 45 |
| @工作文档/国转中心/_knowledge/ | 38 | 38 |
| @公共/_knowledge/（资产卡片 + 模板 + 标准） | 16 | 16 |
| @工作文档/合同法规/ | 76 | 76 |
| _entities/ ×3（规自委/国转中心/@公共） | 52 | 52 |
| **合计** | **227** | **227**（去重净增 194） |

- documents 总量：13,588 → **13,782**
- 备份：.bak-20261006（254MB，摄入前快照）

## 消费验证

- "地价评审 A-B 双评估" → 命中地价评审业务模型 + 评估台账 ✅
- "低效用地再开发" → 命中业务模型 ✅
- "绩效指标三可原则" → 命中资产卡片 ✅
- "ADR-0453" → 仍命中 ✅（先前摄入不回退）
- 全文检索"信息化项目 全生命周期 房山区" → 10 results ✅

## 治理知识资产覆盖（摄入后）

| 域 | 知识资产 | KOS 状态 |
|---|---|---|
| .omo/_knowledge | 455 ADR / 550 retro / 37 pattern / 47 pitfall | ✅ 已入（T3-03） |
| @工作文档/卫健委 | 144 号纪要等 OCR + 工作文档 | ✅ 已入 |
| @工作文档/规自委 | 12 业务子域知识模型 | ✅ 本轮 |
| @工作文档/国转中心 | 调研/政策/生态运营 | ✅ 本轮 |
| @工作文档/合同法规 | 政策/合同法规 | ✅ 本轮 |
| @公共 | 资产卡片×5 + 模板 + 标准 | ✅ 本轮 |
| @驾驶舱 | V1-V8 视图体系 | 系统生成，暂不入 |

## 提案

- kos-cli ingest 加 --recursive 支持（pitfalls 子目录 41 篇遗漏）
- ingest metadata 加 source_root 字段（保留目录溯源）
- KOS_HOME 权威源契约已在 standards/kos-home-authority.md 落地（ADR-0460 默认项 a）
