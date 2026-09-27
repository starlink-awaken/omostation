---
schema: md/v1
status: active
lifecycle: plan
owner: governance-agent
last-reviewed: 2026-09-27
type: ephemeral
title: "规则接线批次二处置表 — 15 条全落定（BET-Y2Q4-T10-05）"
---

# 规则接线批次二处置表（2026-09-27）

> 授权链：判定工作簿（15 条 + 建议）→ principal「继续吧」全按建议。
> 复跑：`check-rule-wiring-coverage.py` 未引用 **27 → 25**。

## 已接线（2 条）

| 规则 | 别名 | 证据 |
|---|---|---|
| CR-L0-PROTOCOLS-SSOT | `check-hardcoded-ports` | .github/workflows/port-registry-enforce.yml（#4411 dev 端口段门禁） |
| x2-staleness | `staleness` | bin/compass_radar.py staleness 子分（540 文件扫描 → health.yaml staleness_detail） |

## 已收窄声明（2 条，governance-checks 注释标注）

- CR-EVIDENCE-SHA-FRESHNESS：口径收窄至 spec binding digest（complete 校验范围）
- CR-BIN-RETIREMENT-CHECKLIST：机器执行面仅 quota-diff 层

## 已弃用标注（3 条，条目保留）

CR-P76-6-5-LLM-DEFERRAL、CR-P77-2-1-PRINCIPLE-FORMALIZATION、CR-P77-2-2-CATALOG-SSOT
—— 原则类不入 GaC 机器清单（principal 批准工作簿）；保留条目供历史追溯。

## 待决落档（8 条，证据 + 建议，batch-3 或 owner 专项）

| 规则 | 现状证据 | 建议 |
|---|---|---|
| CR-L4-DOMAIN-REGISTRY-FRESHNESS | `service-registry-reality` make 目标存在（T10-206）但不在可执行语料（Makefile 非语料） | 待其接入 CI workflow 后接线 |
| CR-EVIDENCE-DECLARED | 疑似被 complete D0 覆盖，未核锚 | 复核 complete() 覆盖面后接线或收窄 |
| CR-L2-TASK-DELIVERABLE | 执行器未定位 | owner 定任务卡机制去留后处置 |
| CR-L0-SSOT-PATH-NORM | 契约文档已消失 | 补契约或弃 |
| CR-X1-POLICIES-SSOT | x1 家族词汇映射未建 | 并入 SH-4 DEC-SH-4-AUTHORITATIVE-REGISTRY 决策 |
| CR-X2-FRESHNESS-SSOT | 同上 | 同上 |
| CR-GIT-STAGE-SUBMODULE-PIN | 无 hook 实现禁 add -A | 实现需 pre-commit 语义设计（add -A 不可事后检测），建议改为 staged-gitlink 指向子仓 origin/main 的可检口径 |
| CR-DEBT-GATE-ENUM-01（批次一遗留） | 债务 gate_level 值域违约实证 | 小实现：debt 注册表 lint 加值域校验 |

## --strict shadow 状态

剩余 25 条未引用 = 8 待决 + 17 个经批次一判定的真未实现/孤儿——**未归零，--strict
不上门禁**。shadow 巡检可先行：`python3 bin/gac/check-rule-wiring-coverage.py --strict`
退出码语义（0=无新增）已具备，建议批次三做 shadow 观察一周后再强制。
