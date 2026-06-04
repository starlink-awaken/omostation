# Phase 5 — Self-Collab-Consensus 架构落地

> **周期**: 2026-05-25 ~ 2026-06-02 (8天)
> **负责人**: hermes (P8: prometheus) + 老王 (P10: atlas)
> **目标**: 实现4+1+3架构的自我层(L4)、协作层(L3)、价值堆栈(X3)三大缺口的基础设施
> **前置**: Phase 4 (文档+CI+测试) 已完成
> **风险**: KOS MCP Server需原地扩展而非新建进程，确保不影响现有13个工具
> **验收总标准**: 所有MCP工具可通过Agora调用，End-to-End测试全部通过

---

## Wave 5.1 — Eidos Schema + KOS EntityType (Day 1-2)

### Wave 5.1.A — Eidos Schema 定义 (Day 1)

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T063 | 在`eidos/schemas/`下创建4个新JSON Schema: identity-role, value-principle, consensus, task-object | `workspace contracts validate` 通过所有新Schema | 60min |
| T064 | 在`eidos/schemas/registry.json`注册新Schema，各Schema附版本号 | `workspace contracts list` 显示新条目 | 15min |
| T065 | 在`~/Workspace/eidos/`创建`schemas/epoch-life.json`（基于RETRO经验，每个组件需带`--json`输出和路径无关约束） | Schema约束字段含`json_output`和`path_free` | 30min |

### Wave 5.1.B — KOS EntityType 扩展 (Day 2)

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T066 | 修改`kos/ontology/_types.py`：EntityType增加ROLE/AXIOM/PRINCIPLE/THEORY/FRAMEWORK/SKILL/CONSENSUS/TASK 8个新类型，对应新增前缀 | `python3 -c "from kos.ontology._types import EntityType; print(list(EntityType))"` 显示15个类型 | 30min |
| T067 | 修改Entity dataclass增加Value Stack字段: value_tier, half_life_days, freshness_status, last_validated, next_review, references | Entity类支持所有新字段的序列化/反序列化 | 30min |
| T068 | 为KOS索引器增加新实体类型的提取规则（`ENTITY_REF_RE`模式扩展） | `kos ontology rebuild` 不报错，新类型实体可被提取 | 30min |

---

## Wave 5.2 — L4 Self Domain (Day 3)

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T069 | 创建`kos/self/__init__.py`和`kos/self/api.py`：提供get_profile/update_profile/get_current_role/get_vision_summary 4个API，数据存`~/.kos/self/profile.json` | `python3 -c "from kos.self.api import get_profile; print(get_profile())"` 返回带默认值的profile | 45min |
| T070 | 在`kos/self/mcp.py`导出SELF_TOOLS和SELF_HANDLERS，实现3个MCP工具: self.get_profile, self.get_current_role, self.get_vision_summary | 每个工具可独立调用，返回JSON格式符合Eidos Schema | 60min |
| T071 | 修改`kos/mcp/server.py`：在run_stdio中import并注册SELF_TOOLS和SELF_HANDLERS，dispatch增加self.前缀路由 | KOS MCP Server重启后list_tools包含self.*工具 | 30min |
| T072 | 写`~/.hermes/scripts/self_inject.sh`：每天首次交互时调用self.get_vision_summary，把结果注入Hermes prompt | 每天第一条消息自动加载L4画像 | 30min |

---

## Wave 5.3 — L3 TaskObject Domain (Day 4)

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T073 | 创建`kos/collab/__init__.py`和`kos/collab/api.py`：在KOS检索库中新增kos_collab_tasks表(CREATE TABLE)，实现create_task/get_task/list_tasks/update_task | SQLite表创建成功，CRUD基本操作可用 | 45min |
| T074 | 在`kos/collab/api.py`实现claim_subtask(含BEGIN IMMEDIATE行锁+依赖检查)和complete_subtask(含进度自动计算) | 并发调用claim_subtask时只有一个成功；依赖未满足时返回DEPENDENCY_NOT_MET | 60min |
| T075 | 在`kos/collab/mcp.py`导出COLLAB_TOOLS和COLLAB_HANDLERS，实现6个MCP工具: create_task, get_task, list_tasks, update_task, claim_subtask, add_artifact | E2E链路: 创建→认领→完成→查看 跑通 | 60min |
| T076 | 修改`kos/mcp/server.py`注册collab.*工具，dispatch增加collab.前缀路由 | list_tools包含collab.*工具 | 15min |

