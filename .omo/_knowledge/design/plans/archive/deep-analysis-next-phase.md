# 深度分析与下一阶段规划

> 日期: 2026-05-27 | 基于全项目扫描+4维度分析

---

## 一、系统现状总览

### 1.1 MCP 覆盖矩阵

```
 项目          | MCP Server | 工具数 | 传输方式      | 端口
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 gbrain-repo   | ✅ 74 ops  | 74     | stdio          | -
 KOS           | ✅         | 26     | stdio+SSE      | -
 Agora         | ✅         | 27     | stdio+HTTP     | 7430
 agentmesh     | ✅         | 22     | stdio+SSE      | 3000
 SharedBrain   | ✅ (T6)    | 5(+15) | stdio          | 7420/8080/7421
 Iris          | ✅         | 7      | stdio          | -
 eidos         | ✅         | 5      | stdio          | -
 SSOT          | ✅         | 5      | stdio          | -
 minerva/sophia| ✅         | ~10   | stdio          | 8765
 ontoderive    | ❌         | -     | CLI only       | -
 MetaOS        | ❌         | -     | CLI only       | -
 hermes-webui  | ✅         | ~20   | WebSocket      | 8787
 Forge         | ❌         | -     | CLI only       | -
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 总计          | 10/14 项目 | ~243  | 3 种传输      | 7 端口
```

**关键发现**: ontoderive 和 MetaOS 仍无 MCP 暴露。Forge（111 tools, 423 nodes）无 MCP 接口——这是最大的 MCP 缺失。

### 1.2 集成拓扑图

```
                          MCP Hub
                           Agora
                        (27 tools)
                       ↗  ↑  ↑  ↖
                     /    |  |    \
              gbrain   KOS  eidos  SSOT
             (74 ops) (26)  (5)   (5)
                     \    |  |    /
                      ↘   ↓  ↓  ↙
                   agentmesh
                  (22 tools)
                       ↑
                       |
                    hermes-webui

CLI-only (no MCP): ontoderive, MetaOS, Forge
```

### 1.3 治理合规（引用类型检查）

```
直接 import 违反 (MCP > REST > CLI > import 等级制):
  🔴 kos → eidos              (大量 import, 最严重)
  🟡 iris → eidos             (可选 import)
  🟡 eidos → SharedBrain      (文件系统耦合)
  🟡 iris → minerva           (path 耦合)
  🟡 eidos → kos              (少量)

合规率: ~65% (21 合规 / 5 违规)
```

### 1.4 测试覆盖

| 项目 | 测试数 | 通过率 | CI | 备注 |
|------|--------|--------|----|------|
| SharedBrain | 1371 files | ❌ 失败 | ❌ | Python 3.14 兼容问题 |
| agentmesh | >20 | ✅ 24/24 | ❌ | 仅 bun test |
| KOS | 22 | ❌ 2 fail | ❌ | 需修复 |
| Agora | ~40 | ✅ | ✅ | 稳定 |
| Iris | 66 | ✅ | ❌ | 无 CI |
| MetaOS | 39 | ✅ 39/39 | ✅ | 已修复 |
| SSOT | 50 | ✅ 50/50 | ❌ | 已修复 |
| ontoderive | ~10 | ❌ 1 fail | ❌ | |
| hermes scripts | 80+ 脚本 | ❌ 0 | ❌ | **严重缺口** |
| integration | 6 | ❌ 部分失败 | ❌ | **新置** |

### 1.5 运行时拓扑与 SPOF (已修正)

```
启动依赖链:
  Agora (7430)          ← 服务发现 [已有 degrade 降级模式!]
    ├── agentmesh (3000) ← Agent 编排
    ├── KOS MCP          ← 知识 OS
    ├── eidos MCP        ← Schema 验证
    ├── SSOT MCP         ← 一致性检查
    ├── SharedBrain MCP  ← 数字生命 OS
    └── Iris MCP         ← 连接器

SPOF:
  🟢 Agora 宕机 → degrade cache + direct mode fallback (已有实现)
  🟡 KOS 宕机 → L4/L3/X3 全部失效
  🟡 SharedBrain 宕机 → 器官系统不可用
```

Agora 降级状态机: NORMAL(正常) → 2 failures → DIRECT(缓存+直连) → recovery → NORMAL
参考: Agora/src/agora/service_cache.py (109行), router.py (452行), tests/test_degrade.py (342行, 7+测试)
→ ✅ 分析报告中的 SPOF 判断修正。Agora 并非单点故障。

---

## 二、关键缺口排序

按影响从高到低：

### 🔴 Critical (阻塞战略目标) — 已修正

