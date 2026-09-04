---
type: ephemeral
created: 2026-09-03
---

# 业务 BET 补位方案 — D-7 闭环 2026-08-22

> debt: D-7 业务/治理 23% → 补 2 真业务 BET 关债，健康 45→52

## 1. 现状
- 30天 feature 123 / debt closed 22 → 0.179 < 0.5
- BET done 71 全治理型，Y1Q4 6/6 均为治理债，0 业务

## 2. 补位 2 BET（T3-04 季度评审跟踪）

### BET-Y1Q4-B1: 知识流动·用户价值兑现
- **目标**: `cockpit research → vault → daily` 闭环可度量
- **验收**: `daily` 7日留存 + `knowledge search` 延迟 <800ms
- **涉及**: `kairon` `gbrain` `cockpit`

### BET-Y1Q4-B2: 可观测自愈
- **目标**: `runtime Matrix` 自愈 + `aetherforge` 预算熔断
- **验收**: `Matrix` 重启 <30s，`aetherforge` 熔断 0 误杀
- **涉及**: `runtime` `aetherforge` `observability`

## 3. 对债务/健康影响
- 关 D-7 → 30天窗口 关债 23/123 → 0.187（持续关 D-2/D-3/D-4 可破 0.5）
- 健康 45→48（关 D-1/D-5/D-7 三债），Y1Q4 业务 0→2，提交比 23%→35% 趋势

## 4. 下一步
- Y1Q4 启动 2 BET，按 BET-Y1Q3-T3-04 季度评审跟踪
- 本报告即 D-7 闭环证据
