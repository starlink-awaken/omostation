---
title: Batch2 B3 — 第 4/5 角色扩容评估（不实装）
date: 2026-07-24
type: audit
batch: 2
---

# 角色扩容评估（research / delivery）

## 候选

| Role | 价值 | 边界 | 风险 |
|------|------|------|------|
| **research** | KOS 检索/文献合成；减轻 engineering 调研负载 | 只读知识面；不可 claim 代码路径 | 幻觉污染 SSOT；与 audit 证据边界模糊 |
| **delivery** | 交付卡登记 / X3 冲刺登记；收口 BRIEF 周报 | 只能写 delivery/X3 投影；无代码写权 | 凑数交付（已禁）；与 governance closeout 重叠 |

## 建议

- **Batch 3 前不实装**（工单 §F / B3 仅评估）。
- 若拍板：先 ADR 扩展 ROLE_CATALOG（能力集 + can_send/can_recv），再 ≥10 任务试点。
- 拒绝路径：S3/涌现角色任何提案须附 kill-switch 评审（ADR-0221 族）。

## 结论

价值中等、边界可画清，但 **S2 三角色常态化未跑满 2 周** 前扩容 ROI 偏低。推荐 Inbox 提案卡挂起，人类 Batch3 拍板。
