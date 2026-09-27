---
schema: md/v1
status: active
lifecycle: plan
owner: governance-agent
last-reviewed: 2026-09-27
type: ephemeral
title: "规则接线批次一判定表 — 36 条候选四态归因（BET-Y2Q4-T10-01）"
---

# 规则接线批次一判定表（2026-09-27）

> 基线：BET 铸造时 42 条未引用；**SH-4（#4337，09-25）已建 35 组别名**使候选降至 36。
> 本批次追加 7 组**语料可证**别名（36→**29**），全量 36 条四态归因如下。
> 证据标准：每条至少 1 个 文件:行 锚；入别名映射的须 2 处（声明 + 执行体语料）。

## 状态 a) 已实现换名 → 已入别名映射（7 条，36→29 的来源）

| 规则 | 别名（语料可证） | 锚 |
|---|---|---|
| CR-M0-STAGE-GATE | `mof-bootstrap` | ecos-ci.yml:81 tool-loop 调用 + source_ref bin/mof/mof-bootstrap.py |
| CR-M4-BOOTSTRAP-REFLEX | `mof-bootstrap` | 同上（M4 5-check 在 mof-bootstrap 内） |
| CR-HARNESS-STRUCTURE | `CR-HARNESS-SECTION` | gac-gate.yml:154（required step）+ 声明自述"合并自 SECTION-COMPLETENESS 等" |
| CR-HARNESS-MOF-INTEGRATION | `CR-HARNESS-MOF` | gac-gate.yml step + 合并自述 |
| CR-HARNESS-OPERATIONS | `CR-HARNESS-ENFORCE` | gac-gate.yml step（**中置信**：排除法对应，owner 可复核） |
| CR-HARNESS-GOVERNANCE | `CR-HARNESS-OMO` | gac-gate.yml step + 合并自述（known_debt + OMO 同步） |
| CR-GITLINK-BUMP-SQUASH-MAIN | `gitlink-ancestry` | hook-manifest.yaml:107 + 契约 submodule-pointer-bump-contract.md |

## 状态 b-1) 执行器存在但孤儿（脚本在、调用面缺）（3 条）

| 规则 | 执行器 | 缺口 |
|---|---|---|
| CR-M4-MCPTOOL-INTEGRITY | bin/gac/mcp-tool-data-complete.py 存在 | 不在 workflows/.githooks/hook-manifest 任何调用面 |
| CR-CROSS-REPO-CONSISTENT | bin/ssot/check-cross-repo-consistency.py 存在 | 同上（描述自称 Phase 3 治本+har…，未见接线） |
| CR-GAC-TIMEOUT-AUDIT | bin/gac/timeout-audit.py 存在 | 同上 |

→ 建议：登记 ci-surfaces.yaml 或 pre-push 批量跑（owner 拍板接入面）。

## 状态 b-2) 真未实现（幽灵声明：source_ref 脚本从未建）（10 条）

| 规则 | 实证 |
|---|---|
| CR-SEC-YAML-BYPASS | source_ref bin/ssot/check-yaml-bypass.py 不存在；ruff/CI 无等价禁令 |
| CR-SEC-SENSITIVE-WRITE | source_ref 不存在；**部分等价**：omo_lint.py:176-182 仅覆盖 governed 路径写入助手，非全仓 secret 扫描 |
| CR-SEC-EVAL-EXEC | source_ref 不存在；无等价机制 |
| CR-PY-MUTABLE-DEFAULT | source_ref 不存在；pyproject 无 B006 |
| CR-AGE-BOS-01 / -POLICY-01 / -MEMORY-01 / -REPLAY-01 / -EVENT-01 | 5 个 check-age-*.py 全部不存在；现存 agent-cell-* 仅为 smoke/canary，非规则检查器 |
| ~~CR-COMMIT-LLM-ASSIST~~ → **改判 a) 换名**（2026-09-27 复核）| source_ref 路径笔误（bin/gac/ → bin/commit-assist.py 真实存在、274 行、#4422 活跃维护）；已修 source_ref + 接线别名 |

→ 建议：SEC 四条接 ruff（S-band/B006）一次收口；AGE 五条 owner 确认 AGE-v2 是否仍活跃（否→转退役）；COMMIT-LLM-ASSIST 连同僵尸测试转 c)。

## 状态 c) 过时/僵尸（1 条，另 1 条挂 owner）

- **CR-COMMIT-ASSIST-E2E**：tests/test_commit_assist_e2e.py 测试一个从未存在的 bin/commit-assist.py（僵尸测试；当前 CI 未收集故未红）。→ owner 确认后删测试 + 规则标 deprecated。

## 状态 d) 存疑 → owner 决策卡（15 条）

x2-staleness（radar staleness_score 部分对应，中置信）、CR-L2-TASK-DELIVERABLE、CR-X3-DEBT-TIER（delivery-value-gate 是交付文件口径，债务口径未接线）、CR-L0-PROTOCOLS-SSOT（描述引用的 check-vault-paths.py 未能定位）、CR-L0-SSOT-PATH-NORM（契约文档自身已缺失）、CR-L4-DOMAIN-REGISTRY-FRESHNESS（6h cron 巡检不在可执行语料）、CR-EVIDENCE-DECLARED、CR-P76-6-5-LLM-DEFERRAL、CR-P77-2-1、CR-P77-2-2（P76/P77 原则族，无机器执行器）、CR-X1-POLICIES-SSOT、CR-X2-FRESHNESS-SSOT（x1/x2 家族词汇映射 SH-4 未覆盖）、CR-EVIDENCE-SHA-FRESHNESS（complete 有 spec digest 校验但非全锚重算）、CR-BIN-RETIREMENT-CHECKLIST（六层登记人工流程）、CR-GIT-STAGE-SUBMODULE-PIN（无 hook 实现禁 add -A）。

## 复算

- `python3 bin/gac/check-rule-wiring-coverage.py` → 未引用 36 → **29**（alias_map_size 35→40）
- 判定覆盖：36/36 有状态归因；锚定判定 21 条（a 7 + b-1 3 + b-2 10 + c 1）≥ 20（批次一门槛）
