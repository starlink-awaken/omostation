---
type: ephemeral
created: 2026-09-03
---

# agora P1+P2 深化深度复盘报告 (2026-08-06)

> 复盘范围: P1 (ProcessPool/ProxyManager收口/路径env化) + P2 (/metrics/hashchain/双进程统一/本地调用放行) 全链路。
> 结论: 核心目标达成 (假绿修复/可观测性/深层架构修复), 但复盘暴露 **2 个高危遗留 (含 1 个命令注入级安全漏洞) + 1 个口径 bug + 1 个死代码**。

## 一、PR 合并清单 (全部 MERGED)

| PR | 内容 | commit |
|---|---|---|
| #1047 | P1 三项: ProcessPool 接入 + ProxyManager 收口 + 路径 env 化 | agora 9987103 |
| #1052 | deploy 配置修复: admission=degraded + auth=permissive | agora 2b5a8b1 |
| #1057 | P2 四项: /metrics + hashchain + 双进程统一 + 本地调用放行 | agora d128c5f |
| #1059 | P2 主仓: swarm 面板 agora 健康 + CI deploy-smoke | 主仓 b02d6789 |

## 二、目标达成度

| 目标 | 状态 | 验证 |
|---|---|---|
| 假绿修复 (backends 恒 0) | ✅ | /health 报 6/99 (修复前恒 0) |
| /metrics 可观测 | ✅ | Prometheus 格式输出 |
| audit 防篡改 | ⚠️ 半 | hashchain 写入+verify 实现, 但**无外部校验入口** (死代码) |
| 双进程统一 | ✅ | SSE 单一 owner, gateway 废弃 |
| 本地调用 tools=0 | ✅ | 89 tools (修复前 0) |
| 面板 agora 健康 | ✅ | text+TUI 显示 backends 6/99 |
| CI 部署 smoke | ⚠️ 半 | deploy-smoke 通过, 但仅主仓触发, 子模块侧无快速回归 |

## 三、复盘发现的问题 (按严重度排序)

### 🔴 HIGH-1: `/v1/backends/register` 无认证命令注入 (P2-1 引入)
- **位置**: `mcp_entry.py:90-119` (P2-1 `_register_common_routes` 共用路由)
- **现象**: POST `/v1/backends/register` 无需任何认证即可调用; 接受任意 `command/args/mcp_endpoint`; `pm.add_service` 会 spawn 子进程
- **实测**: `curl -X POST .../v1/backends/register -d '{"name":"x","command":"echo","args":["probe"]}'` → `{"status":"ok"}`
- **当前唯一防线**: admission 元数据缺失拦截 (degraded 模式), 但 `manager.py:264-268` 相对路径判定有 bug (`_is_local_workspace` 用绝对路径匹配 `projects/c2g` 判空), 配置了元数据即可绕过
- **暴露面**: SSE 绑定 `0.0.0.0:7431`, 内网可达 → 任意命令执行
- **影响**: 高危命令注入/SSRF
- **根因**: `_additional_http_routes` 不走 FastMCP AuthMiddleware (Explore 确认 `http.py:515` additional routes 是裸 Route)

### 🟡 MED-2: /health backends 口径量纲混用 (P2-5 我引入)
- **位置**: `tools_health.py:117-120`
- **现象**: `backends_total = len(registry.entries)` = **99 个工具条目**; `backends_alive = len(registry._clients)` = **6 个已连接服务** — 工具数 vs 服务数对比, 误导性强 (99/6 让人以为 93 个挂了, 实际是口径不同)
- **影响**: 指标不可解释, 假红/假绿并存 (我修假绿时引入了新的口径混用)
- **修复方向**: 统一为服务数 vs 服务数, 或明确标注 `tools` 维度

### 🟡 MED-3: verify_chain 死代码 (P2-2 半成品)
- **位置**: `mcp.py:401` verify_chain 定义; 唯一调用是单测
- **现象**: hashchain 写入生效, 但**无 MCP 工具/HTTP 端点/health 校验入口** — 防篡改能力无法被运维验证
- **影响**: hashchain 有写入无校验闭环, 违规写入无法被发现
- **修复方向**: 在 `health_self_check` 暴露 `audit_chain_ok`, 或加 `audit_verify_chain` MCP 工具

### 🟢 LOW-4: serve 死配置残留
- **位置**: `scripts/com.agora.serve.plist` + `install-launchd.sh`
- **现象**: `agora-mcp` 无参数 = stdio 模式, 无 stdin 消费方, 不绑端口不冲突
- **影响**: 死配置, launchctl 列表噪音
- **修复方向**: 删除 serve plist + 卸载逻辑

## 四、其他发现

### deploy-smoke 触发盲区
- 主仓 `agora-ci.yml` 仅主仓 push/PR 触发; **agora 子模块 push 只触发 agora 自身 ci.yml (无 deploy-smoke)**
- 主仓 bump 指针 (纯 gitlink) 对 `projects/agora/**` 路径匹配不确定, 可能漏跑
- **影响**: 子模块侧无法快速回归部署拓扑, 合并后才验证

### 指标三口径 (data quality)
- `services.total=35` (registry.list_all) vs `backends.total=99` (registry.entries) vs `alive=6` (clients)
- 三口径互不对应, 运维解读困难

## 五、后续推进建议 (按优先级)

### P0 (立即, 安全)
1. **/v1/backends/register 加认证**: 复用 `_current_http_request` + `require_agora_api_key` 校验, 或限制为 localhost-only + 来源校验。参考 `tool_call_endpoint` 的 token 注入模式
2. **修复 `manager.py` `_is_local_workspace` 相对路径 bug**: `projects/c2g` vs 绝对路径匹配判空

### P1 (短期, 正确性)
3. **统一 /health backends 口径**: 服务数 vs 服务数 (或明确标 tools), 消除 99/6 误导
4. **暴露 verify_chain**: health_self_check 加 `audit_chain_ok`; 加 `audit_verify_chain` MCP 工具

### P2 (中期, 治理)
5. **补 KNOWN_BACKENDS admission 元数据**: 19 个 backend 中 4 个缺元数据, 9 个子进程断连 (包缺失) — 提升 6/19 连接率
6. **deploy-smoke 子模块侧接入**: agora 自身 ci.yml 加部署 smoke, 或主仓 bump 强制跑

### P3 (长期, 架构)
7. **serve 死配置清理**
8. **指标三口径统一** (services/backends/tools 语义明确化)
9. **生产级认证**: 部署 metaos admission provider + AGORA_API_KEY, 关闭 permissive

## 六、复盘方法论反思

- **P2-5 引入口径 bug**: 修假绿时用 registry._clients 做 alive, 但 total 用了 entries — **修复时的验证只看 alive 是否>0, 没审 total 量纲**。教训: 修复指标时须验证新旧口径语义一致
- **P2-1 引入安全漏洞**: `_register_common_routes` 抽共用路由时把 register 端点也暴露给 SSE, 且未加认证 — **功能扩展时未同步安全评估**。教训: 新增 HTTP 路由须过安全审查
- **P2-2 半成品**: hashchain 写入完整但校验未接线 — **"实现"与"闭环"的差距**, 测试通过≠能力可用
