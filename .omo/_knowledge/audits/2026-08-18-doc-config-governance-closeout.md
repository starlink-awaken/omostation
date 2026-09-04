---
status: archived
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
archived-since: 2026-08-18
note: "2026-08-18 文档与配置全面治理 closeout (RISE 循环)"
---

# 文档与配置全面治理 Closeout (2026-08-18)

**日期**：2026-08-18
**范围**：root workspace 文档 frontmatter / index / ADR 配置治理
**workflow**：`20260818T071451Z-governance-audit-40cefaad` (governance-audit, bet=BET-Y1Q3-T6-05)
**commit**：`d26bcaf3c`

---

## 0. RISE 循环概览

| 阶段 | 产出 |
|------|------|
| R (Research) | 快照: 工作树 29 / MOF drift 1 LOW / frontmatter 289 warnings / cross-refs 0 |
| I (Investigate) | 279 missing_frontmatter + 10 invalid_metadata; index 缺 omlxc/knowledge; ADR-0413/0414 未登记 |
| S (Strategize) | 全量治理 + 模板推断 (status=active, lifecycle 按目录, owner=governance-team) + 枚举映射 |
| E (Execute) | 169 文件修复, commit d26bcaf3c |
| C (Closeout) | 全门禁验证通过, 本报告 |

## 1. 治理前基线 (R/I)

- `doc-governance-check`: **289 warnings** (279 missing_frontmatter + 10 invalid_metadata)
- `check-index-drift`: project index 缺 `omlxc`、`knowledge` 两项目
- `dir-hygiene`: 1 violation (共享主仓 `ws-t6-05-selfclean/` 空目录, T6-05 bet 残留)
- ADR-0413/0414: 未登记 INDEX.md + frontmatter 不规范 (status=ACCEPTED 大写, 缺 id/lifecycle/owner/last-reviewed)
- cross-refs: 0 断链 (健康基线)

## 2. 治理决策 (S, 用户确认)

1. **全量治理**: 279 frontmatter + 10 枚举 + index + ADR-0413/0414 全修
2. **模板推断**: status=active / lifecycle 按目录映射 / owner=governance-team / last-reviewed=今天
3. **枚举映射**: ACTIVE→active, completed→archived, final→archived, proposed→draft, approved-for-dispatch→active, archived→history, retrospective→history, proposal→plan

## 3. 执行 (E)

### 3.1 lifecycle 目录映射表

| 目录 | lifecycle |
|------|-----------|
| docs/adr/, docs/architecture/, docs/operations/, .omo/_knowledge/decisions/, .omo/standards/ | contract |
| docs/plans/, docs/superpowers/plans/, docs/proposals/ | plan |
| docs/ (根) | entry |
| .omo/_knowledge/patterns/, pitfalls/, designs/, summaries/, sweeps/ | pattern |
| .omo/_knowledge/retros/, audits/ | history |
| .omo/_truth/ | ssot |

### 3.2 修复明细

- 补 frontmatter 4 字段: **169 文件** (120 无 frontmatter 插入 + 49 部分缺失追加)
- 修正非法枚举: **12 项** (10 文件, 2 文件各修 2 字段)
- project index 重新生成: 补 `omlxc`、`knowledge` 项目
- ADR-0413/0414: frontmatter 规范化 (id/status=accepted/lifecycle=contract/owner/last-reviewed) + INDEX.md 登记

## 4. 验证 (C)

| 检查 | 前 | 后 |
|------|-----|-----|
| doc-governance-check | 289 warnings | **0 findings** |
| check-index-drift | FAIL (缺 2 项目) | **ALL PASS** |
| dir-hygiene-check | FAIL | **PASS** (worktree) |
| current-state-coherence | active, 0 warnings | **active, 0 warnings** |
| cross-refs | 0 断链 | 0 断链 |
| workflow verify | - | **PASS** |

## 5. 遗留项 / 观察

1. **共享主仓 `ws-t6-05-selfclean/`**: 空目录残留 (T6-05 bet 产物), 未删除 — 归 T6-05 bet owner 或人类清理, 不属于本次文档治理范围
2. **`.omo/plans/omni-bus-phased-program.md`**: 本地忽略文件, worktree cross-refs 报假阳性 (共享主仓有该本地文件) — 非回归
3. **ADR-0413/0414 `deciders`**: 标记"最终确认 pending" — 决策已 ACCEPTED 但 deciders 字段保留 pending 提示, 人类可后续确认
4. **共享主仓本地 sync**: 本地 main 落后 origin/main — 用户 `git pull` 处理

## 6. 诚实话语

- 本任务为 **文档/配置治理**, 未改任何代码/行为
- frontmatter 的 status/lifecycle 是模板推断值, 个别文档的**语义准确性**需后续人工抽查 (工具无法语义判断)
- 遗留的共享主仓子模块 dirty (13 个) 为 worktree claim init 副作用, 未提交

## 7. 补充: CI capability-registry drift 处理 (2026-08-18 晚)

**现象**: PR CI 的 `capability-registry drift` job 失败 (continue-on-error, 非阻塞)。
**根因**: 既存 CI 债 — main 的 `docs/generated/capability-registry.yaml` 是旧版
(cli_commands 138), 完整子模块环境 sync-all-docs 生成 144。任何基于当前 main 的
PR 触发 governance-check 都会撞上。与本次文档治理无关。
**处理**: 生成文件恢复 origin/main 版 (不引入内容漂移); 共享主仓较新 agora
生成的 595 版偏离基线, 未采用。
**遗留**: capability-registry.yaml 需一次独立的完整 sync-all-docs 提交 (归 CI/维护),
非本次范围。

## 8. 最终治理指标

| 指标 | 前 | 后 |
|------|-----|-----|
| doc-governance findings | 289 | **2** (CLI-REFERENCE.md 生成文件合理例外) |
| index drift | FAIL | **ALL PASS** |
| 修复文件数 | - | **169** (frontmatter) + index + ADR-0413/0414 |
| PR | - | #1691 |
