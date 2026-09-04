---
type: ssot
---

# projects — 项目容器与子仓库治理入口

## 定位

`projects/` 是多项目容器，承载多个子仓（如 `projects/cockpit`、`projects/omlxc`、`projects/omo` 等）。该目录仅负责项目边界治理，不作为单一代码构建单元。

## 首先阅读

1. 根仓治理指引：[`../AGENTS.md`](../AGENTS.md)
2. 子项目本地治理指引：每个子仓自身 `AGENTS.md`
3. 确认 `git status --short`（根仓与目标子仓）
4. 对需求迭代按 ADR-0203 走 `agent-workflow`（`bootstrap -> start -> claim -> verify -> closeout`）

## 约束

- `projects/` 下多数目录是独立子模块；非显式要求，不直接在容器层面进行业务变更。
- 修改子模块时，优先在子模块内部提交与变更闭环，再在必要时更新根指针（若有）。
- 未经明确授权，不将运行态状态文件、历史证据文件、缓存状态作为新治理目标写入该层级。

## 目录地图（快速入口）

- `projects/AGENTS.md`：本目录治理说明
- `projects/README.md`：本入口文档
- 各子项目 `AGENTS.md`（如 `projects/omo/AGENTS.md`）
- [项目分层索引](../docs/project-registry.yaml)

## 维护动作

- 变更新子项目：先补齐子项目的 `README.md`、`AGENTS.md` 与 `CLAUDE.md`（存在时）
- 变更跨项目时同步更新：`docs/project-registry.yaml` 与生成索引
- 每次交付前执行 `make gac-local-gate --scope files --file projects`（按需）或对应子项目检查命令

