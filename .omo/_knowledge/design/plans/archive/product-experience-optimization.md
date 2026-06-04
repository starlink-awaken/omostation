# Product Experience Optimization

> 基于 60 场景分析和 Top 10 用户旅程验证的修复计划

## Wave 1 — P0 即时修复 (健康体验)

| # | 场景 | 问题 | 修复 |
|---|------|------|------|
| W1.1 | D1 系统健康 | 只测 CLI 存在，不测端口是否通 | `workspace status` 做 HTTP health check |
| W1.2 | C7 结果通知 | 研究完成后无系统通知 | macOS `osascript` 系统通知 |
| W1.3 | B2 知识搜索 | 不能全文搜索 | SQLite FTS5 全文搜索 |

## Wave 2 — P1 体验补齐 (核心场景)

| # | 场景 | 问题 | 修复 |
|---|------|------|------|
| W2.1 | A2 追问 | 不调用真实 minerva | `research --ask` 调用 minerva |
| W2.2 | A1 深度研究 | 无 Web UI 浏览 | `workspace dashboard` 一键拉起 |

## Wave 3 — P2 体验增强

| # | 场景 | 问题 | 修复 |
|---|------|------|------|
| W3.1 | E3 全量测试 | 无聚合报告 | `make test` 用 rich 汇总 |
| W3.2 | F1 每日简报 | 无自动生成 | `workspace daily` 命令 |

## 验证方法

每个修复完成后：
1. `python3 -m workspace <command>` 运行验证
2. 检查 LSP diagnostics
3. 更新 USER_JOURNEYS.md 进度
