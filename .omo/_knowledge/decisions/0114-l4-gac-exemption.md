---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-29
---

# ADR-0114: L4 自我层 GaC 强约束豁免

- **Status**: ACCEPTED
- **Date**: 2026-06-29
- **Authors**: omostation governance (L0/SSOT/M0/MOF 全链路对齐审计 D5)
- **Superseded by**: (无)
- **Related**: [2026-06-29-l0-ssot-m0-mof-alignment.md](../audits/2026-06-29-l0-ssot-m0-mof-alignment.md) (D5), [执行手册](../audits/2026-06-29-l0-ssot-m0-mof-alignment-remediation.md) §5

## Context and Problem Statement

2026-06-29 L0/SSOT/M0/MOF 全链路对齐审计 (D5) 发现:

- `bin/gac-validate.py:44` 的 `LAYER_ENUM = {"M0","L0","L1","L2","L3","I0","X","meta"}` 缺 L4
- `.omo/_truth/registry/governance-checks.yaml:128` 的 `layer_enum` 声明同样缺 L4

**后果**: 任何标 `layer: L4` 的 GaC 规则 → `gac-validate.py:82` schema 校验失败 (`layer not in LAYER_ENUM`) → 所以 **0 条 L4 规则** → `projects/l4-kernel/` (L4 自我层管理面) 整层游离 GaC 治理外.

**根因**: 5+4+1+1 架构演进时, L4 (自我层) 后加, `LAYER_ENUM` 定义未跟上.

## Decision

1. **`LAYER_ENUM` 补 L4** (`gac-validate.py:44` + `governance-checks.yaml:128`), 允许未来按需加 L4 规则 — ✅ 已实施 (本次审计闭环)
2. **当前 L4 不补强约束规则**, 显式豁免 — 本 ADR 记录此决策

## Rationale

- **l4-kernel 变更频次低** — 自我层管理面, 非业务热路径
- **l4-kernel 自身 CI 已守质量** — `projects/l4-kernel/` 有独立测试/lint
- **当前 0 条 L4 规则, 执行层全绿** — GaC drift 0 / mof-validate 132✓ / evidence resolve 1.0, 无盲区事故
- **YAGNI** — 待 l4-kernel 变更频次升 / 出事故, 再补规则 (届时无需再改 enum, 已补)

## Consequences

- **正面**: l4-kernel 变更不被 GaC layer-specific 规则阻塞, 靠项目自身 CI + X1-X4 横切治理守
- **正面**: 未来加 L4 规则无需再改 enum (已补 L4), 降低门槛
- **负面**: L4 层无 layer-specific 治理规则 (如 Stage/Gate / boundary check), 质量全靠项目 CI
- **缓解**: X1-X4 横切 (审计/保鲜/价值/一致性) 仍覆盖 L4 文件; l4-kernel 自身 CI 守代码质量

## Revisit triggers

满足任一条件则重新评估补 L4 规则:
- l4-kernel 月变更频次 > 10 次
- L4 层出现治理事故 (drift / 鸿沟 / 违规写)
- 架构演进使 L4 成为热路径

## 关联

- 审计主报告: [2026-06-29-l0-ssot-m0-mof-alignment.md](../audits/2026-06-29-l0-ssot-m0-mof-alignment.md) (§3 D5)
- 执行手册: [2026-06-29-l0-ssot-m0-mof-alignment-remediation.md](../audits/2026-06-29-l0-ssot-m0-mof-alignment-remediation.md) §5
