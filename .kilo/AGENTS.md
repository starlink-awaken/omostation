---
type: ssot
---

# AGENTS.md — .kilo

## Scope

`.kilo/` 承载本地工具运行与治理协作过程中的运行时文件与辅助配置，属于偏运行面目录。

## 编辑前置

1. 阅读根仓 [`../AGENTS.md`](../AGENTS.md) 与相关子域说明。
2. 对 `git status` 异动保持最小化，避免将临时产物常驻。

## 治理约束

- 优先使用脚本和 CLI 产出文件，不手工构造长期数据。
- 运行态中间文件尽量可重建，禁止在该目录提交不必要的历史快照。
- 大文件或日志类产物应通过 `.gitignore` 或外部持久化治理。

## 常用命令

- `ls -la .kilo/`
- `git status --short .kilo/`
- `python3 -m py_compile .kilo/**/*.py`

