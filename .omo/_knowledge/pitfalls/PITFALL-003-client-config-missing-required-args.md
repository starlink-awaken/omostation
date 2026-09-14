---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-08-18
type: ssot
---
# PITFALL-003: 客户端 MCP 同步脚本缺失核心参数

- **条目编号**: `PITFALL-003`
- **严重等级**: `HIGH`
- **关联架构**: ADR-0191 多客户端 Documents MCP 自动挂载
- **首次踩坑**: 2026-08-16

---

## 1. 踩坑现象与根因

### 现象
在调用 `ecos-constraint documents sync-clients` 时，若未提供 `--mode` 或参数默认值缺失，导致脚本解析失败或静默未生成配置文件。

### 规避配方
所有 CLI 子命令必须在 argparse 中提供明确的 `default` 与 `choices`，并在同步逻辑中包含 `--dry-run` 保护机制。
