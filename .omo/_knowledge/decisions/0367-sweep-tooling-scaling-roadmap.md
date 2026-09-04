---
id: ADR-0367
title: Python 质量扫描基础设施规模化路线图
status: PROPOSED
date: 2026-08-04
owner: governance-team
lifecycle: spec
last_updated: 2026-08-04
related:
  - 0366-pyright-sweep-algorithm.md
  - 0130-p74-workflow-solidification.md
  - 0220-gconv7-concurrency-discipline.md
  - ../decisions/0371-pasw-submodule-isolation.md
  - ../../standards/agent-workflow-contract.md
---

> 📋 **处置 (2026-08-17 分类, 推演文档 §4 分支B)**: 保持 PROPOSED — 仍相关 (质量扫描规模化持续议题, 留待 Y1Q4/Q2 排期)

# ADR-0367: Python 质量扫描基础设施规模化路线图

## 背景

`bin/sweep/` 工具（pyright / ruff / nested-with）和 `pyright-sweep` workflow 已合并（PR #940，commit `611d94fe3`）。
当前治理仍存在 9 个未完成的工程债务，分散在 5 个架构主题下。本 ADR 把它们纳入 `governance-evolution-roadmap.yaml` 的
新 initiative `sweep-tooling-scaling`，并定义 SSOT、入口、可验证证据和依赖顺序。

### 现状盘点（post-merge）

| 主题 | 当前状态 | 痛点 |
|------|----------|------|
| **Sweep 工具** | 工具 + 测试在 main；`pyright-sweep-check` `required: false` | 默认门禁不强制，新 PR 仍可能回潮 |
| **Sweep 治理** | 无历史、无抑制比守门 | 难分辨“真实修复” vs “抑制补丁” |
| **Worktree 生命周期** | `claim` marker + cleanup 跳过已落地 | 集成测试缺；trap 行为未测；`branch-claims` 容错未补 |
| **ADR/索引一致性** | `adr-coverage.py` 检测 frontmatter + INDEX | 305 个历史 ADR 无 frontmatter `id`；ADR-0366 重复编号 |
| **PR 合并后续** | runtime registry 修复随 PR #940 合并 | 缺 ADR 沉淀契约变化 |

## 决策

### 主题 A：Sweep 工具硬化

| 任务 | SSOT | 入口 | 证据 |
|------|------|------|------|
| A1 `bin/sweep/README.md` 描述工具 | `bin/sweep/README.md` | `make gac-local-gate` 含 `pyright-sweep-check` | 文档可读、参数覆盖、退出码示例 |
| A2 `pyright-sweep-check` 升 `required: true` | `agent-workflows.yaml::diff_checks` | `make gac-local-gate` | gate 不再 38/38 而是 ≥1 sweep-check 必跑 |
| A3 抑制比守门（`file_suppressions ≥ 3` 或 `suppression_ratio > 0.6` 阻断 PR） | `bin/sweep/pyright.py` | `bin/sweep/pyright.py` 退出码 | 干跑样例通过/失败各 1 |
| A4 `bin/sweep/scan.py` 调用 `uv run pyright --outputjson` 收集产物 + 写报告 | `bin/sweep/scan.py` + `.omo/_knowledge/sweeps/<date>.json` | `bin/sweep/scan.py` | 输出 JSON 包含 `errors / line_suppressions / file_suppressions / suppression_ratio` |
| A5 历史归档（`A4` 落盘） | `.omo/_knowledge/sweeps/INDEX.md` | `rg ".omo/_knowledge/sweeps"` | 索引指针；不复制数据 |

### 主题 B：Worktree 生命周期守护

| 任务 | SSOT | 入口 | 证据 |
|------|------|------|------|
| B1 集成测试：真子进程跑 `gac-worktree.sh claim` + 并发 `gac-worktree-cleanup.sh --dry-run` | `tests/test_gac_worktree_lifecycle_integration.py` | `uv run pytest tests/test_gac_worktree_lifecycle_integration.py -q` | 集成测试 ≥ 2 通过 |
| B2 补充 trap 在子进程异常时清理验证 | `bin/gac/gac-worktree.sh` | `tests/test_gac_worktree_trap.sh` | trap 在异常路径下清理 |
| B3 `branch-release` 兜底删除孤儿 claim | `bin/gac/swarm_discipline.py::branch_release` | `bin/gac/swarm-discipline-cli.py branch-release` | 单元测试 + 集成测试 |
| B4 在清理脚本新增 README 解释 marker / claim GC 协议 | `bin/gac/gac-worktree-cleanup.sh::header` | `bin/gac/gac-worktree.sh help` | 注释 + 集成测试 |

### 主题 C：ADR/索引一致性

