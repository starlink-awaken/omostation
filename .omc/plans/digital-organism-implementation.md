---
type: ssot
last-reviewed: 2026-08-26
owner: governance-team
---
type: ssot

# 数字生命体 — 全面实施方案

> 参考: `docs/DIGITAL-ORGANISM-ARCHITECTURE.md` (四论框架 + 13条决策 + 缺口审计)
> 模式: Direct Plan | 覆盖: Phase 0-4 全部任务

---

## Requirements Summary

将omostation从"治理框架"升级为"数字生命体"——覆盖工作/家庭/健康/财务/教育全领域, 具备感知/认知/执行/反思/进化能力, 渐进自主, 可扩展给家庭成员, 可形成蜂群。

**核心原则**: 先接血管(连接已有基建), 再建大脑(MOS+Advisor), 再补领域(scene cards), 再建进化(evolution agent), 最后开放(swarm+router)。

---

## Phase 0: 接血管 (CRITICAL, ~1周, 5 tasks)

### P0-T1: MOS agent_belief三表建表
- **文件**: `projects/kairon/packages/mos/src/mos/agent_belief/` (新建)
  - `world_snapshot.py` — 世界快照 schema + 读写
  - `capability_calibration.py` — 能力校准(trust score) schema + 读写
  - `decision_outcome.py` — 决策结果 schema + 读写
- **BOS路径**: `bos://memory/mos/write` (写入), `bos://memory/mos/recall` (读取)
- **验收**: 三表可通过BOS URI读写, 重启后数据持久
- **对应BET**: T3-COGNI (Y1Q1-T3-01)

### P0-T2: Neo4j本地实例配置
- **文件**: `.omo/state/memory-os.env` (NEO4J_URI), `docs/operations/memory-os-neo4j-local.md`
- **命令**: `make mos-neo4j-up` (Docker本地实例)
- **验收**: `echo $NEO4J_URI` 返回bolt://localhost:7687; MOS写入→重启→数据在

### P0-T3: Aetherforge wire到AgentHost
- **文件**: `projects/omo/src/omo/omo_agent_host.py` (扩展tick_all)
- **改动**: 每个agent tick后调 `aetherforge.bus_adapter.emit_event("agent.tick", {agent_id, action, details})`
- **验收**: agent tick行为通过Aetherforge可追踪

### P0-T4: MOS Bridge — outcome→decision_outcome
- **文件**: `bin/ssot/scene-outcome-recorder.py` (扩展)
- **改动**: record_outcome()追加写入MOS decision_outcome表(通过BOS或直接Python import)
- **验收**: outcome记录同时在JSONL和MOS表中出现

### P0-T5: MOS Bridge — reflection→world_snapshot
- **文件**: `bin/ssot/scene-reflection.py` (扩展)
- **改动**: generate_reflection()追加写入MOS world_snapshot表
- **验收**: reflection记录同时在JSONL和MOS中

---

## Phase 1: 建大脑 (HIGH, ~2-3周, 8 tasks)

### P1-T1: MOF M2 Agent Spec模型
- **文件**: `projects/ecos/src/ecos/ssot/mof/m2/agent.yaml` (新建)
- **内容**: agent-id/tier/identity/capabilities/skills/performance/lifecycle schema
- **验收**: MOF schema校验通过

### P1-T2: MOF M2 Permission模型
- **文件**: `projects/ecos/src/ecos/ssot/mof/m2/permission.yaml` (新建)
- **内容**: 7层过滤器schema + 动态授权schema
- **验收**: MOF schema校验通过

### P1-T3: MOF M2 Capability Provider模型
- **文件**: `projects/ecos/src/ecos/ssot/mof/m2/provider.yaml` (新建)
- **内容**: provider-id/capabilities/launch/governance/cost schema
- **验收**: MOF schema校验通过

### P1-T4: Trust Policy Engine实现
- **文件**: `projects/omo/src/omo/scenewatcher.py` (扩展, 不新建)
- **改动**: +trust_score评估 +4原则实现 +滑动窗口阻尼 +滞回区间
- **验收**: evaluate_action(action, context)返回 permit/ask/block + reasoning

