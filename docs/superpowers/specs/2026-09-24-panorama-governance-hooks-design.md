---
schema_version: specification/v1
spec_version: 1.0.0
title: 统一治理 React Query Hooks 与双模供给层实现
bet_id: BET-Y2Q2-T8-06
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

# 统一治理 React Query Hooks 与双模供给层设计规约

## 1. 目标与背景

在主权驾驶舱「双核归一」体系中，全景数据（门禁矩阵、哨兵巡检、道法术器拓扑、BCOS 进化链）需要兼顾动态实时性与极端离线/异常下的可用性。
本设计规约定义了 `useGovernancePanorama` Hook，采用「API First + 本地静态度假降级（Dual-Mode Supply）」策略，确保驾驶舱永不白屏。

## 2. 核心架构与契约

### 2.1 双模获取逻辑
1. **优先模式 (Live Mode)**：向 `/api/governance/panorama` 或 BFF 发起 GET 请求；
2. **容灾模式 (Fallback Mode)**：若网络异常、HTTP 非 2xx 或超时，自动静默降级为内置的完整静态快照数据 `FALLBACK_PANORAMA_DATA`；
3. **状态透传**：向 UI 暴露 `isFallback: boolean` 标识，UI 可根据该标识显示优雅的轻量状态标签（如“静态容灾快照”），但不打断人类正常审阅交互。

### 2.2 接口签名
```typescript
export interface GovernancePanoramaResult {
  data: PanoramaOverviewPayload;
  isLoading: boolean;
  isError: boolean;
  isFallback: boolean;
  refetch: () => Promise<unknown>;
}

export function useGovernancePanorama(): GovernancePanoramaResult;
```

## 3. 验收标准与测试
- 编写完整的 Vitest 单元测试；
- 覆盖 Live API 响应与 Fallback 容灾两种场景；
- 运行 `bun run test:unit src/api/hooks/__tests__/useGovernancePanorama.test.ts` 全部通过。
