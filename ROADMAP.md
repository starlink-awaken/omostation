---
type: ephemeral
created: 2026-09-03
---

# ROADMAP — Python 质量扫描基础设施规模化

> ADR-0367 / `governance-evolution-roadmap.yaml::sweep-tooling-scaling`
> 最后更新: 2026-08-04

## 1. 主题总览

| 主题 | 范围 | SSOT | 入口 | 状态 |
|------|------|------|------|------|
| A. Sweep 工具硬化 | README / required gate / 抑制比 / scan / 历史 | `bin/sweep/`, `agent-workflows.yaml::diff_checks`, `.omo/_knowledge/sweeps/` | `make gac-local-gate` | A1-A5 计划 |
| B. Worktree 生命周期 | 集成测试 / trap 异常 / branch-release 兜底 | `bin/gac/`, `tests/` | `bash bin/gac/gac-worktree.sh` | B1-B4 计划 |
| C. ADR/索引一致性 | 0366 重复 / frontmatter id / 历史 ADR 补全 | `.omo/_knowledge/decisions/`, `bin/adr/adr-coverage.py` | `adr-coverage.py --json` | C1 完成，C2-C4 计划 |
| D. runtime registry 沉淀 | ADR-0368 沉淀 + 注释 | `projects/runtime/src/runtime/registry/` | `adr-coverage.py` | D1-D2 计划 |
| E. PR 拆分 | `git log` 可读性 | git history | history review | E1 可选 |

## 2. 依赖与执行顺序

```text
A1 README ─┐
A3 抑制比 ─┼─ A4 scan.py ─── A5 历史归档
          │
          └─ A2 required (依赖 A1)

C1 重复 ADR (独立) ── C2 校验 ── C3 补 frontmatter ── C4 gate 必跑

B1 集成测试 ─┐
B2 trap 异常 ─┼─ B4 文档化
B3 release 兜底 ─┘

D1 ADR-0368 (独立) ── D2 注释

Phase 1 收口后 A2+C4+B1+D1 触发 E1 (可选)
```

## 3. 验证

```bash
make gac-local-gate          # ≥38 checks 必含 pyright-sweep-check
python3 bin/adr/adr-coverage.py --json
uv run --with pyyaml python bin/gac/governance-evolution.py validate
```

## 4. 决策记录

- `agent-workflows.yaml` 的 `pyright-sweep-check` 当前 `required: false`，A2 完成前不能调高。
- C1 通过文件名重命名 `0366-agt-ecos-integration.md` → `0370-agt-ecos-integration.md` 解决编号冲突。
- `bin/adr/adr-coverage.py` 在 `governance-evolution-roadmap.yaml` 的 `path_exists_if_local` 校验里只接受文件路径，因此 deliverable 不写 `::` 段。

## 5. 后续工作

详见 ADR-0367 中的 Phase 1 / 2 / 3 路线图。
