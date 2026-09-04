---
title: E-DOC 边界规则生效状态核实报告 (OPS-INFRA 任务 1)
type: audit
owner: governance-agent
created: 2026-08-17
bet: BET-Y1Q1-T6-08
related:
  - docs/adr/ADR-0191-workspace-documents-dual-plane-architecture.md
  - docs/OPS-INFRA-GOVERNANCE-LONGTERM-BLUEPRINT-2026-08.md
last_updated: 2026-08-25
lifecycle: history
---

# E-DOC-001~005 (即 ADR-0191 §2.2 ln 规则集) 生效状态核实

## 结论速览

**五条全部为「仅设计，未接线」**。规则定义只存在于 ADR-0191 Markdown 正文，
MOF 规则引擎（governance-checks registry）、CI 拦截器、Agent Preflight 均无对应实现。

## 逐条证据 (2026-08-17 实测)

| 规则 | 语义 | 检索 | 结论 |
|---|---|---|---|
| E-DOC-001 (ln-001) | 禁止 Documents 下可执行脚本 | `rg 'ln-001'` registry/bin/ecos 全零命中 | **仅设计** |
| E-DOC-002 (ln-002) | 禁依赖环境目录入 Documents | 同上零命中 | **仅设计** |
| E-DOC-003 (ln-003) | 跨域修改须走 signals/Agora | governance-checks.yaml 无对应 check_type | **仅设计** |
| E-DOC-004 (ln-004) | facts 14 天保鲜门禁 | registry 仅 freshness 泛规则（X2 面向子仓 freshness_seconds），非 documents facts 专用 | **仅设计**（存在语义相邻但非同物） |
| E-DOC-005 (ln-005) | 多客户端配置单源生成 | `bin/gac/documents-claude-desktop-config.py` + `documents-zcode-config.py` **存在**，SSOT `documents-domain-projects.yaml` 存在 | **部分接线**（生成工具在，但无 REQUIRED 级拦截规则强制"禁手工维护"） |

检索记录：`rg -rln 'ln-00[1-5]' .omo/_truth/registry/ bin/ projects/ecos/src/` → 零输出。
ADR-0191 的 `Diagnostic Envelope` 修复建议机制同样零实现
（`rg 'DiagnosticEnvelope|diagnostic_envelope'` 零命中）。

## 命名勘误（打假）

派工指令称"E-DOC-001~005 来自 ADR-0190（PR #1626）"——**两处不准**：
1. `.omo/_knowledge/decisions/0190-*` 实为 "Wave2 dashboard JSON contract"，
   MOF 动态约束引擎的 0190 是 `docs/adr/ADR-0190-mof-dynamic-constraint-engine.md`（两套 ADR 目录撞号）；
2. E-DOC 编号在仓内任何文件中**不存在**——实际规则编号是 ADR-0191 §2.2 的 `ln-001~005`。
   指令起草者（蓝图 §1.3）自己转写时换了名，未回仓核对。

## 未做违规样本注入测试的理由

指令允许"找到实现后构造最小违规样本验证拦截"。既然实现不存在，该步骤前提不成立——
如实记录，不伪造"测试通过"。

## 建议（交人类排期，本轮不执行）

1. 若决定接线：5 条规则落 `governance-checks.yaml` + `bin/gac/check-documents-boundary.py`
   （建议一次脚本承载 001/002/003 三条静态检查，004 复用 freshness 语义，005 走 CI drift 检查）
2. 若决定不接线：ADR-0191 §2.2 标注 `status: DESIGN-ONLY (not enforced)`，消除歧义
3. 撞号问题：`docs/adr/` 与 `.omo/_knowledge/decisions/` 的 ADR-0190 各指不同物，建议 ADR 索引加目录前缀消歧


## 处置 (2026-08-17 同日, 用户批准 H2)

H2 已执行: ADR-0191 §2.2 双镜像 (docs/adr + docs/governance) 均已标注
DESIGN-ONLY (not enforced)。接线 (H1) 留待下轮排期。
