---
title: T6-01 去重清单终版 — gbrain + kairon → knowledge
type: evidence
status: draft
owner: engineering-agent
created: 2026-08-16
bet: BET-Y1Q3-T6-01
related:
  - docs/plans/2026-08-16-t6-01-knowledge-merge-spec.md
---

# T6-01 去重清单终版（逐项可复核）

## 口径声明

- 表面计量以 **merge 后主仓 `bet-ledger.py surface`** 为准（worktree 内子模块 checkout 不全，
  数字失真，不可作为证据 — 本文档写作时 worktree 实测 863K/435K 即失真值）。
- test_loc 基线 **350,854** 为保护量；归并前主仓实测 799,371。
- 归并形态为「治理层归一 + 异构栈目录内包」，src 下降量只能来自治理面去重，
  代码文件原样搬运（git archive tree-vs-disk 零差异：gbrain 1770/1770，kairon 1454/1454）。

## 清单（合并后删除项 → 行数）

| # | 去重项 | 实证 | 删除量 (行) |
|---|--------|------|------------|
| 1 | kairon 独立仓 .omo/ 治理残留 | `git rm -r projects/knowledge/kairon/.omo`：39 files, **-9,410** (commit a29c7c898 stat) | 9,410 |
| 2 | .gitmodules 双条目 | projects/gbrain + projects/kairon 两条 submodule 声明删除 | 8 |
| 3 | registry 双头条目 | gbrain: 6 行改写并入 + kairon: ~40 行结构迁移（元数据零丢失，kos_details 25 mcp_tools 保留） | ~10 净减 |
| 4 | layer-contract 双头 | L2 projects 列表 kairon+gbrain → knowledge；2 依赖条目改名 | ~4 净减 |
| 5 | submodule_policy dormant/stable 条目 | gbrain 从 dormant 移除 | 1 |

**治理面去重合计：~9,433 行**（其中 kairon .omo/ 占 9,410）。

## 非去重项（明确不列）

- gbrain/kairon 各自 CLAUDE.md/AGENTS.md/README：栈特定文档，随代码内包保留（KISS：
  删了反而让 knowledge/ 目录失去自解释性）。
- chunkers(ts) vs codeanalyze(py)：语言隔离，删任一侧 = 砍能力 ≠ 去重（spec §4 已声明）。
- 子仓 CI（kairon-ci.yml 等）：路径已重写到 knowledge/，工作流本身保留。

## 附带修复（不属去重，零代码功能变更）

| 修复 | 类型 | 证据 |
|------|------|------|
| conflict-marker hook Setext 误报 | 治理工具 | commit aaf69f595 |
| agora a2a smoke metaos importorskip | 上游断测 | agora e1b24d0 |
| kos llm_extractor import os | 上游手误（10 failed→16 passed） | commit a29c7c898 |
| mos rbac RbacDenied alias | 上游断测（1 error→56 passed） | commit 5da4952f4 |
| iris entry-points 期望集过期 | T2-01 残留（183 passed） | commit a29c7c898 |
| minerva LLM 降级断言 + 路径语义化 | 基线断测（588 passed） | commit a29c7c898 |
| c2g BOS 死路径改道 omo._vendored | T1-01 残留 | agora c6f519b |
| agora services.py 45 处路径 | evidence 鸿沟 48→0 | agora 0986057 |

## 验证状态（2026-08-16 worktree 内实测）

| 验证 | 结果 |
|------|------|
| gbrain bun test | 7377 pass / 388 fail / 563 skip（基线对照跑中，见 §基线） |
| kairon 16 包 pytest | **全绿 FAIL=0**（含修复后 kos/minerva/iris/mos） |
| evidence-smoke | **100/100, 鸿沟 0, resolve 1.0** |
| gac-local-gate | 44 checks PASS |
| tree-vs-disk 搬运完整性 | gbrain 1770/1770 · kairon 1454/1454 零差异 |
| CI (#1600) | Actions 平台停摆中（全库 14:07Z 后零 run），本地链完备，待恢复 merge |

## 待办（merge 后收口）

1. 主仓 `bet-ledger.py surface` 真实前后对比 + test_loc ≥ 350,854 核验
2. `bash tests/integration/run-all.sh` 全量
3. 回滚 tag 推远端（lane 白名单当前不含 tag push，需 registry 逃生口或人工）
4. retro 五问 + 台账 T6-01 → in_progress (awaiting human_gate)