---

## Wave 5.4 — X3 Consensus Domain + 保鲜Cron (Day 5-6)

### Wave 5.4.A — Consensus 系统 (Day 5)

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T077 | 创建`kos/consensus/__init__.py`和`kos/consensus/api.py`：在KOS检索库中新增kos_consensus表，实现三级共识模型(L1 Agent/L2 User/L3 RedTeam) | 创建L1/L2/L3共识，有效期自动计算 | 45min |
| T078 | 在`kos/consensus/mcp.py`导出CONSENSUS_TOOLS和CONSENSUS_HANDLERS，实现4个MCP工具: create, get, list_expired, renew | 共识创建→查询→过期→续签 全链路跑通 | 60min |
| T079 | 修改`kos/mcp/server.py`注册consensus.*工具，dispatch增加consensus.前缀路由 | list_tools包含consensus.*工具 | 15min |

### Wave 5.4.B — 保鲜Cron + 集成验证 (Day 6-8)

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T080 | 写`~/.hermes/scripts/freshness_check.sh`：扫描半衰期到期的实体，标记stale；L1共识自动续签，L2/L3等待确认 | 每周一早8点运行，过期实体在报告中列出，无异常时静默 | 45min |
| T081 | 在Agora中验证所有新工具可调用：self.*, collab.*, consensus.*共13个 | `agora tool list | grep -E "self|collab|consensus"` 显示13个工具 | 30min |
| T082 | 编写`phase5_e2e_test.py`端到端测试：L4→L3→X3完整链路 | `python3 phase5_e2e_test.py` ALL PASSED | 45min |
| T083 | 更新`.omo/INVENTORY.md`和`.omo/STATE.md`反映Phase 5完成状态 | STATE.md显示Phase 5进度100% | 15min |

---

## 依赖关系

```
Wave 5.1.A (Day 1: Eidos Schema)
  │
  └──→ Wave 5.1.B (Day 2: KOS EntityType)
         │
         ├──→ Wave 5.2 (Day 3: L4 Self) ───────→ Phase 5 E2E Test (Day 7-8)
         │
         ├──→ Wave 5.3 (Day 4: L3 TaskObject) ──→ Phase 5 E2E Test
         │
         └──→ Wave 5.4.A (Day 5: Consensus) ───→ Wave 5.4.B (Day 6: Cron)
                                                       │
                                                       └──→ Phase 5 E2E Test
```

## 回滚策略

| 失败场景 | 回滚操作 |
|---------|---------|
| KOS EntityType新增导致现有代码崩溃 | `git checkout kos/ontology/_types.py` |
| MCP Server注册新工具后启动失败 | 回退server.py，删掉新增的import和dispatch |
| Self数据写错 | 删除`~/.kos/self/profile.json`（自动重建） |
| TaskObject数据损坏 | `DROP TABLE kos_collab_tasks`（任务丢失但系统恢复） |
| Consensus数据冲突 | `DELETE FROM kos_consensus WHERE status='active'` |

## Wave → Task Prompt 索引

| Wave | 对应Task Prompt | 生成日 |
|------|----------------|--------|
| 5.1.A | `.omo/task-prompts/wave-5.1A-eidos-schema.md` | Day 1 |
| 5.1.B | `.omo/task-prompts/wave-5.1B-kos-entitytypes.md` | Day 2 |
| 5.2 | `.omo/task-prompts/wave-5.2-self-domain.md` | Day 3 |
| 5.3 | `.omo/task-prompts/wave-5.3-collab-domain.md` | Day 4 |
| 5.4.A | `.omo/task-prompts/wave-5.4A-consensus.md` | Day 5 |
| 5.4.B | `.omo/task-prompts/wave-5.4B-cron-e2e.md` | Day 6-8 |