### P1-T5: Advisor Agent实现
- **文件**: `projects/omo/src/omo/scenewatcher.py` (继续扩展)
- **改动**: +evaluate_against_telos() +读MOS三表 +L4注入TELOS
- **依赖**: P0-T1 (MOS三表), P1-T4 (Trust Policy)
- **验收**: Agent提议动作 → Advisor评估 → 返回recommend/caution/reject

### P1-T6: Agent Registry实现
- **文件**: `.omo/_truth/registry/agents/` (新建目录) + `bin/ssot/agent-registry.py`
- **内容**: agent spec注册/查询/校验(MOF M2)
- **验收**: 注册一个agent → 查询返回 → MOF校验通过

### P1-T7: L4 injector扩展TELOS
- **文件**: `projects/l4-kernel/src/l4_kernel/claude_injector.py` (扩展)
- **改动**: +TELOS注入模式 (读LifeOS USER/TELOS/ → 注入Agent上下文)
- **验收**: Advisor运行时上下文含TELOS内容

### P1-T8: Eidos PatternMiner wire到Governor
- **文件**: `bin/ssot/pattern-governor-bridge.py` (新建)
- **改动**: 定期调Eidos PatternMiner → 输出模式 → 喂给Governor
- **验收**: PatternMiner输出 → bridge消费 → 产出pattern报告

---

## Phase 2: 补领域 (MEDIUM, ~2-3周, 8 tasks)

### P2-T1~T4: 四领域场景卡 (各3-5张)
- **家庭**: `docs/scene-cards/family-*.yaml` (日历/采购/家务/亲子/家庭财务)
- **健康**: `docs/scene-cards/health-*.yaml` (运动/饮食/体检)
- **教育**: `docs/scene-cards/education-*.yaml` (作业/辅导/成长记录)
- **财务**: `docs/scene-cards/finance-*.yaml` (收支/投资/报税)
- **验收**: 每领域≥3张卡, `make scene-card-check`通过

### P2-T5~T6: 对应journey specs (6-10条)
- **文件**: `docs/journey-specs/family-*.yaml` 等
- **验收**: `make journey-check`通过

### P2-T7: 冷启动 — WPS Notes预灌MOS
- **文件**: `bin/ssot/mos-cold-start.py` (新建)
- **逻辑**: iris list wpsnote → 提取知识 → 写入MOS world_snapshot
- **验收**: MOS world_snapshot非空, 含WPS Notes知识

### P2-T8: 冷启动 — Documents预灌MOS
- **文件**: `bin/ssot/mos-cold-start.py` (扩展)
- **逻辑**: 扫描~/Documents/ → 提取公文模板/工作流程 → 写入MOS
- **验收**: MOS含公文格式知识

---

## Phase 3: 建进化 (MEDIUM, ~3-4周, 7 tasks)

### P3-T1: 可观测性Dashboard
- **文件**: `projects/cockpit/src/cockpit/web/templates/digital-organism.html` (新建)
- **内容**: agent状态面板 + trust趋势图 + journey热力图 + debt看板 + MOS健康
- **验收**: cockpit访问/digital-organism显示实时面板

### P3-T2: Evolution Agent
- **文件**: `bin/ssot/evolution-agent.py` (新建) + `projects/omo/src/omo/omo_agent_host.py` (注册)
- **能力**: 日debt扫描 + 周web research + 月vision审计
- **验收**: 周报产出进化提案JSON

### P3-T3: Risk Gate实现
- **文件**: `bin/ssot/risk-gate.py` (新建)
- **内容**: C5动作分层授权 + 白名单 + 冷却期 + 延迟执行 + 审计
- **验收**: 模拟C5动作 → Risk Gate返回 permit/2FA/human/block

### P3-T4: Permission Matrix实现
- **文件**: `bin/ssot/permission-matrix.py` (新建)
- **内容**: 7层过滤器 + 动态授权 + 学习型权限
- **验收**: 模拟跨twin访问 → 7层过滤 → 返回permit/degraded/deny

### P3-T5: Governor Agent
- **文件**: `projects/omo/src/omo/omo_agent_host.py` (新增GovernorAgent class)
- **能力**: Eidos pattern → 提议新agent + trust策略执行 + 周报synthesis
- **验收**: Governor tick → 输出pattern分析 + trust调整建议

