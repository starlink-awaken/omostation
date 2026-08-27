---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: design-dashboard-cockpit.md
deprecated-since: 2026-06-23

---

# P0-DASHBOARD_COCKPIT 设计方案

> 2026-06-06 | 状态: design-locked

## 目标
将现有的碎片化 Dashboard 升级为 eCOS 统一驾驶舱，聚合服务健康/事件流/快速入口。

## 现状分析
- Agora 有独立 Web Dashboard（`agora/web/dashboard.html`）— 硬编码 WS 连接
- `projects/runtime/` 有 `dashboard_server.py` — HTTP API for I0 data
- `~/Documents/驾驶舱/` 有个人 CARDS/DASHBOARD/SIGNALS
- 三者互不关联

## 设计方案

### Phase 1 (MVP, 2h)
在 `projects/runtime/` 的 CLI 中添加 `runtime dashboard` 命令：
```
用法: runtime dashboard [--watch]
```

输出:
```
╔══════════════════════════════════════╗
║  eCOS Dashboard              99.5   ║
╠══════════════════════════════════════╣
║ Services:  12 total (8 running)      ║
║ Protocols: 16 total (1 active)       ║
║ Debts:     73 total (66 resolved)    ║
║ Phase:     28 → W3 → W4             ║
╚══════════════════════════════════════╝
```

数据来源:
- 服务状态: `runtime matrix list` (projects/runtime matrix)
- 债务: `.omo/debt/registry.yaml` + dashboard state
- Phase: `.omo/state/system.yaml`

### Phase 2 (未来相位)
Web 面板聚合 `agora/dashboard.html` + `runtime/dashboard_server.py`
到单一静态 HTML，通过 `runtime dashboard --serve` 端口提供 HTTP 服务。

## 实施计划
1. ✅ `runtime kei dashboard` — 已实现
2. 命令行版 dashboard — 排期
3. Web 聚合 — 后续 Phase

参考: `.omo/state/system.yaml`, `.omo/debt/registry.yaml`
