---
id: ADR-0251
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-07-28
related:
  - 0250-health-gate-engineering-surface-only.md
  - 0249-governance-budget-cap-40-40-20.md
  - 0238-mof-m4-phase0-registry-self-governance.md
supersedes: []
amends: []
type: ssot
---

# ADR-0251: 三把锁 gate 定位 (layer-call/drift/doc-claims) + layer-call 增量快路径

## Context

P0-A (integrated-governance §P0) 把三把已存在检查器接线进 SGF gate (sgf-policy.yaml gates 列表),
但 `gac-local-gate.py:93-95` 旧注释误判 "三检查器当前 exit=0 (只报告不阻断) / layer-call
需另加 baseline 机制, 见 follow-up task". G2 核实发现**双重过时**:

1. layer-call `--baseline` new-violation blocking 早已实现 (`check-layer-call-direction.py` L213-229)
2. 三锁实际 **blocking** (不在 `SOFT_CHECKS`, exit!=0 → gate `[FAIL]`), 非 informational

另: layer-call 全量扫描带 `--baseline` 在 CI >25s 超时 (exit=124), pre-commit 不可用 (G1).

## Decision

三锁 gate 定位 (**均 BLOCKING**):

| 检查器 | 定位 | 机制 | 当前状态 (2026-07-28) |
|--------|------|------|---------------------|
| layer-call-direction | **BLOCKING** | `--baseline` new-violation (存量 11 grace) + `--files` 增量快路径 (G1) | 11 grace / 0 new, exit 0 |
| mof-capabilities-drift | **BLOCKING** | exit 1 on any drift (声明/执行鸿沟, P71 类 A 严重) | drift=0, exit 0 |
| doc-claims | **BLOCKING** | exit 1 on findings (`--project all` 17 projects 全覆盖) | 0 findings, exit 0 |

**不在 `SOFT_CHECKS`** (`gac-local-gate.py` L121-124) → exit!=0 时 gate `[FAIL]` 阻断, **非 informational**.

layer-call G1 增量快路径:
- checker 加 `--files <paths>` (`scan_files`, 只扫指定文件, baseline 比较逻辑不变)
- gate `scoped_layer_call_command`: pre-commit (非 strict) 传 staged `.py/.ts/.tsx` → `--files`; CI strict 全量 baseline

## Rationale

- **layer-call blocking**: 跨层 import 违规是架构性, 新违规必须拦. baseline (存量 grace + 新违规 fail) 平衡历史债与新违规防护.
- **drift blocking**: registry 声明 vs 实现漂移 = 声明/执行鸿沟 (P71 类 A), 不能软挡. drift=0 时不卡.
- **doc-claims blocking**: 文档裸数字宣称失真, scope=all 全覆盖. 0 findings 时不卡.
- 三锁均**非 informational**: informational 门禁 = 没门禁. 三锁当前全绿 (grace/drift/findings 归零), blocking 不卡工程推进.

## Enforcement

- `gac-local-gate.py` `SOFT_CHECKS` **不含**三锁 (保持 blocking).
- layer-call `--baseline` **严禁塞新违规造假绿** (= 重建假绿, 最高级违规).
- layer-call `--files` 增量**不跳过** (无 staged 代码 → 全量 baseline, 保持覆盖).
- baseline 11 条逐条 triage 清零 (只减不增).
- **不得靠调大超时或 `|| true` 掩盖性能问题** (G1 红线).

## 实测验证 (2026-07-28)

| 测试 | 结果 |
|------|------|
| layer-call 全量 `--baseline` | exit 0, ok=True, new=0, grace=11 (~3s) |
| layer-call `--files` (baseline grace 文件) | exit 0, grace=1 (**不误伤存量**) |
| layer-call `--files` 注入新违规 | **exit 1 (拦)** |
| `--files` 耗时 | **0.042s** (pre-commit <5s 目标, ~120x 提升) |
| gate `--scope files` 增量 | `[PASS] layer-call-direction-check --files <staged>` |
| drift gate | exit 0, 0 drift |
| doc-claims `--project all` | exit 0, 17 projects, 0 findings |

## Related

- 上游: P0-A (integrated-governance §P0), G1/G2 (本轮 strat-p82 follow-up)
- 实现: `bin/ssot/check-layer-call-direction.py` (L213-229 baseline, `scan_files` + `--files`), `bin/gac/gac-local-gate.py` (`scoped_layer_call_command`, `SOFT_CHECKS`), `bin/mof/check-{doc-claims,mof-capabilities-drift}.py` (定位注释)
- gate 注册: `projects/ecos/src/ecos/ssot/mof/m1/governance/sgf-policy.yaml` (gates: mof-capabilities-drift-check / doc-claims-check / layer-call-direction-check)