### P3-T6: Workflow Mesh集成
- **文件**: `bin/ssot/journey-runner.py` (扩展)
- **改动**: checkpoint → Workflow Mesh ApprovalRequested事件映射
- **验收**: journey checkpoint产生Mesh审批事件

### P3-T7: 自动Debt写入
- **文件**: `bin/ssot/problem-detector.py` (新建)
- **逻辑**: 扫描metrics/logs → 检测异常/performance drift → 自动写debt.yaml
- **验收**: 制造性能下降 → problem-detector自动写debt条目

---

## Phase 4: 开放 (LOW, 持续, 7 tasks)

### P4-T1: Swarm协议
- **文件**: `.omo/standards/swarm-protocol.md` + `bin/ssot/swarm-manager.py`
- **内容**: twin发现 + 临时编组 + 共享上下文 + 解散
- **验收**: 两个namespace组成swarm → 共享context → 完成后解散

### P4-T2: Capability Router
- **文件**: `bin/ssot/capability-router.py` (新建) + `.omo/_truth/registry/capability-providers.yaml`
- **验收**: 模拟任务 → Router选最佳provider → 返回选择理由

### P4-T3: Multi-namespace隔离
- **文件**: omo workspace扩展 + namespace配置schema
- **验收**: 两个namespace各自独立运行, 互不干扰

### P4-T4: Emergency Override
- **文件**: `bin/ssot/emergency-override.py`
- **验收**: 模拟用户不可用 + 时限紧迫 → Advisor代决策(约束内) → 事后审计

### P4-T5: OA-write连接器
- **文件**: `projects/kairon/packages/iris/src/iris/connectors/seeyon_oa.py` (扩展)
- **内容**: CDP Runtime.evaluate → OA DOM操作 → 公文提交
- **验收**: 通过CDP在OA中执行提交操作(测试环境)

### P4-T6: 银行/电商连接器
- **文件**: 新建connector或browser自动化
- **约束**: 所有操作走Risk Gate C5门禁
- **验收**: 余额查询通过Risk Gate(permit) + 转账触发2FA

### P4-T7: Agent Lifecycle Manager
- **文件**: `bin/ssot/agent-lifecycle.py`
- **内容**: spawn/retire/version + 涌现创建流程
- **验收**: Governor提议新agent → 你确认 → 注册 → 运行 → retire

---

## Acceptance Criteria (全Phase)

| Phase | 验收命令 | 期望 |
|-------|---------|------|
| 0 | `bos://memory/mos/recall` | 返回真实数据(非fixture) |
| 0 | agent tick后查Aetherforge日志 | 有agent行为事件 |
| 1 | `python3 bin/ssot/agent-registry.py list` | 至少5个agent注册 |
| 1 | Advisor.evaluate_action() | 返回recommend+reasoning |
| 2 | `make scene-card-check` | ≥21 cards全通过 |
| 2 | `python3 bin/ssot/mos-cold-start.py` | world_snapshot非空 |
| 3 | cockpit `/digital-organism` | 实时面板可见 |
| 3 | Evolution Agent周报 | 有进化提案JSON |
| 4 | 两namespace组swarm | 共享context完成 |
| 4 | OA提交(CDP) | 提交操作成功(测试) |

---

## Risks and Mitigations

| 风险 | 缓解 |
|------|------|
| MOS三表schema设计不当 → 后续返工 | 先最小schema(id/ts/type/data), 后扩展 |
| Neo4j部署失败 | Docker compose + fixture fallback |
| 冷启动知识质量差 | 人工review预灌数据, 标记confidence |
| Phase膨胀(每个Phase越做越多) | 严格bet-ledger appetite限制, 超时降级 |
| Aetherforge API变化 | Phase 0只做最小wire(emit_event), 不深度依赖 |

---

## Verification

每个Phase完成时:
1. `make ci-local` — 全门禁通过
2. `make scene-card-check && make journey-check` — 场景验证
3. `make tool-audit` — 工具健康
4. 对应Phase的验收命令
5. 写retro: `.omo/_knowledge/retros/PHASE-{N}.md`
