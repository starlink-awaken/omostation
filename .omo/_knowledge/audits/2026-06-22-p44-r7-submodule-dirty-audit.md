---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# P44 R7 子模块脏目录盘点报告

> 2026-06-22 盘点
> 范围: 13 个 gitlink 子模块 + 1 个新 gitlink (omo-debt)
> 数据源: `git status` 根仓 `m` 标记 + `git submodule status`

## 1. 现状

根仓 gitlink 全部 MATCH (12 子模块)。子模块内 dirty 文件累计 229 个。
这些 dirty = 各子仓本地未提交变更（不是根仓的事）。

| 子模块 | 根 gitlink 状态 | 子仓 dirty 文件 | 主要类型 |
|--------|--------------|---------------|---------|
| aetherforge | MATCH | 93 | gateway 内部文件 (待子仓 commit) |
| agora | MATCH | 1 | mcp_gateway.py 修改 |
| bus-foundation | (无根脏) | (未测) | — |
| c2g | MATCH | 6 | adapter + tests + bets.json 新增 |
| cockpit | MATCH | 1 | api_ecos.py |
| ecos | MATCH | 1 | pyproject.toml |
| family-hub | MATCH | 2 | .env + test 删除 |
| gbrain | MATCH | 3 | operations.ts 拆分尝试 |
| kairon | MATCH | 41 | omc 状态 + derivation logs |
| metaos | MATCH | 3 | pyproject + uv.lock + .bak |
| model-driven | (无脏) | (未测) | — |
| observability | MATCH | 1 | docker-compose.yml |
| omo | MATCH | 71 | mof-extract 同步文件 + registry |
| runtime | MATCH | 6 | .env + CLAUDE.md + others |
| scripts | MATCH | (未测) | — |
| omo-debt (新) | MATCH | 0 | 新增子模块已注册 |
| hermes-console | MATCH | (未测) | — |
| l4-kernel | MATCH | (未测) | — |

## 2. 处理策略 (P43 submodule_state_decoupling 教训)

**根仓不动**。各子模块 dirty 必须在子仓自己内:
1. **评估** — 真 PR 候选 vs 临时 hack vs mof-extract 钩子产物
2. **子仓 commit** — 每个子仓按自己流程 commit + push
3. **根仓 bump** — 子仓推完后根仓 `git add projects/<name>` + commit gitlink

## 3. 根仓责任

- ✅ 已建 P44-SUBMODULE-PIN (治理规则)
- ✅ 已建 P44-DEFER-SUBMODULE-PUSH (ecos 4 + gbrain 15 待推)
- ✅ 已建 P44-DEFER-GBRAIN-OPS-SPLIT (75 operations 拆分)
- ✅ 已建 P44-DEFER-GBRAIN-TODOS (53 TODOs)
- ✅ 已建 P44-DEFER-EXECUTOR-SPLIT (80 files 拆分)
- ✅ 已建 P44-DEFER-OMO-SUBPKG (124 files 物理重组)
- ✅ 已建 P44-DEFER-SYS-PATH-INSERT (drift 校正后无新发现)

## 4. 未推进任务

| 任务 | appetite | 阻塞 |
|------|---------|------|
| P44-SUBMODULE-PIN | P1 | 已 done (锁仓) |
| P44-DEFER-SUBMODULE-PUSH | P1 | 子仓先行 push |
| P44-BET-3b90-FOLLOWUP | P2 | human product team |
| P44-DEFER-EXECUTOR-SPLIT | medium | dedicated session |
| P44-DEFER-OMO-SUBPKG | medium | dedicated session |
| P44-DEFER-GBRAIN-OPS-SPLIT | low | dedicated session |
| P44-DEFER-GBRAIN-TODOS | P3 | 拆分后批量清 |
| P44-DEFER-SYS-PATH-INSERT | medium | drift 已 7→1 |

## 5. 治理验证

- omo governance: 100 A+ (稳定)
- mof-drift: 7→1 (校正后仅 1 LOW: gbrain TODOs)
- mof-version: v0.0.26
- 5 P44 done + 7 P44 PLANNED (deferred-tracking)

## 6. 结论

P44 治理面 ✅ 收口 + 干净收敛. **剩余 229 个子仓内部 dirty 是子仓自己的工作**,
根仓按 P43 教训不批量 bump. 8 个 P44 PLANNED 任务已建立治理可见性,
等子仓自行推进 + human product team 处理用户面向 followup.
