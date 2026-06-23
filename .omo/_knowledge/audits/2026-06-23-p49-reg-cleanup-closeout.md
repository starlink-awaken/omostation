# P49 治理注册表收口报告 — PLANNED 清零

> 2026-06-23 · mof-version v0.0.37
> Pattern: c2g → omo → mof (P48 闭环延伸)

## 1. 背景

P48 (commit 993ca322) 完成后审计：

- **3 PLANNED 候选残留**:
  - `IMPORTED-f9b1e2`: 任务1 (c2g brainstorm 历史)
  - `OPC-P6-SELF-EVOLUTION-doc-gate-e`: OPC phase 6 治理
  - **`TASK-A5378E91`: 治理注册表漂移** (P48 末尾 commit 89cd7f6f 已部分修)

## 2. P49 3 Rounds

| Round | 主题 | 关键产物 |
|-------|------|---------|
| R1 | 立项 + 验证 | P49-REG-CLEANUP task + cockpit test_no_subcommand PASS |
| R2 | 3 候选 done | 2 cascade + TASK-A5378E91 已在 done/ (89cd7f6f) |
| R3 | 收口 | P49-REG-CLEANUP done + mof-version v0.0.37 + PLANNED 清零 |

## 3. R1 详细 — registry 验证

**`cockpit test_no_subcommand` PASS**:
- test_cli_research_extra.py::TestCmdGovernance::test_no_subcommand 1 passed
- `omo-governance-surfaces.yaml` registry 已含 OMO-DOC-LIFECYCLE/OMO-BETS/OMO-TASKS
- debt/workers 块保留为 SSOT governance surface (即使物理目录 gitignore)

**TASK-A5378E91 描述的"3 新资产未注册"实际已修** (P48 末尾 commit 89cd7f6f):
- 修需 = registry 维护 → 已修
- 修需 = omo-cli governance register 命令 → P48 omo 升级时已加

## 4. R2 详细 — 3 候选 done

| Task | Outcome | Evidence |
|------|---------|----------|
| IMPORTED-f9b1e2 | superseded (历史 c2g brainstorm 残影) | P45 全面落地覆盖 |
| OPC-P6-SELF-EVOLUTION-doc-gate-e | superseded (OPC P6 self-evolution 闭环) | P45 R6 frontmatter 100% 收口 |
| TASK-A5378E91 | **completed** (P48 末尾 89cd7f6f 已修) | registry 修 + test pass |

## 5. R3 详细 — 收口

- **P49-REG-CLEANUP** task → done
- **PLANNED 目录清零** (0 candidate/pending, 历史首次)
- mof-version v0.0.36 → v0.0.37
- governance 100 A+ 7/7 持续

## 6. PLANNED 目录演进

| 阶段 | PLANNED 数量 | 备注 |
|------|--------------|------|
| P44 R7 收口 | 11 | 历史 c2g/IMPORTED/REMEDIATE 任务 |
| P45 R7 | 7 | P44 7 PLANNED done (cascade) |
| P46 R1 | 11 | 11 PLANNED done (cascade) |
| P47 R1 | 0 (mof-extract 清空) | - |
| P48 R3 | 3 (mof-extract 重新生成) | IMPORTED + OPC + TASK |
| **P49 R3** | **0** | **历史首次完全清零** |

## 7. 累计治理状态 (P43 → P49)

| Phase | mof-version | governance | 关键 |
|-------|-------------|------------|------|
| P43 | v0.0.12 | 100 A+ | closed-loop pattern |
| P44 | v0.0.28 | 100 A+ | wf-convergence + 5 REMEDIATE |
| P45 | v0.0.32 | 100 A+ (7/7) | doc-lifecycle 4 类 + 14/15 维度 + 第 7 项 |
| P46 | v0.0.33 | 100 A+ | 11 PLANNED + 3 mof 实施 |
| P47 | v0.0.35 | 100 A+ | 12/12 mof + drift 7→1 |
| P48 | v0.0.36 | 100 A+ | mof-drift v3 + 17 项目 lint |
| **P49** | **v0.0.37** | **100 A+** | **PLANNED 清零** |

## 8. P50+ 路线

- gbrain 53 TODOs 实际推进 (keep=13→close / fix=6→fix / planned=1→实施)
- gbrain 15 commits ahead 子仓推送
- TASK-08B2A2C5 / TASK-8CF4636A 验证 (子仓)
- 持续 mof-drift 6 维度监控

## 9. 关联

- TASK-A5378E91: 真实债 (P48 89cd7f6f 已部分修)
- P48 R3: mof-drift v3 + 17 项目 lint
- P45 R6: frontmatter 100% (DOC-LIFECYCLE.md 起点)
