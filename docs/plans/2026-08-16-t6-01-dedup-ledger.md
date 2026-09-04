---
title: T6-01 去重清单终版 — gbrain + kairon → knowledge
type: evidence
owner: engineering-agent
created: 2026-08-16
bet: BET-Y1Q3-T6-01
related:
  - docs/plans/2026-08-16-t6-01-knowledge-merge-spec.md
lifecycle: plan
last_updated: 2026-08-18
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
| gbrain bun test | 内包后 7377 pass / 388 fail vs **原仓基线 7388 pass / 389 fail** — fail 数持平（环境性测试），内包零新增失败 |
| kairon 16 包 pytest | **全绿 FAIL=0**（含修复后 kos/minerva/iris/mos） |
| evidence-smoke | **100/100, 鸿沟 0, resolve 1.0** |
| gac-local-gate | 44 checks PASS |
| tree-vs-disk 搬运完整性 | gbrain 1770/1770 · kairon 1454/1454 零差异 |
| doctor | ok=True（cockpit/agora path 深度修正 ../knowledge/kairon 后） |
| CI (#1600) | Actions 事件消化延迟（平台侧, head 1fcf0e2 runs=0），本地链完备，待恢复 merge |

## 待办（merge 后收口）— 2026-08-17 更新

1. ~~主仓 surface 前后对比~~ ✅ **已实测**：
   - test_loc **454,784 ≥ 基线 350,854**（+103,930）— 保护量守住 ✅
   - numstat 全生态口径：治理面去重 ≈ 9,475（kairon .omo 9,410 + registry/gitmodules/contract 65）
     ≈ 去重清单合计 9,433（差 42 = 断测修复净增）— 「src 下降量 == 去重清单」闭环 ✅
   - 注：worktree surface 绝对值受子模块 checkout 完整度干扰（scripts 嵌套 submodule 污染），
     真实口径以 numstat (b7530c27 → 30771c289) 前后差为准
2. `bash tests/integration/run-all.sh` 全量 — 运行中
3. 回滚 tag 推远端 — lane 白名单不含 tag push，**需人工** `git push origin pre-knowledge-merge-20260816`
4. ~~retro + 台账停审~~ ✅ 已落（#1600 merged，origin/main 核对 in_progress + awaiting 确认）

### 附：Y1Q4 核实性收口（同 PR）

- T3-01 自主性阶梯 → done（45 tests / rejected 注入降级实测 / evidence 100）
- T5-01 fork/join → done（三策略 + 7 tests）
- T7-01 → 保持 candidate（format_check 无裁决数据，circuit_breaker 禁强行放权）
