---
status: active
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
title: "Spec: Dashboard Sunset Redirector and Port Convergence (BET-Y2Q2-T6-02)"
---
# Spec: Dashboard Sunset Redirector and Port Convergence (BET-Y2Q2-T6-02)

## 1. 概述与设计意图 (Overview & Intent)
随着 Cockpit-UI `/panorama` 治理全景控制舱的全面就绪与双核归一，历史遗留的独立 HTTP 服务（`:43191` 知行底座与 `:43910` Panorama 静态服务）正式进入平稳下线阶段。

为防止人类驾驶员历史浏览器书签失效，以及任何存量自动化脚本因端口突然被拒发生硬性中断，本规范定义双核下线守护与导流服务（`Sunset Redirector`）：
1. **浏览器人类请求**：访问 `:43191` 或 `:43910` 的根路径与 HTML 请求，自动 302 重定向至 `http://localhost:5173/panorama`，并带有友好的过渡过渡 HTML 页面；
2. **API 接口请求**：对于 `/api/panorama/overview`、`/api/gates`、`/health` 等数据接口请求，继续返回当前最新生成的 JSON 遥测快照，确保老旧脚本的无感向下兼容；
3. **轻量常驻守护**：原生 Python 标准库实现，0 外部依赖，极低内存（<15MB）。

## 2. 核心架构与实现设计 (Architecture & Implementation)

### 2.1 导流器实现 (`bin/panorama/sunset-redirector.py`)
- **双端口监听或可配置端口**：默认支持 `--port 43191` 与 `--port 43910`。
- **请求路由处理**：
  - `GET /` 或 `Accept: text/html`：
    - 返回 HTTP 302，`Location: http://localhost:5173/panorama`。
    - 响应体包含暗夜毛玻璃过渡引导页（附带 `<meta http-equiv="refresh" content="1;url=http://localhost:5173/panorama">` 与可点击链接）。
  - `GET /api/panorama/overview` 或数据接口：
    - 读取 `runtime/dashboard/data.json` 或返回结构化降级 payload，HTTP 200 `application/json`。
  - `GET /health`：
    - 返回 `{"status": "SUNSET_REDIRECTING", "target": "http://localhost:5173/panorama"}`。

### 2.2 测试契约 (`tests/test_sunset_redirector.py`)
- 验证浏览器 HTML 请求收到 302 重定向到 `/panorama`；
- 验证 API 请求正常返回 JSON 数据；
- 验证 `/health` 端点状态。

## 3. 验收标准 (Acceptance Criteria)
1. 启动导流守护脚本后，`curl -I http://127.0.0.1:<PORT>/` 明确返回 `302 Found` 且 `Location` 指向 `http://localhost:5173/panorama`；
2. 单元测试全部通过。
