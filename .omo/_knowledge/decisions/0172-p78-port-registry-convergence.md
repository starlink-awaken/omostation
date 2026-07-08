---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-08
related:
  - 0170-p77-phase7-env-var-port-migration.md
  - 0168-p77-phase5-hardcoded-ports.md
  - 0167-p77-phase4-port-registry-consistency.md
  - ../../../../../protocols/port-registry.yaml
supersedes: []
---

# ADR-0172: P78 — 端口注册表收敛 (deprecated 清理 + transport 字段)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-08), P78 收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **8765/9090 deprecated** | ✅ | port-registry: `status: deprecated`, `state: freed` |
| **transport 字段** | ✅ | 每端口标注 stdio/http/sse/udp/deprecated |
| **conflicts_pending → resolved** | ✅ | 8765/9090 conflict 记录闭环 |
| **GaC rule: CR-DEPRECATED-PORT** | ✅ | governance-checks.yaml: 173 rules |
| **catalog 55 原则** | ✅ | P78-1..5 |
| **ADR-0172** | ✅ | 本 ADR |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

P77 七阶段 env var 重构完成 (50 原则, 172 GaC rules). P78 清理在 P77 流程中暴露的僵尸端口:

- **8765**: 原 minerva/kos/ontoderive 端口, 2026-06 已收敛到 cockpit /dev/*, 但一直保留在 `conflicts_pending`
- **9090**: 原 ecos-dashboard 端口, 2026-06 已收敛到 cockpit /api/ecos/*, 同留僵尸
- 注册表无 `transport` 字段 → 新 reader 不知道端口是 stdio/http/sse/udp

### 1.2 WHAT — port-registry 重构

```yaml
ports:
  3100:
    name: mcp-stdio
    transport: stdio
    status: active
  # ...
```

### 1.3 WHAT — 8765/9090 弃用

```yaml
  8765:
    name: minerva-kos-ontoderive
    transport: deprecated
    status: deprecated
    note: "2026-06 收敛到 cockpit /dev/*. 2026-07-08 标记 deprecated."
```

### 1.4 WHAT — transport 字段定义

| transport | 含义 | 端口数 |
|-----------|------|--------|
| `stdio` | 仅通过 stdio MCP 协议通信, 无独立 HTTP 监听 | 6 |
| `http` | HTTP/HTTPS 服务, 独立监听端口 | 13 |
| `sse` | Server-Sent Events (MCP over SSE) | 3 |
| `udp` | UDP 通信 | 1 |
| `deprecated` | 已弃用, 保留仅用于历史追溯 | 2 |

## 2. 沉淀原则 (P78)

| # | 原则 | 含义 |
|---|------|------|
| P78-1 | **dead-port-cleanup** | 端口功能收敛后必须从 SSOT 显式标记 `status: deprecated` |
| P78-2 | **transport-declaration** | 每个注册端口必须声明 transport 类型 (stdio/http/sse/udp) |
| P78-3 | **conflict-lifecycle** | conflicts_pending 不再 pending 时必须转 resolved 或清理 |
| P78-4 | **ssot-status-machine** | 注册表每个条目标 `status: active|deprecated|reserved`, 无隐含状态 |
| P78-5 | **registry-as-source** | port-registry 是传输方式和状态的 SSOT, 不从代码推断 |
