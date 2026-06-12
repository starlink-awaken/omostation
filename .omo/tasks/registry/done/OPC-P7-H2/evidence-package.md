# OPC P7-H2 跨仓 phase gate 实装 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P7 / Gate H / Sub-gate H2

## 1. check_phase_gate.py 跑通

```text
$ python3 scripts/opc_p7_phase_gate_check.py
```

9 phase × gate 矩阵 (取自 `.omo/_delivery/phase-gate/2026-06-12.json`):

| 阶段 | Gate | Status | Sub-gates |
|------|------|--------|-----------|
| P0 | Gate A | missing | 0/0 (历史 plan 不存在, 不假装全绿) |
| P1 | Gate B | missing | 0/0 |
| P1.5 | Gate B2 | missing | 0/0 |
| P2 | Gate C | passed | 4/4 |
| P3 | Gate D | passed | 5/5 |
| P4 | Gate E | passed | 5/5 |
| P5 | Gate F | not_yet_passed | 1/4 (closeout 阶段) |
| P6 | Gate G | not_yet_passed | 0/4 (closeout 阶段) |
| P7 | Gate H | not_yet_passed | 2/5 (closeout 阶段) |

`phases_total: 9, phases_passed: 3, phases_open: 6`.

## 2. 落盘 audit

- `.omo/_delivery/phase-gate/2026-06-12.json` — 完整 9 phase × gate 矩阵
- `.omo/_delivery/phase-gate/2026-06-12.md` — 人类可读 markdown 报告

## 3. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | check_phase_gate.py 跑通 | ✅ | exit 0, 9 phase 全扫 |
| 2 | 9 Gate acceptance 自动检查 (P0-P7 + P1.5) | ✅ | 9 phase × gate 矩阵 |
| 3 | audit 写入 | ✅ | phase-gate/{date}.json + .md 双写 |

## 4. 红线遵守

- ✅ 9 gate 全扫 (P0-P7 + P1.5)
- ✅ P0/P1/P1.5 历史 plan 文件不存在 → 标记 `missing` (不假装全绿)
- ✅ P5/P6/P7 仍 not_yet_passed (closeout 阶段, 不本 review 替代 closeout)
- ✅ phase-gate 报告 (P7 not_yet_passed) 与 plan.yaml (P7 not_yet_passed) 一致 (SSOT 自洽)

## 5. 模拟说明

> phase-gate 自动检查实施完成, 9 phase × gate 矩阵生成器已落地.
> 真实情况: P5/P6/P7 closeout 阶段 (本轮 11 个子门同步 closeout 中),
> phase-gate 报告 "P7 not_yet_passed" 与 plan.yaml 一致 (SSOT 自洽).
> 完整 closeout 完成后 phase-gate 报告 phases_passed=9, phases_open=0.
