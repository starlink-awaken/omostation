---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
---

# P87: 系统性优化复盘

> 触发: 2026-08-23 系统性优化返工后复盘

## 1. 返工事实

| 返工点 | 影响 | 根因 |
|--------|------|------|
| `tests/` 物理分层导致 54 个 collection errors | 全量回滚 | 路径依赖扫描缺失 |
| `ruff` config 加载行为误判 | 浪费 2h+ 调试 | 未用 `--show-settings` 验证 |
| `git stash` 冲突处理 | `.omo` 文件冲突未预期 | 直接 `--theirs` 可能丢变更 |

## 2. 判断错误

1. **tests/ 移动导致路径断裂**：120+ 文件移动后 54 个 collection errors，最终全部回滚
2. **ruff config 加载行为误判**：浪费 2h+ 调试，实际是 monorepo config 查找逻辑
3. **git stash 冲突处理**：未预期到 `.omo` 文件冲突，直接 `--theirs` 可能丢失变更

## 3. 返工根因

- 路径依赖扫描缺失（`parents[1]` 出现 100+ 处）
- PoC 范围不足（5 文件通过就全量推进）
- 工具行为假设（未用 `--show-settings` 验证）

## 4. 正确做法

- 零侵入优先：pytest markers 替代物理分层
- 验证前置：5% 抽样 → 全量 dry-run
- 基线纪律：删除脚本 = 维持配额，而非更新 baseline

## 5. 固化措施

- Memory: 本文件
- AGENTS.md: §11 文件/目录移动纪律
- Hook: `bin/gac/path-dependency-scan.py`
