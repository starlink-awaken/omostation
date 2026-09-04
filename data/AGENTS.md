---
type: ssot
---

# AGENTS.md — data

## Scope

`data/` 承载仓库级数据资产与中间结果，属于可治理目录；优先维护数据边界与访问行为的一致性。

## Reading Order

1. 根仓 [`../AGENTS.md`](../AGENTS.md)
2. 目标子目录对应的 `AGENTS.md`（如存在）

## 治理规则

- 不在未授权场景下改写已归档或历史来源不明的数据文件。
- 数据文件新增/删除/重分流必须在同一 PR 中更新数据来源说明（如有）。
- 避免直接提交大体量运行时临时产物；必要时通过外部存储或 `.gitignore` 管控。

## 常用命令

- `ls -la data/`
- `git status --short data/`
- `rg --files data | wc -l`（目录规模检查）

## 风险与边界

- `data/` 不是服务运行时配置面，禁止把运行态状态文件放入该目录持久化。
- 若涉及敏感字段变更，先确认是否受 `.omo/_truth`/治理域约束。

