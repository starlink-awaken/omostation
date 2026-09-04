---
title: README
type: doc
---

# kairon-plugin-sdk

> Plugin development toolkit for kairon

从 `shared-lib` 拆出的独立包（2026-06-06）。

## 公共 API

```python
from kairon_plugin_sdk import BosPlugin, PluginContext
```

- `BosPlugin` — 所有 kairon 插件的抽象基类
- `PluginContext` — 运行时插件执行上下文

### CLI 工具（可选）

```bash
pip install kairon-plugin-sdk[cli]
```

提供 `click` + `yaml` 驱动的插件生命周期管理 CLI。

## 依赖

- 零运行时依赖（仅 stdlib）
- 可选 CLI 依赖: `click>=8.0`, `pyyaml>=6.0`, `requests>=2.0`
- Python >= 3.10

## 测试

```bash
uv run --package kairon-plugin-sdk pytest tests/ -v
# 12 passed
```
