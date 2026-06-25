---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Phase 31 — 可观测性与成本追踪 (Observability & Cost Tracking)

> **状态**: 🟡 部分完成 (P29 + P30 部分)
> 已实现: kairon-governance history.jsonl (P29-W2), daemon (P29-W3), omo 已有 alert/cost/dashboard (20+ 模块)
> 待做: 完整可观测性指标体系 (P31 W2)

> 目标: 建立服务运行时可观测性 + LLM Token 成本追踪 + KEI 审计闭环
> 优先级: P1 | 预估: 2-3 周
> 依赖: Phase 29 (工具体系)

---

## 一、需求分析

### 1.1 问题陈述

四个互相关联的可观测性缺口：

| 缺口 | 现状 | 影响 |
|------|------|------|
| 32 服务无统一面板 | `runtime dashboard` CLI 已实现但无 Web 聚合 | 无法一眼看出全系统健康 |
| KEI 审计日志无人消费 | 11K+ 条记录，但无人分析趋势 | 审计成为"写一次就忘" |
| LLM Token 零追踪 | agent-runtime 和 llm-gateway 都不记录 token | 不知道每个月花多少钱 |
| 无告警闭环 | 服务挂了只写日志，未接入通知 | 半夜服务挂到第二天才发现 |

### 1.2 用户故事

- **作为系统管理员**，我想在统一的 Web 仪表板上查看所有服务状态
- **作为成本管理者**，我想知道每个任务/每个 Agent 消耗了多少 LLM Token
- **作为安全审计员**，我想看到 KEI 沙箱阻断趋势，知道哪些操作频繁被拦截
- **作为值班人员**，我想在服务不可达时收到微信通知

### 1.3 验收标准

- [ ] `runtime dashboard --serve` 提供 HTTP 仪表板，聚合 4 组数据（服务/协议/债务/KEI）
- [ ] llm-gateway 每次 LLM 调用记录 Token 用量到 JSONL
- [ ] `runtime cost estimate` 显示周期 Token 消耗统计
- [ ] KEI 审计 > 10 条阻断记录/hour 触发警告
- [ ] 服务不可达持续 > 5min 推送微信通知

---

## 二、实施计划

### Wave 1: 统一仪表板 (4h) — 部分已完成
- [x] `runtime dashboard` CLI (Phase 28)
- [x] `runtime kei dashboard` CLI (Phase 28)
- [ ] `runtime dashboard --serve` HTTP 模式
- [ ] 聚合 agora/dashboard.html 的 WebSocket 数据
- [ ] 输出: 单页 HTML，每 30s 自动刷新

### Wave 2: KEI 告警回路 (3h)
- [x] `runtime kei dashboard` — 摘要展示 (Phase 28)
- [ ] 添加阻断率阈值检测: `runtime kei alert --threshold 10`
- [ ] 集成 notify-alerts.sh (Phase 28 已创建脚本)
- [ ] 输出: KEI 阻断率超过阈值时调用 WeChat 通知

### Wave 3: LLM Token 追踪 (4h)
- [ ] 在 `llm-gateway` 的 provider.py 中添加 Token 计数
  - 每次 `provider.generate()` 返回后记录 `input_tokens`, `output_tokens`, `model`
  - 写入 `~/.runtime/data/llm_cost.jsonl`
- [ ] 在 `agent-runtime` 的 `_call_llm()` 中已有 usage 字段 → 确保写入 `execution_log.jsonl`
- [ ] `runtime cost estimate --period 7d` 显示周消耗
- [ ] 输出: JSONL 日志 + CLI 查询命令

### Wave 4: 告警通道闭环 (2h)
- [ ] 配置 `notify-alerts.sh` 的 WeChat webhook URL
- [ ] 健康扫描发现服务不可达时调用通知
- [ ] 每日 9:00 自动推送"服务健康摘要"到 WeChat

---

## 三、参考

- 当前 CLI: `runtime/src/runtime/cli.py` (dashboard/kei dashboard/cost)
- LLM 网关: `kairon/packages/llm-gateway/src/llm_gateway/provider.py`
- 通知脚本: `projects/runtime/scripts/notify-alerts.sh` (已创建骨架)
- 审计: `projects/runtime/src/runtime/kei_sandbox.py`
