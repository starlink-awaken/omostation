# Cockpit 能力地图

> L3 统一入口 · CLI + MCP + Web

---

## 一、架构定位

```
┌─────────────────────────────────────────────────────────────┐
│                    Cockpit — L3 统一入口                      │
├─────────────────────────────────────────────────────────────┤
│  CLI 入口  │  MCP Server  │  Web Dashboard  │  研究管理     │
│  18 cmds  │  20 tools    │  REST API       │  Lifecycle    │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心功能

| 功能 | 说明 | 测试数 |
|------|------|--------|
| CLI 命令 | 18 个子命令 | 30 |
| MCP Server | 20 个工具 | 20 |
| Web Dashboard | FastAPI + Vue | 15 |
| 研究管理 | 研究生命周期 | 9 |

---

## 三、CLI 命令

```bash
cockpit research      # 研究管理
cockpit status        # 系统状态
cockpit contracts     # 契约管理
cockpit governance    # 治理检查
cockpit dashboard     # 启动 Web
```

---

## 四、MCP 工具

| 工具 | 说明 |
|------|------|
| governance_check | X1-X4 治理检查 |
| governance_status | 治理状态 |
| governance_sla | SLA 达成 |
| governance_leaderboard | 排行榜 |
| governance_dashboard | 仪表板数据 |
| governance_history | 历史数据 |

---

## 五、测试覆盖

| 模块 | 测试文件 | 测试用例 |
|------|----------|----------|
| CLI | 15 | ~100 |
| MCP | 10 | ~80 |
| Web | 8 | ~60 |
| 研究 | 6 | ~50 |
| **总计** | **74** | **~600** |

---

*版本: 0.4.0 · 更新: 2026-06-12*