| # | 缺口 | 影响 | 实际状态 | 建议动作 |
|---|------|------|---------|---------|
| G1 | **hermes 脚本零测试** | 80+ 核心治理脚本无防护 | ✅ 已新增 smoke test 框架 | 持续完善 |
| G2 | **Forge MCP 缺失** | 111 工具无 MCP 接口 | 🟢 实验性代码存在，已正式化 | 本次已创建 server/mcp_server.py |
| G3 | **Agora SPOF** | 全系统 MCP 单点故障 | 🟢 degrade模式已实现(service_cache+router)| 无需额外动作 |
| G4 | **ontoderive MCP 缺失** | 推导引擎只能 CLI | ❌ 仍无 MCP | 仍需创建 ~200LOC |

### 🟡 Medium (阻塞交付质量)

| # | 缺口 | 影响 | 建议动作 |
|---|------|------|---------|
| G5 | **kos→eidos 直接 import** | 违反治理等级 | 抽取 MCP 协议接口 ~150LOC |
| G6 | **SharedBrain 测试 1371 file 失败** | 无测试防护 | 修复 Python 3.14 兼容 ~200LOC |
| G7 | **KOS 2 测试失败** | 质量下降 | 修复 ~50LOC |
| G8 | **CI 覆盖不全** | 6 项目无 CI | 逐个添加 ~100LOC/每个 |

### 🟢 Nice-to-Have

| # | 缺口 | 建议 |
|---|------|------|
| G9 | 统一系统启动编排 | docker-compose + launchd 整合 |
| G10 | 运行状态仪表板 | 汇总所有 daemon 状态 |
| G11 | Agent 可靠性修复 | deep/unspecified-high agent 100% 失败率 |
| G12 | 跨 MCP 认证 | 统一身份认证层 |

---

## 三、下一阶段规划

基于深度分析，建议的 **Phase D（集成与巩固）** 方案：

### Sprint D1: MCP 全覆盖 — 已调整为单一任务

| Wave | 任务 | 依赖 | 估计 |
|------|------|------|------|
| D1.1 | ontoderive MCP server — 唯一仍缺失的 MCP | 无 | 2h |

> Forge MCP → ✅ 本次已创建 (Forge/server/mcp_server.py)
> Agora 降级 → ✅ 已有实现 (service_cache.py + router.py)

### Sprint D2: 测试与质量

| Wave | 任务 | 依赖 | 估计 |
|------|------|------|------|
| D2.1 | hermes 脚本测试框架 | 无 | ✅ 本次已创建 |
| D2.2 | kos→eidos 解耦 (MCP 协议替换 direct import) | 无 | 2h |
| D2.3 | SharedBrain + KOS + ontoderive test 修复 | 无 | 1h |

### Sprint D3: CI 与运维 (Medium)

| Wave | 任务 | 依赖 | 估计 |
|------|------|------|------|
| D3.1 | 6 项目 CI 添加 (KOS/Iris/SSOT/integration/hermes/Forge) | 无 | 3h |
| D3.2 | 统一启动编排 (docker-compose 升级 + launchd) | D3.1 | 2h |
| D3.3 | 运行时仪表板 (汇总 daemon 状态) | D3.2 | 2h |

### Sprint D4: 治理强化 (持续)

| Wave | 任务 | 依赖 | 估计 |
|------|------|------|------|
| D4.1 | Agent deep/unspecified-high 修复或替换 | 无 | 2h |
| D4.2 | 跨 MCP 身份认证 (信任模型代码化) | D4.1 | 3h |

### 并行度

```
D1.1 (Forge MCP)  ──── D1.3 (Agora 降级)
D1.2 (ontoderive MCP) ──┘        (依赖 D1.1+D1.2)
D2.1 (hermes test)  ──── D2.2 (kos→eidos 解耦) ──── D3.1 (CI)
D2.3 (test fixes)   ────┘
D4.1 (agent fix)    ──── D4.2 (auth)
D3.2 (orchestration) ←─── D3.1 (CI)

最大并行: 6 个 Wave (D1.1, D1.2, D2.1, D2.2, D2.3, D4.1)
```

---

## 四、Agent 基础设施根本问题

本次执行中，`deep` 和 `unspecified-high` 类别 Agent 100% 失败（7/7 卡在思考阶段）。
`quick` 和 `explore` 类别成功（11/13）。

**根因分析**:
1. deep/unspecified-high 使用更强的模型 → 思考代价更高 → 更容易在"探索"阶段陷入无限循环
2. 这些 Agent 没有 tool-use 超时保护或思考深度限制
3. 所有失败的 Agent 共同特征：只有 read/think → 从不 write

**建议修复**:
1. 为 deep Agent 添加明确的 tool-use 时间预算（如：5 次 read 后必须 write）
2. 在每次 read 后强制输出一次思考总结 + 下一步计划
3. 如果 3 次 read 后没有 write，自动降级为 quick
