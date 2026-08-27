---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# AgentMesh Capability Audit

> 日期: 2026-06-02 | Phase 17 (P17-W4-AGENTMESH-AUDIT)
> 范围: 7 TypeScript包 → kairon Python目标

## 包概览

| 包 | 状态 | 源文件 | 目标kairon | 差距 |
|-----|------|:------:|------------|:----:|
| agents | DEPRECATED | 1 README | agent-hub (NEW) | 100% — 需从零创建 |
| core-types | Active | 9 .ts | core-models | 100% — 互补域 |
| domains | Config | 30+ .md/.json | metaos | 最小重叠 — 配置数据 |
| engine | Active | 60+ .ts (~15K行) | agent-runtime | ~95% — agent-runtime是薄壳 |
| gateway | Active | 32 .ts (~5K行) | agora | 架构不同 — 互补 |
| model-orchestrator | Active | 14 .ts (~2K行) | llm-gateway | ~50% — 概念重叠 |
| toolkit | Active | 110+ .ts (~20K行) | forge | 最小重叠 — SDK vs CLI |

## 关键发现

### 1. 无浏览器/Edge依赖 (AR-5风险已解除)
所有agentmesh包仅依赖Node.js/bun API，无browser-specific API。bun:sqlite → Python sqlite3可直接映射。

### 2. 15个TS独有能力必须保留
DSL编译器、16种Agent设计模式、阶段状态机(DF-CEA)、工作流技能、插件沙箱、Swarm协议、3层记忆系统、中间件链、AutoGen、Edge计算代理、LangChain Runnable、Agents.md索引器、能力发现/匹配器、异常检测、ISC语义检查

### 3. 迁移工作量估算
- 总计~20-25K行Python代码
- 跨越8+包
- P19 6周拆分: 前2周核心类型, 中2周引擎, 后2周网关+归档

### 4. 无浏览器能力丢失风险
所有运行时依赖为标准Node.js/bun API。bun:sqlite(3文件)风险最高→Python sqlite3直接替换。

### 5. gateway vs agora 架构根本不同
gateway是agentmesh HTTP API网关。agora是MCP服务网格+融合中枢(DHT发现/联邦/身份CA/信任网/多协议)。两者互补而非重叠。
