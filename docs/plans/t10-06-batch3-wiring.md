---
schema: md/v1
status: active
lifecycle: plan
owner: governance-agent
last-reviewed: 2026-09-27
type: ephemeral
title: "规则接线批次三 — 真接线 + 值域迁移 + 幻影显式化（BET-Y2Q4-T10-06）"
---

# 规则接线批次三（2026-09-27）

> 轨迹：42 → 36 → 29 → 27 → 25 → **20**（全部有标注/处置，零无主）。

## 一、真接线（6 组，coverage -6）

| 规则 | 接线方式 | 锚 |
|---|---|---|
| CR-M4-MCPTOOL-INTEGRITY | **孤儿入 CI**（本批新步骤） | governance-check.yml `python3 bin/gac/mcp-tool-data-complete.py` |
| CR-CROSS-REPO-CONSISTENT | 孤儿入 CI | 同上 `check-cross-repo-consistency.py` |
| CR-GAC-TIMEOUT-AUDIT | 孤儿入 CI | 同上 `timeout-audit.py` |
| CR-DEBT-GATE-ENUM-01 | **实现**（check-debt-closure-discipline.py scan_gate_level_enum）+ 20 条值域迁移 | 脚本 docstring 锚规则 id |
| CR-SEC-YAML-BYPASS | 换名发现：omo.cli lint yaml-bypass 一直在 CI 跑 | governance-check.yml |
| CR-SEC-SENSITIVE-WRITE | 换名发现：omo.cli lint sensitive-governed-writes | 同上（governed 路径口径） |

## 二、CR-DEBT-GATE-ENUM-01 实现细节

- 校验：`scan_gate_level_enum` 值域 {gate, watchlist, none}，接入 check-debt-closure-discipline（检查 D，--json 含 gate_level_enum）。
- **迁移 20 条**（P0→gate ×2 / P1→watchlist ×7 / P2→none ×11）：修复"高严重度债务 rank=99 在 review 队列最后被看"的原始缺陷。迁移后分布 {gate:2, watchlist:7, none:15}，校验 rc=0。
- 迁移映射为自然语义对齐（P0 最紧急→gate 阻断；P2→none），owner 如需个别改判直接改对应 yaml（每条 diff 可见）。

## 三、显式化待决（20 条全部有标注，零无主）

| 类别 | 规则 | 需要的 owner 表态 |
|---|---|---|
| 幻影·安全 | CR-SEC-EVAL-EXEC | 补 omo lint（eval/exec）或 ruff S 规则 → 接线 |
| 幻影·安全 | CR-PY-MUTABLE-DEFAULT | ruff B006 → 接线 |
| 幻影·AGE | CR-AGE-BOS/POLICY/MEMORY/REPLAY/EVENT-01 ×5 | AGE-v2 活跃→立项实现；否则退役声明 |
| 待决 | CR-L4-DOMAIN-REGISTRY-FRESHNESS | 需 macOS CI lane（launchd 依赖，ubuntu 不可跑） |
| 待决 | CR-EVIDENCE-DECLARED / CR-L2-TASK-DELIVERABLE | 复核后收窄或接线 |
| 弃用候选 | CR-L0-SSOT-PATH-NORM | 契约文档已消失 |
| 并入决策 | CR-X1/X2-POLICIES-SSOT | SH-4 DEC-SH-4-AUTHORITATIVE-REGISTRY |
| 收窄已标注 | CR-EVIDENCE-SHA-FRESHNESS / CR-BIN-RETIREMENT-CHECKLIST / CR-GIT-STAGE-SUBMODULE-PIN | 声明口径已对齐实现（仍计未引用，因收窄后仍无全量执行器） |
| 弃用已标注 | CR-P76-6-5 / CR-P77-2-1 / CR-P77-2-2 | 原则族 |

## 四、--strict 门槛（不变）

剩余 20 条中 9 条幻影需 owner 二选一（接线 vs 退役），收窄/弃用类建议批次四将"弃用"
条目从统计口径分离（deprecated 不计未引用）——两条路都通向归零，等 owner 表态后一个
批次收口。
