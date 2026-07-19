# Phase 2 兑现期 · 门禁诚实看板

> 禁止用 sim 数字填物理门禁。SSOT：`phase-scope.yaml::metrics_caliber`。

## 三分栏

| 栏 | Gate | 状态 | 口径 | 说明 |
|----|------|------|------|------|
| **Local pass** | G-DEL.2b | OPEN / harness 绿 | process-local | `collab_cli` + CollabBus |
| | G-DEL.4 | OPEN / callchain 绿 | single_repo gbrain | `shared-context-cli` |
| | G-DEL.5b | OPEN / harness 绿 | process-local + kill-switch | `emergence_cli` |
| **Physical open/fail** | G-DEL.3 | OPEN · 未达标 | physical multi-host ≥2 | large-N p99≈101ms Wi-Fi；有线见 `G-DEL-3-WIRED-REMEASURE.md` |
| **BLOCKED** | G-DEL.1 | **BLOCKED** | physical multi-host ≥4 | ADR-0226；需 y7000p SSH + cloud 等 |

## 并行目标（非 G-DEL 物理门禁）

| 目标 | 状态 | 实测 | 入口 |
|------|------|------|------|
| KOS-Q-GROWTH Q4 ≥3000 | **Q4 floor met** | documents=3231 | `bin/gac/kos-seed-import.py --prefer-new` |
| KOS-Q-GROWTH 2027Q1 ≥5000 | 进行中 | 同上 | 叠加家庭/个人 vault |

证据：`.omo/_knowledge/audits/2026-07-20-kos-q4-seed.md`。

## 操作入口

| Gate | 入口 |
|------|------|
| 2b | `bin/delivery/collab_cli.py` |
| 4 | `bin/delivery/shared-context-cli.py` |
| 5b | `bin/delivery/emergence_cli.py` |
| 3 | `bin/delivery/measure_physical.py` + `network_path.py` |
| 1 | 解除条件见 `phase-scope` `g_del_1.unblock_when` |
| KOS | `bin/gac/kos-seed-import.py` · `docs/KOS-QUARTERLY-GROWTH.md` |

## 纪律

1. Local 绿 ≠ Phase 2 全绿。  
2. G-DEL.3 未过前不得宣称「多机同步达标」。  
3. G-DEL.1 在 4 机前不得宣称「调度门禁达标」。  
4. KOS 篇数增长不等于物理 G-DEL 过门。
