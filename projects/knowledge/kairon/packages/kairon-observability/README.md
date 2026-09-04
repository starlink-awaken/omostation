---
title: README
type: doc
---

# kairon-observability

> Monitoring and observability toolkit for kairon

从 `shared-lib` 拆出的独立包（2026-06-06）。

## 模块

| 模块 | 功能 |
|------|------|
| `metrics` | Prometheus 风格指标收集器（计数器/仪表/直方图） |
| `alerts` | 基于规则的告警引擎 |
| `anomaly` | 滑动窗口 Welford 在线异常检测 |
| `dashboard` | 健康仪表板数据提供者 |
| `slo` | SLO 跟踪器（p99 延迟 + 可用性） |
| `monitoring_metrics` | D-Harvest 特定指标收集 |

## 依赖

- 零运行时依赖（仅 stdlib）
- Python >= 3.10

## 测试

```bash
uv run --package kairon-observability pytest tests/ -v
# 6 passed
```
