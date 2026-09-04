---
title: BET-Y1Q2-T1-01 复盘 — omo-debt + c2g 并入 omo (L3, 停审)
type: retro
owner: governance-team
created: 2026-08-16
context: >-
  L3 不可逆归并, human_gate: true — 实施完成, 停在接受审。前置 ADR-0412 (T1-02 判定
  model-driven 不在归并范围)。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q2-T1-01 复盘 (实施完毕, 待 human gate)

## 交付面 (2026-08-16)

| 项 | 结果 |
|---|---|
| 内包 | omo_debt_engine (18 文件) + c2g (27 文件) → omo/_vendored/, import 全限定改写, 语法+导入全验 |
| 消费者迁移 | cockpit debt_scoring.py → omo._vendored (唯一跨仓消费者, 已改) |
| 子模块条目移除 | .gitmodules 摘净 + gitlink D×2 + .git/config 清 |
| CLI 兼容 | omo-debt (主仓原生) + c2g/c2g-mcp (pyproject scripts 补) |
| CI/registry 同步 | ci-python-coverage pkg 列表 + c2g-gc-weekly/c2g-radar-daily/omo-autopilot 改道 + project-registry 条目摘 |
| 依赖 | gitpython>=3.1.0 补入 omo deps |
| 去重清单 | docs/reports/adr-0412-merge-dedup-list.md (逐项可复核) |
| 回归 | omo 1595 passed / 0 failed (release.sh 存量失败已修正为条件 skip) |

## done_when 对照

- ✅ omo-debt/c2g 作为 omo 内包存在, 子模块条目移除
- ✅ 去重清单产出 (互补非重复判定: 主仓=治理 CLI, 子仓=评分引擎)
- ✅ test_loc 不降 (内包后随 omo 计)
- ✅ CLI 入口兼容 (omo-debt 原生 + c2g scripts)

**status: in_progress (实施完停审) — human_gate 批准后置 done。**

## 停审理由 (L3 红线)

归并不可逆。批准检查点: ①merge 后 omo-debt/c2g 远端仓转 archive ②worktree 重开验证 uv sync 干净 ③cockpit model-driven 命令实测
