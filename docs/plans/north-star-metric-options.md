---
status: active
lifecycle: plan
owner: xiamingxing
last-reviewed: 2026-08-28
---

# 北极星"工作交付"真指标口径选项 (决策辅助, 2026-08-28)

> 背景: X3 工作交付维度现为"待接入"(旧 mtime 伪指标已废)。只有你能定口径。
> 目标: 一个**不可被 agent 自刷**的口径 (Goodhart 防腐, ADR-0431 D4 原则)。

## 选项对比

| 方案 | 口径定义 | 防腐强度 | 实施成本 | 适合场景 |
|------|----------|----------|----------|----------|
| **A 人工确认制** | 你在 briefing/草稿上标记"已用"才算 1 分; agent 无权写此字段 | ★★★ 唯一无法自刷 | 低 (inbox 加确认标记) | 最真但依赖你到场 |
| **B 发出即计** | mail_sender 实际发出的每封工作邮件 = 1 分 (SMTP 回执级, 非草稿) | ★★☆ 发送需 HITL 确认, 半真 | 低 (sender hook) | 高频但可能含转发性噪音 |
| **C 旅程走完制** | admin-notification-workflow 走完 7 步到 submitted = 1 分 | ★☆☆ journey 可被 agent 自动跑完 (会自刷!) | 零 (已有) | ❌ 不推荐做主指标 |
| **D OA 回响制** | Seeyon OA 里由你提交的表单/公文数 (抓 OA 已提交列表) | ★★★ OA 是外部系统, agent 无写权 | 高 (OA connector) | 最真但要先接 OA |
| **E 混合制 (推荐)** | 主指标 = A (你确认的分), 辅指标 = B (自动统计参考, 标注"含水分") | ★★★ 主指标防腐 | 低 | 真实+自动兼顾 |

## 推荐: E 混合制

```
north_star.work_delivery = {
  confirmed: <你标记的分>   ← 主指标 (人工确认, 每周 5 分钟)
  auto_sent: <发送数>       ← 辅指标 (自动, 仅参考)
}
显示: confirmed 为主, auto_sent 折线对照
```

**理由**: C 会被 agent 刷 (旅程自动跑完≠真实价值); D 依赖 OA 接入进度;
A 最真但纯人工无自动对照; E 用 5 分钟/周的人工成本买到不可腐蚀的主指标,
同时保留自动指标做趋势对照。

## 实施路径 (选定后)

E 方案: inbox briefing 头部加 `[ ] 本周确认: N` 复选 (人工改数字),
north_star_meter_v2 读此字段为主指标, mail_sender 计数为辅。
改 2 个文件, 半小时。
