---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 5.4.A — Consensus Domain

> 类型: P9 → P8 Task Prompt | 状态: backlog | 预估: 120min
> Phase: 5 → 5.4.A | 负责人: prometheus | 日期: Day 5
> 前置: Wave 5.3 (L3 Collab Domain) 已完成

## 一、目标

实现三级共识模型(L1/L2/L3)，4个MCP工具：创建、查询、过期扫描、续签。

## 二、文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `kos/consensus/__init__.py` | 新建 | 模块声明 |
| `kos/consensus/api.py` | 新建 | kos_consensus表 + 三级共识CRUD + 过期自动处理 |
| `kos/consensus/mcp.py` | 新建 | 4个MCP工具: create, get, list_expired, renew |
| `kos/mcp/server.py` | 修改 | import + dispatch注册consensus.*路由 |

## 三、验收标准

```
☐ 创建L1共识(Agent) → 有效期30天
☐ 创建L2共识(用户参与) → 有效期90天
☐ 创建L3共识(红队验证) → 有效期365天
☐ 查询实体的活跃共识列表
☐ 过期自动标记stale，L1自动续签
☐ KOS MCP Server list_tools 显示 consensus.* 4个工具
```

## 四、关键实现

见09-架构Review与机制设计.md第4节完整代码。
三级共识: level由agreed_by自动判断(含user:→L2, 否则L1)，有效期自动计算。

## 五、→ 下一个Wave

完成后触发 **Wave 5.4.B (保鲜Cron + E2E验证)**。
