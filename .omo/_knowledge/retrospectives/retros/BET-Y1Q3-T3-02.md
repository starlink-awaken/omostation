---
title: BET-Y1Q3-T3-02 复盘 — Neo4j 生产启用 (L2 停审)
type: retro
owner: governance-team
created: 2026-08-16
context: >-
  核实性收口: 代码面 (routing/neo4j-writer/env.sh/port-registry) 已由 ADR-0372 Phase 6-8
  轮次交付, 本 bet 完成生产启用验证 + 本机配置生效。human_gate: true → 实施完停审。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T3-02 复盘 (实施完毕, 待 human gate)

## done_when 对照 (2026-08-16 实测)

| done_when | 结果 | 证据 |
|---|---|---|
| NEO4J_URI 配置生效 + 7474/7687 注册 | ✅ | config/memory-os.env 已建 (NEO4J_URI=bolt://localhost:7687); memory-os-env --check bolt UP; port-registry 已有 NEO4J_HTTP_PORT/BOLT_PORT |
| temporal_fact/entity_relation 召回走 Neo4j | ✅ | routing.py: entity_relation=[NEO4J,GBRAIN,TEMPORAL], temporal_fact=[NEO4J,TEMPORAL,GBRAIN] — NEO4J 第一优先; test_phase7_neo4j_recall 5/5 真实连库 (写+召回) |
| 不可达时降级可见不静默 | ✅ | 停容器 → `bolt: DOWN (run: bash bin/memory-os-neo4j-up.sh)` 明确提示; 恢复命令可见 |

verify 双命令 (make memory-os-check / check-memory-os-surfaces.py) 全过。

## 生产启用状态

- Neo4j 容器 mos-neo4j 运行中 (docker compose, heap 512M 受限, healthcheck 正常)
- 本机 config/memory-os.env 生效 (gitignored 本地配置)
- off_until_NEO4J_URI 状态结束

## Q3

代码面与启用面分离: 基础设施轮次交付了「支持 NEO4J 的代码 + 端口 + 脚本」, 本 bet 交付「URI 配置生效 + 真实召回验证 + 降级可见」。前者 tracked, 后者本机配置+实证。

## 停审理由 (L2 human_gate)

生产启用决策 (Neo4j 常驻 + 事实图走真库) 需人工批准。批准检查点: ①mos-neo4j 容器常驻策略确认 ②资源占用 (heap 512M) 可接受 ③T3-03 (mem0 退役) 与 T6-01 (gbrain/kairon 归并) 依赖本启用。

## Q5 给下一个 agent

- 批准后: T3-03 (mem0 退役) + T6-01 (归并) 依赖解锁
- 若超 2 周未批: circuit_breaker → 保持 TemporalShadow, registry 标 degraded
