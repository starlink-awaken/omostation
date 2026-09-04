---
type: ssot
---

# AGENTS.md — runtime

## Scope

`runtime/` 是运行态工位目录，包含执行日志、sandbox 与调试产物。该目录默认高波动，优先保持可重建性。

## 编辑限制

1. 阅读根仓 [`../AGENTS.md`](../AGENTS.md)。
2. 禁止手工改写正在运行中的 runtime 产物（如日志/套件中间文件）为稳定配置。
3. 配置性改动先确认是否存在更高层配置源（`protocols/`、`.omo/`、相关项目配置）。

## 常用约定

- `runtime/` 优先用于运行时文件，不作为产品功能源码归档区。
- 持久化配置应下沉到项目配置或 SSOT 对应目录，避免长期漂移。

## 轻量检查

- `git status --short runtime/`
- `rg --files runtime | head`

