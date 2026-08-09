---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-09
---
# BET-Y1Q3-T3-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 1 week。Neo4j 生产启用（写面 + 召回 + 降级可见）08-09 落地（done_at 2026-08-09, run 20260809T012847Z），未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| NEO4J_URI 配置生效, 7474/7687 在 port-registry 注册 | ✅ NEO4J_URI=bolt://localhost:7687, 7474/7687 双端口注册 |
| temporal_fact 与 entity_relation 召回走 Neo4j | ✅ memory-os.yaml neo4j_recall: true, neo4j_writer (Phase 7) |
| 服务不可达时降级可见, 不静默回退 | ✅ notes: NEO4J_URI-gated production writes; no false ready claims |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **「生产启用」不等于「全部走 Neo4j」**: 召回 prefer neo4j search 但有降级路径；写面 NEO4J_URI-gated。诚实标注比全量切换更重要（no false ready claims）。
2. **启动方式二选一**: Docker preferred，brew 为后备；本地无 Neo4j 时不可谎报 ready。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- projects/kairon/packages/mos/src/mos/neo4j_writer.py (Phase 7)
- bin/memory-os-neo4j-up.sh 启动脚本
- memory-os.yaml neo4j 配置 (as_of/recall/writer)
- port-registry 7474/7687 注册
- docs/operations/memory-os-neo4j-local.md

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. NEO4J_URI 未设 = 写面不启用；召回在 Neo4j 不可达时走降级且必须可见。
2. 启动: `bin/memory-os-neo4j-up.sh`（Docker preferred / brew 后备）。
3. 端口 7474 (HTTP) / 7687 (Bolt) 已注册，勿占用。
