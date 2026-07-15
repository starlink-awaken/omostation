# Cockpit 能力地图

> L3 统一入口 · CLI + MCP + Web

---

## 一、架构定位

```
┌─────────────────────────────────────────────────────────────┐
│                    Cockpit — L3 统一入口                      │
├─────────────────────────────────────────────────────────────┤
│  CLI 入口  │  MCP Server  │  Web Dashboard  │  研究管理     │
│  CLI cmds (见 project-registry.yaml)  │  MCP tools (见 project-registry.yaml)    │  REST API       │  Lifecycle    │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心功能

| 功能 | 说明 | 测试数 |
|------|------|--------|
| CLI 命令 | 27+ 个子命令 | 57+ |
| MCP Server | 20 个工具 | 20 |
| Web Dashboard | FastAPI + Vue | 15 |
| 研究管理 | 研究生命周期 | 9 |

---

## 三、CLI 命令

### L3 原生命令
```bash
cockpit research      # 研究管理
cockpit status        # 系统状态
cockpit contracts     # 契约管理
cockpit governance    # 治理检查
cockpit dashboard     # 启动 Web
```

### 项目收敛入口（委派 / 聚合 / 能力化）
```bash
cockpit agora         # 委派 agora CLI (BOS 网关)
cockpit model-driven  # 委派 model-driven CLI (生命周期 / OKR)
cockpit gbrain        # 委派 gbrain CLI (Postgres 知识库)
cockpit kairon        # 聚合 kairon monorepo (kos/eidos/iris/code/...)
cockpit bus           # 能力化 Omni-Bus 三平面
cockpit observe       # 能力化 Langfuse 可观测性栈
cockpit family-hub    # 能力化家庭数字枢纽
cockpit mesh          # 能力化 omlx 算力网格路由
cockpit bos capability # Toolbox 外部能力
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
