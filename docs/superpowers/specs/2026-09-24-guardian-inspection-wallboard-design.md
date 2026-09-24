---
schema_version: specification/v1
spec_version: 1.0.0
title: 74s 哨兵守护与健康大屏组件研发 (GuardianInspectionWallboard)
bet_id: BET-Y2Q2-T7-07
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-24'
last-reviewed: '2026-09-24'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
type: ssot
---

# 74s 哨兵守护与健康大屏组件研发 (GuardianInspectionWallboard) 设计规约

## 1. 目标与背景

74 秒哨兵是体系持续运转的心跳常态巡检引擎。旧体系中哨兵以抽屉或外挂控制台方式呈现，缺少专职全屏监控大屏态。
本规约设计全屏现代化监控大屏 `<GuardianInspectionWallboard />`，支持实时雷达心跳、四大子系统网格巡检、告警分级流与自愈记录展示。

## 2. 核心架构与功能需求

### 2.1 状态接入
- 消费 `useGuardianStatus()` 或 `useGovernancePanorama()`；
- 获取 `pulseIntervalSec = 74`、综合健康度评分 `healthScore`、四大核心子系统状态与告警列表。

### 2.2 视觉与组件布局 (SSDS/v1)
1. **脉冲雷达看板**：
   - 晶体化展示健康得分（如 `99.6%`），动态圆形进度环；
   - 74s 扫描动态心跳倒计时，展示最近心跳时间戳；
2. **四大子系统网格**：
   - 门禁巡航守卫 (`gate_guardian`)
   - 台账原子审计器 (`ledger_auditor`)
   - BCOS 自蒸馏引擎 (`bcos_engine`)
   - TinyBOS 局域网算力网格 (`network_mesh`)
   - 显示各自健康状态（HEALTHY/WARN/DOWN）与端到端延迟（毫秒）；
3. **实时告警与自愈流**：
   - 支持严重度分级筛选（全部/严重/预警/提示）；
   - 展示历史自愈行动（如写锁自愈、分支同步）；
4. **一键巡检触发**：
   - 提供「立即执行哨兵全量巡检」按钮，调用 `refetch()` 并通过 `useToast` 给出响应反馈。

## 3. 验收标准与测试
- 编写 Vitest 单元测试 `GuardianInspectionWallboard.test.tsx`；
- 验证健康评分计算、子系统卡片渲染、一键巡检与告警筛选；
- `bun run test:unit src/views/panorama/__tests__/GuardianInspectionWallboard.test.tsx` 全部 PASS。
