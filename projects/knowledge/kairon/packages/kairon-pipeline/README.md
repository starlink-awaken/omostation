---
title: README
type: doc
---

# kairon-pipeline

> D-Harvest data pipeline for kairon

合并 `sources` + `extractors` + `quality` + `integration` 子包（2026-06-06）。

## 模块

| 模块 | 功能 |
|------|------|
| `source_connectors` | 原始内容载体（RawContent） |
| `source_registry` | 数据源注册表 |
| `source_priority` | 收获任务优先级队列 |
| `extract_base` | 规范输出模型（StructuredKnowledge） |
| `extract_html` | HTML 内容提取器 |
| `quality_gate` | 质量门控（内容验证） |
| `downstream_trigger` | 下游处理触发器 |

## 依赖

- 零运行时依赖（仅 stdlib）
- Python >= 3.10

## 测试

```bash
uv run --package kairon-pipeline pytest tests/ -v
# 5 passed
```
