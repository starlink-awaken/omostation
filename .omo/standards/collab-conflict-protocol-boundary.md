---
lifecycle: contract
owner: governance-team
last_updated: "2026-07-29"
---
# 协作冲突协议边界 (P86 B 波 · SSOT)

> Status: MANDATORY | 上位: B1' · R2 · Q1/§STOP · P3 红线  
> 可执行门: `bin/collab/scenario_lib.py`（旧 check-scenario-growth 已归档 bin/_archive/）  
> 审计: `.omo/_knowledge/audits/2026-07-29-p86-r2-adv25-59-boundary-declaration.md`

## 1. 已设计类别 (计入消解成功率分母)

以下类在 `scenario_lib` 有**有意协议实现**，可复测；目标消解成功率 **≥60%**（仅对本集合，不对全对抗集）。

| kind / 场景 | 代表 ADV | 事件/handler | 计入分母 |
|-------------|---------|--------------|----------|
| cycle | ADV01 | cycle_detected | ✅ |
| deadlock | ADV03 | deadlock_break | ✅ |
| broken_chain | ADV05 | broken_chain_detected | ✅ |
| double_claim | ADV07 | double_claim_detected | ✅ |
| partial_failure | ADV09 | partial_failure 合成 | ✅ |
| resource_starvation | ADV11 | starvation 合成 | ✅ |

**分母排除**: 仅对抗、真实任务 0 发生、且协议声明 **unsupported** 的类别（§2）——**不得**用它们刷「全库通过率」。

## 2. 已知边界 (unsupported · 非沉默)

凡 **仅对抗集构造**、真实 runs/done **0 发生** 的类别，协议声明:

> **unsupported / known boundary** — 不补 `_synthesize_*` 以实现「通过」；不为刷分新增检测器。

覆盖范围 (stock freeze 2026-07-29):

| 范围 | 处置 |
|------|------|
| ADV19–23 | byzantine / replay / cross_key — 边界 |
| ADV25–65 | split_brain … double_spend 族 — 边界 (R2) |
| ADV67–185 | wave10+ 能力轨传送带存量 — **一律边界**；已有检测器不回滚、**不算产能** |
| GEN-ADV-* / 变体 vN | 同标准 |

统一声明文案:

```
协议不支持 <kind> (仅对抗集 / 真实 0 发生)。
属已知边界 (unsupported)。禁止为构造场景补实现 (P3/Q1)。
```

## 3. 新增规则 (STOP)

1. 新 ADV / GEN-ADV **无** `real_occurrence_evidence` → **blocking** (`check-scenario-growth`)  
2. ADV 编号 **> ADV_CAP** (冻结为 stock max) 且不在 baseline → blocking  
3. `scenario_lib` detector 数 **> detector baseline** → blocking  
4. 扩大 `baseline-scenario-growth.txt` 行数 → `check-baseline-growth` blocking (须人类批准)

## 4. 红线

❌ 把边界类成功率混入已设计类 ≥60% 分母  
❌ 为仅构造场景新增检测器 / 场景 (无真实发生证据)  
❌ 静默忽略 unsupported（须显式写边界，不可「没写=默认支持」）  
✅ 真实发生 ≥1 → 可派单设计协议后实现  
