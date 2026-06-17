# omostation 架构审计整改方案 v2（修订版）

> 日期: 2026-06-03 | v2修订: 采纳交叉审阅CRITICAL级建议
> 基线修正: 健康分 29.1(非75.2)，债务已解决 0项(非2项)
> 本文档是历史整改修订稿，保留当时的估算、回滚、依赖与修订理由，不是当前系统健康、当前债务状态或当前执行面的权威来源。
> 当前债务以 `/.omo/debt/registry.yaml`、`/.omo/debt/items/*.yaml` 为准；当前系统状态只看 `/.omo/state/system.yaml` 的派生摘要。

---

## 交叉审阅主要修订

| 原方案 | 审阅指出 | 修订 |
|--------|---------|------|
| 健康分75.2→97.0 | system.yaml真实值29.1 | 基线修正为29.1，目标60.0 |
| Hermes估时1-2周 | 零依赖，需加@modelcontextprotocol/sdk等 | 改估3-4周，分两阶段 |
| agentmesh `mv *` | 会移动node_modules/.git | 改为精确路径+先grep检查引用 |
| shared-lib拆分2-3天 | 143模块全量import路径需更新 | 改估7-10天 |
| 无回滚步骤 | 无一有回滚方案 | 每项加回滚 |
| bridge依赖standalone | P2 standalone未启动则bridge无法激活 | 调整执行顺序 |

---

## 问题概览（修正版）

| # | 问题 | Pri | 当前 | 目标 | 估时 | 回滚 |
|---|------|:---:|:----:|:----:|:----:|:----:|
| 1 | Hermes Console骨架 | P0 | 296行 | Phase A: MCP客户端+数据展示 | 3-4周 | git revert |
| 2 | agentmesh TS未归档 | P0 | 533文件原位 | 归档到_archived/ | 1天 | mv回移 |
| 3 | 测试通过率68% | P0 | 709/1038 | 85%+ | 5天 | git checkout |
| 4 | shared-lib太胖 | P1 | 143模块 | 6子包 | 7-10天 | __init__ shim |
| 5 | sharedbrain-bridge | P1 | 桥接壳子 | 可用链接 | 1-2天 | 桥接开关 |
| 6 | SharedBrain遗留代码 | P1 | 旧代码占用 | 清理 | 1天 | mv回移 |
| 7 | gbrain→kairon验证 | P1 | 未验证 | E2E通路<500ms | 1天 | 无(只读测试) |
| 8 | 健康分提升 | P2 | 29.1 | ≥60.0 | 持续 | 无 |
| 9 | standalone验证 | P2 | 未运行 | 端口响应 | 1天 | 无(仅测试) |

---

## 执行顺序（含依赖关系）

```
批次1: agentmesh归档 (P0, 1天)       ← 先做，独立
    │
批次6: SharedBrain清理 (P1, 1天)     ← 可并行，独立
    │
批次3: 测试修复 (P0, 5天)           ← 可并行
    │
批次7: gbrain集成验证 (P1, 1天)      ← 可并行，只读
    │
    ▼
批次9: standalone验证 (P2, 1天)     ← 需要bridge先部署
    │
批次5: bridge激活 (P1, 1-2天)       ← 需要standalone可用
    │
    ▼
批次2: Hermes Console (P0, 3-4周)  ← 需要MCP后端运行
    ├─ Phase A (1-2周): MCP客户端+基础面板
    └─ Phase B (2周): 图谱+图表+告警可视化
    │
批次4: shared-lib拆分 (P1, 7-10天)  ← 低优先级，独立
    │
批次8: 健康分提升 (P2, 持续)        ← 最后
```

---

## 关键批次的修订细节

### 批次1(修订): agentmesh TS归档

**精确步骤:**
1. `grep -r "projects/agentmesh" projects/kairon/ projects/hermes-console/` → 确认引用
2. `mkdir -p projects/_archived/agentmesh/`
3. `mv projects/agentmesh/packages projects/_archived/agentmesh/`
4. `mv projects/agentmesh/src projects/_archived/agentmesh/` (如果有)
5. `mv projects/agentmesh/apps projects/_archived/agentmesh/` (如果有)
6. 保留`projects/agentmesh/README.md` 指向_archived
7. 删除空目录

**验收:** agentmesh核心代码已移动，README指向_archived，无活动引用

**回滚:** `mv projects/_archived/agentmesh/* projects/agentmesh/`

---

### 批次2(修订): Hermes Console — 分两阶段

**Phase A — MCP客户端+基础面板 (1-2周):**
- 新增依赖: `@modelcontextprotocol/sdk`, `react-router-dom`, `@vitejs/plugin-react`
- `src/mcp/client.ts` — MCP连接管理
- `src/mcp/tools.ts` — 工具发现
- `src/dashboard/SearchPanel.tsx` — 搜索+结果
- `src/agent/AgentList.tsx` — Agent列表+状态
- `src/agent/ChatInterface.tsx` — 对话界面
- `src/health/AlertPanel.tsx` — 告警列表

**Phase B — 可视化面板 (2周):**
- 新增依赖: `d3`, `cytoscape`, `recharts`
- `src/dashboard/KnowledgeGraph.tsx` — 图谱可视化
- `src/health/ServiceTopology.tsx` — 拓扑图
- `src/health/MetricsCharts.tsx` — 指标图表
- `src/agent/TaskMonitor.tsx` — 任务监控

**依赖:** 需要gbrain/agora MCP后端运行（批次7完成）

---

### 批次3(修订): 测试修复 — 分类明细

| 目标包 | 失败数 | 主要原因 | 真/假阴性 | 修复策略 |
|--------|:------:|---------|:---------:|---------|
| agora | 15 | GitHub API e2e依赖网络 | 假阴性85% | 加network skip标记 |
| ecos | 25+ | SSB依赖缺失/文件路径 | 假阴性100% | conftest skip |
| agent-runtime | 5 | terminal_run安全级别断言 | 真阴性 | fixassert |
| ecos extended | 8 | EmailSender分类逻辑 | 真阴性 | 更新测试 |
| **合计** | **53+** | | **真≈13, 假≈40** | |

---

### 批次4(修订): shared-lib拆分

**先做import热度分析:**
```bash
rg "from kairon_lib" --type py | awk '{print $2}' | sort | uniq -c | sort -rn | head -20
```

**按引用热度排序拆分:**
1. `governance/` — 最高引用(approval/rbac/policy等)
2. `security/` — 高引用(threat/audit/quarantine)
3. `infra/` — 中(middleware/events/testing)
4. 其余按需

**估时调至7-10天**

---

### 批次5(修订): 解决bridge/standalone死锁

**问题:** bridge激活需要standalone运行，但standalone验证在P2。

**解法:** 
1. 先启动standalone(临时，仅用于bridge开发)
2. bridge + NeuralCenter实现服务发现
3. standalone验证正式计入P1
4. standalone+在一起交付

---

## 交叉审阅检查表(v2)

- [x] 健康分基线修正为29.1，债务已解决修正为0
- [x] Hermes Console估时上调，依赖清单明确，分Phase A/B
- [x] agentmesh归档改为精确路径，加grep引用检查
- [x] shared-lib拆分估时上调，加import热度分析
- [x] 每批次加回滚步骤
- [x] bridge/standalone死锁通过同步执行顺序解决
- [x] 测试修复加分类明细
- [x] 执行顺序含依赖关系(原方案遗漏)