| 任务 | SSOT | 入口 | 证据 |
|------|------|------|------|
| C1 修复 ADR-0366 重复编号：将 AGT 集成那条改为 ADR-0370 | `bin/adr/next-adr-id.py` | `adr-coverage.py --json` | duplicate_numbers=[] |
| C2 `adr-coverage.py` 增强：检测 frontmatter `id` 与 header `# ADR-NNNN:` 一致性 | `bin/adr/adr-coverage.py` | `bin/adr/adr-coverage.py --json` | `files_not_in_index / mismatch` 字段 |
| C3 305 个历史 ADR 补 `id: ADR-NNNN` frontmatter | `.omo/_knowledge/decisions/` 全部 | `adr-coverage.py --json` | `frontmatter_issues` 降到 ≤ 5 |
| C4 `bin/adr/adr-coverage.py` 加入 CI 必跑 | `gac-local-gate.py::CHECKS` | `make gac-local-gate` | gate 含 `adr-coverage` |

### 主题 D：runtime registry 修复 ADR 沉淀

| 任务 | SSOT | 入口 | 证据 |
|------|------|------|------|
| D1 ADR-0368：runtime registry `test_submit_no_agent` / `test_failover_redispatches_inflight_task` 与 TaskFallback 协议变化 | `.omo/_knowledge/decisions/0368-runtime-taskfallback-test-contract.md` | `agent-workflow verify` | `adr-coverage.py` 收录 |
| D2 在 `projects/runtime/src/runtime/registry/__init__.py` 头注释里引用 ADR-0368 | `runtime/registry/__init__.py` | `rg ADR-0368 projects/runtime` | 注释落地 |

### 主题 E：PR #940 提交历史拆分（可选项）

| 任务 | SSOT | 入口 | 证据 |
|------|------|------|------|
| E1 在 main 已合并 commit `611d94fe3` 之上，将 commit 拆分为 `feat(sweep): tools` + `test(sweep): coverage` + `chore(worktree): claim marker` 三条 | `git log omostation-root/main` | 历史浏览 | 拆分 commit 在主分支历史可读；不需重开 PR |

## 依赖与执行顺序

```text
A1 README ─┐
          ├─ A2 required (依赖 A1 文档)
A3 抑制比 ─┘
       │
       └─ A4 scan.py (依赖 A3 的报告字段)
                  │
                  └─ A5 历史归档 (依赖 A4)

C1 重复 ADR (独立) ─┐
C2 frontmatter 校验 (依赖 C1)  ── C3 批量补 frontmatter (依赖 C2) ── C4 gate 必跑
                                                                   
B1 集成测试 ─┐
B2 trap 异常 ─┤─ B4 文档化
B3 release 兜底 ─┘

D1 ADR-0368 (独立) ── D2 注释 (依赖 D1)

A2 + C4 + B1 + D1 完成后，E1 commit 拆分（一次性）才有价值
```

## 影响

- 9 个待办合并为 5 个可验证主题。
- A 主题让 `pyright-sweep-check` 从 advisory 升级到 required 守门。
- C 主题修复 ADR-0366 编号冲突与 305 个无 frontmatter ADR 的历史债务。
- B 主题闭合 worktree 生命周期的竞争/异常路径。
- D 主题把 runtime test 修复沉淀为 ADR，避免后人重复劳动。

## 验证

```bash
# 主题 A
make gac-local-gate   # 含 pyright-sweep-check (required)
python3 bin/sweep/scan.py projects/cockpit --dry-run | jq '.suppression_ratio'
test -f .omo/_knowledge/sweeps/INDEX.md

# 主题 B
uv run pytest tests/test_gac_worktree_lifecycle_integration.py -q
bash tests/test_gac_worktree_trap.sh

# 主题 C
python3 bin/adr/adr-coverage.py --json | jq '.duplicate_numbers, .frontmatter_issues | length'
# 期望: duplicate_numbers=[]; frontmatter_issues 长度 ≤ 5

# 主题 D
python3 bin/adr/adr-coverage.py | rg '0368'
```

## 落地计划

1. **本 ADR 合入**（`project-doc-change` 流程）→ roadmap initiative 入 `governance-evolution-roadmap.yaml`。
2. **Phase 1（短期 1-2 天）**：A1 + C1 + D1 + B1 集中做，先关阻断类问题。
3. **Phase 2（中期 1 周）**：A2 / A3 / A4 / C2-C4 / D2 / B2-B3 推进，让 `pyright-sweep-check` 真正 required。
4. **Phase 3（长期观察）**：A5 sweep 历史归档、GitHub Actions 端到端自举、E1 commit 拆分。
5. **每个 Phase 走 `pyright-sweep` workflow**，避免 `project-code-change` 反复错位。
