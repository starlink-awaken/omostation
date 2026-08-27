---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: tool-heatmap-phase28.md
deprecated-since: 2026-06-23

---

# 工具使用热力图 — Phase 28 基线审计

> 生成: 2026-06-05 · 数据源: agora-routes.json + trace_log.jsonl
> 任务: P28-W0-TOOL-HEATMAP
> 历史工具热力图审计 / reference only。本文记录 Phase 28 时点的注册与调用样本，不是当前 Agora 路由覆盖、当前工具可达性或当前调用热度 SSOT。
> 当前事实请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、当前路由/测试/治理证据。

---

## 核心发现（一句话）

**agora 网关对真实业务工具是透明的——所有 L1 知识工具均未注册，调用全部绕道或失败。**

---

## 一、注册路由现状

### 根目录 `agora-routes.json`
```json
{
  "test.tool": "test-svc",
  "eidos": "eidos"
}
```

### `src/agora-routes.json`
```json
{
  "test.tool": "test-svc"
}
```

**结论：agora 路由表极度稀疏，只有 1-2 条测试条目，零个真实 L1 业务工具注册。**

---

## 二、调用频次热力图（trace_log 统计）

> 注：trace_log 内容全部为测试用例产生，无真实用户会话调用记录。

### 🔴 高频调用 · 全部失败（not_found）

| 工具 | 调用次数（样本） | 状态 | 原因 |
|------|----------------|------|------|
| `ontoderive.derive` | 12+ | ❌ not_found | 未注册到 agora 路由 |
| `ontoderive.check` | 12+ | ❌ not_found | 未注册到 agora 路由 |
| `research_now` (minerva) | 8+ | ❌ 502 / no_instance | minerva 服务不可用 |
| `minerva.research` | 4+ | ❌ not_found | 未注册到 agora 路由 |
| `toolforge.match` | 4+ | ❌ not_found | 未注册到 agora 路由 |

### 🟡 测试服务 · 部分成功（仅 mock）

| 工具 | 调用次数 | 状态 | 说明 |
|------|---------|------|------|
| `mcp-svc.tool` | 2 | ✅ ok | 测试 mock 服务 |
| `rest-api.create` | 2 | ✅ ok | 测试 mock 服务 |
| `retry-api.get` | 2 | ✅ ok | 测试 mock 服务 |

### ⚪ 零调用（agora-routes 中注册但无 trace 记录）

| 工具 | 注册服务 | 调用次数 |
|------|---------|---------|
| `eidos` | eidos | 0（仅在 routes 中注册，无调用记录） |

---

## 三、L1 包网关覆盖度扫描

对比 kairon 25 包现状与 agora 注册情况：

| 包 | 工具数 | agora 注册 | 实际可路由 |
|----|--------|-----------|-----------|
| eidos | 7 MCP tools | ✅ 注册 | ⚠️ 无调用记录 |
| kos | 26 tools | ❌ 未注册 | ❌ |
| minerva | 5 super-tools | ❌ 未注册（502） | ❌ |
| sophia | 8 tools | ❌ 未注册 | ❌ |
| iris | 8 tools | ❌ 未注册 | ❌ |
| ssot | 6 tools | ❌ 未注册 | ❌ |
| forge | 89 tools | ❌ 未注册 | ❌ |
| ontoderive | N tools | ❌ 未注册 | ❌ |
| kronos | 9 tools | ❌ 未注册 | ❌ |
| 其余 16 包 | — | ❌ 未注册 | ❌ |

**覆盖率：1/25 包（4%）**

---

## 四、关键结论

### 结论 1：G27.1 KPI 未落地
Phase 27 G27.1 声明的 KPI：
> "所有 L1 知识工具包必须通过 agora 网关代理，切断跨包函数直连调用"

**实际状态**：agora 路由表仅 2 条，25 个包中只有 eidos 注册（且无调用记录）。L1 工具包仍通过函数直连调用，agora 网关对真实业务透明。

### 结论 2：技术情报雷达的实现路径更清晰了
场景 B（TECH-RADAR）**不依赖 agora 网关正常运行**——可直接调用 kairon 包（minerva/sophia/kos），绕过 agora，先跑通业务逻辑，再补网关注册。

### 结论 3：minerva 服务需要先启动
`research_now` 的 502 错误说明 minerva MCP 服务（localhost:8765）未运行。TECH-RADAR 实现的第一步是把 minerva 服务跑起来。

---

## 五、建议行动

| 优先级 | 行动 | 关联任务 |
|--------|------|---------|
| P0 | 启动 minerva MCP 服务（localhost:8765） | P28-W1-TECH-RADAR |
| P0 | 用直接包调用（非 agora）先跑通 TECH-RADAR | P28-W1-TECH-RADAR |
| P1 | 把 kos/minerva/sophia 注册到 agora 路由表 | 新建补充任务 |
| P1 | E2E-DEMO 场景 A 同样先用直接调用跑通 | P28-W1-E2E-DEMO |
| P2 | 审计 G27.1 实际完成度，更新 Phase 27 交付物 | 补充任务 |

---

*数据来源: agora-routes.json (2 routes) + trace_log.jsonl (样本分析，全量约 279KB)*
