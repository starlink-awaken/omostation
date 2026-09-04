---
schema_version: specification/v1
spec_version: 1.0.0
title: Mobile Cockpit PWA (swipe-to-sign)
bet_id: BET-Y1Q4-T8-02
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-03
last-reviewed: 2026-09-03
type: ssot
last_updated: 2026-09-03
---

# Mobile Cockpit PWA (T8-02)

## Intent

移动端响应式 PWA：待办卡片审阅、左右 Diff 比对、滑动一键署名外发。
私有 PWA 不上架（non_goal）；Face ID (WebAuthn) 二次鉴权；离线审阅+静默同步。

## Architecture (KISS, bun + vite + react)

```
projects/cockpit-ui/ (bun + vite + react PWA, 从零最小骨架)
├─ index.html + manifest.webmanifest + sw.js (离线壳 + localStorage 缓存)
├─ src/pages/MobileCockpit.tsx (write_surface)
│   ├─ 卡片列表 (GET /api/mobile/cards ← im-triage/pipeline 状态面)
│   ├─ 触摸手势: 右滑署名 (sign) / 左滑跳过 (skip) — CSS transform + touch events
│   ├─ WebAuthn Face ID 门: 高危署名前 navigator.credentials.get
│   └─ 离线: SW 缓存 + localStorage 双向同步 (online 事件静默 push)
└─ package.json: bun run build (vite build) / bun test (happy-dom 组件测试)

projects/cockpit/src/cockpit/web/mobile_api.py (write_surface)
└─ FastAPI 路由: GET /api/mobile/cards (聚合 im-triage + supervisor state)
   POST /api/mobile/sign (WebAuthn assertion 校验位 + DLP 前置闸 + 署名落账)
```

## done_when 映射

- ≤300ms 首屏: vite 静态产物 + SW precache (Lighthouse 语义, 断言 bundle 小)
- Face ID: WebAuthn ceremony 接口 (模拟器/无生物识别时降级确认键 — human_gate 边界记录)
- 离线: SW + localStorage; online 静默同步

## Verify (BET contract)

- `cd projects/cockpit-ui && bun run build && bun test` → exit 0
- `make gac-local-gate` → exit 0
