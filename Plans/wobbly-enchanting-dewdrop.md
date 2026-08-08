# Gap 清零规划 — 数字生命体自主迭代闭环落地

> 创建: 2026-08-08 | 前置: 28个gap items注册 (`.omo/debt/gap-items/`) · DoD标准确立
> 战略: 先B(数据流+验证) → 后C(Autoloop+Evolution) → 再D(自主tick)
> 教训: 上次"39/39完成但43%实际" — 根因是DoD缺失。本轮所有task必须有端到端evidence。

---

## 0. Context — 为什么做这个

### 问题链
1. 上次"完成"=代码存在，非功能可验证 → stub也标记完成
2. 5个agent中3个是stub (KnowledgeCurator/Governor/SceneWatcher)
3. 数据流断裂3处 (信号→MOS, outcome→Trust, 反思→进化)
4. 运行时从未跑过真实业务 (全dry-run)
5. Autopoiesis(自创生)完全缺失

### 关键修正 (truth-driven)
探索后发现**3个gap评估不准确**，需在T0校准：
- **GovernorAgent** 不是stub — 有journey timeout扫描逻辑 (omo_agent_host.py:330-346)，只是缺debt/trust趋势扫描
- **evolution-agent.py** 不是stub — 有scan_internal逻辑 (能调用problem-detector + tool-audit)，缺外部抓取 + 调度 + 落地
- **problem-detector.py** 不是stub — 有health/dormant/scene检测逻辑，缺定期调度

### 本轮目标
28个gap中，**本轮可独立清零** (不依赖用户环境):
- 运行时服务(KOS/Neo4j/iris)未启动 → 影响live验证类gap
- 代码层连接/机制类gap → 可独立完成

**拆分**: 本轮清0 = 代码层gap (约18个) · 待用户环境 = live验证gap (约10个，标`needs_env`)

---

## 1. 执行Phase拆分

```
Phase 0 (校准): 修正gap评估 + 建gap-verify工具 + 建task-verify门禁
Phase B (数据流): 连接断裂3处 + 修stub + 场景补齐
Phase C (自主运行): Autoloop + Evolution + 可观测
Phase D (自主进化): Agent tick + Vision自评估 + Autopoiesis设计
Phase E (复盘+清零): 每阶段末复盘 + 最终清零率验证
```

---

## 2. Phase 0 — 校准与机制固化 (3 tasks)

### T0-1: 校准gap-registry (修正错误评估)
**问题**: EVO-05/GOV-01/META-02/META-03评估为"stub"但实际有逻辑
**改动**: 更新4个gap item文件，修正current_state/target_state
- `EVO-05-GOVERNOR-STUB.yaml` → current_state修正为"有journey timeout扫描"
- `META-03-EVOLUTION-ENGINE.yaml` → current_state修正为"有内部扫描，缺外部+调度+落地"
- `META-02-REFLECTION-SCHEDULER.yaml` → current_state修正为"有检测逻辑，缺调度"
- `EVO-02-EXTERNAL-SCRAPE.yaml` → current_state修正为"deep模式仅静态推荐"
**DoD**: 4个gap文件current_state准确反映代码现状

### T0-2: 新建 gap-verify 工具 (机制核心)
**问题**: 无法自动追踪gap状态
**方案**: 新建 `bin/ssot/gap-verify.py` (~120行)
- 扫 `.omo/debt/gap-items/*.yaml`
- 对每个gap检查: status字段 + evidence字段 + verification_cmd可执行性
- 输出: total / open / in_progress / resolved + 清零率
**改动**: `bin/ssot/gap-verify.py` (新建) + `Makefile` (+target `gap-verify`)
**DoD**: `make gap-verify` 输出清零率，能检测缺失evidence的gap

### T0-3: 新建 task-verify 门禁 (防虚假完成)
**问题**: task完成无验证机制 (上次教训根因)
**方案**: 新建 `bin/ssot/task-verify.py` (~100行)
- 扫所有task定义 (`.omo/_truth/registry/agent-workflows/` + gap-items)
- 对标记`completed`的task检查: evidence文件存在? verification_cmd可跑?
- 缺evidence → 降级为`unverified`，红灯
**改动**: `bin/ssot/task-verify.py` (新建) + Makefile + ADR (记录DoD标准)
**DoD**: `make task-verify` 能把无evidence的completed task标记为unverified

---

## 3. Phase B — 数据流连接 (核心)

### T-B1: signal-poller → MOS bridge (DATA-01, META-01)
**方案**: signal-poller检测到信号后，调用 `mos.service.MemoryOS().write(world_snapshot)` 写入认知
**改动**: `bin/ssot/signal-poller.py` (+bridge代码，复用mos.service)
**DoD**: 模拟信号 → MOS world_snapshot有记录 → `mos.recall('signal')` 返回非空

### T-B2: outcome → Trust Policy bridge (DATA-02, THEORY-01)
**方案**: scene-outcome-recorder记录后，自动调 `scenewatcher.evaluate_trust()` 更新calibration
**改动**: `bin/ssot/scene-outcome-recorder.py` (+MOS Bridge写入decision_outcome)
**DoD**: 记录1个outcome → capability_calibration变化 → 控制论反馈回路闭合

### T-B3: reflection → evolution trigger (DATA-03)
**方案**: scene-reflection产出后，检测异常模式 → 触发evolution-agent生成提案
**改动**: `bin/ssot/scene-reflection.py` (+触发钩子)
**DoD**: 1次reflection → 触发evolution-agent → 产出≥1提案

### T-B4: 修 KnowledgeCurator stub (EVO-04)
**方案**: 让tick()读decision_outcome → 构建知识图谱 → 跨scene关联
**改动**: `projects/omo/src/omo/omo_agent_host.py` (KnowledgeCuratorAgent.tick)
**DoD**: tick()写入≥1条知识关系到MOS，非noop

### T-B5: 扩展 GovernorAgent 扫描 (EVO-05)
**方案**: 保留journey timeout扫描 → 增加debt/trust趋势扫描
**改动**: `projects/omo/src/omo/omo_agent_host.py` (GovernorAgent.tick)
**DoD**: tick()产出含debt/trust趋势的治理发现

### T-B6: problem-detector 定期调度 (META-02)
**方案**: 复用现有检测逻辑 → 挂到cron/daemon tick
**改动**: `.omo/state/` 加cron配置 或 omo_agent_host注册
**DoD**: problem-detector被调度运行且产出≥1异常报告

### T-B7: scene-card → journey 补齐 (SCENE-01)
**方案**: 9个scene card → 补齐journey spec，使覆盖率从3/9→6/9
**改动**: `docs/journey-specs/` (+3个新spec)
**DoD**: `make journey-check` 通过，6个journey dry-run全通

---

## 4. Phase C — 自主运行

### T-C1: Autoloop Controller (EVO-01)
**方案**: 新建 `bin/ssot/autoloop-controller.py` (~200行)
- 定期扫debt/gap → 生成task → 执行 → 验证 → 关闭
- 守S1/S2门禁 (低风险自动执行，高风险报人)
**改动**: 新建 + Makefile
**DoD**: ≥1个debt自动转为task并执行，有完整证据链

### T-C2: Evolution Engine 外部抓取 (EVO-02, META-03)
**方案**: 扩展evolution-agent的scan_external → 真实WebSearch/RSS抓取
**改动**: `bin/ssot/evolution-agent.py` (scan_external重写 + 落地写文件)
**DoD**: 产出≥1份有真实外部来源引用的进化提案文件

### T-C3: signal-poller daemon化 (FACE-01)
**方案**: 提供`--daemon`模式或systemd/launchd服务文件
**改动**: `bin/ssot/signal-poller.py` + 服务配置
**DoD**: 服务持续运行，日志有周期poll记录

### T-C4: Mesh事件消费者 (FACE-05)
**方案**: 新建消费者，实时读events.jsonl tail → 处理(Trust更新/告警)
**改动**: 新建 `bin/ssot/mesh-consumer.py`
**DoD**: 事件产生→消费者实时处理→产出动作

### T-C5: predictive-governance 引擎 (GOV-01)
**方案**: 实现引擎读metrics → 匹配trigger → 执行推荐动作
**改动**: 新建 `bin/ssot/predictive-governance.py`
**DoD**: 产出≥1条推荐动作

### T-C6: 模型驱动约束 (GOV-03)
**方案**: Risk Gate/权限阈值从hardcode → governance-checks.yaml读取
**改动**: `bin/ssot/risk-gate.py` + `permission-matrix.py`
**DoD**: 修改yaml配置→约束行为变化 (无需改代码)

### T-C7: 实时dashboard (OBS-01)
**方案**: dashboard.py → 定时刷新 + 实时数据源
**改动**: `bin/ssot/dashboard.py`
**DoD**: dashboard展示<30s延迟的agent/journey状态

### T-C8: 主动告警 (OBS-02)
**方案**: 异常检测 → 告警通知 (日志/文件/message)
**改动**: 新建 `bin/ssot/alert-handler.py`
**DoD**: ≥1次异常触发告警

---

## 5. Phase D — 自主进化 (规划/设计类)

### T-D1: Agent自主tick daemon (AGENT-01)
**方案**: 设计+实现daemon进程，AgentHost持续tick
**DoD**: daemon运行≥1h，agent tick≥10次，有日志

### T-D2: Vision自评估 (EVO-03)
**方案**: 定期比对vision vs 现状 → 产出gap分析
**改动**: 新建 `bin/ssot/vision-audit.py`
**DoD**: 产出≥1份vision-gap分析

### T-D3: 自适应规则 (GOV-02)
**方案**: 审计required规则违规历史 → 无违规自动建议降级
**改动**: 新建 `bin/ssot/rule-adapt.py`
**DoD**: 产出≥1条规则调整建议

### T-D4: Autopoiesis设计 (META-04)
**方案**: 设计文档 — 架构自修改的机制/门禁/回滚
**改动**: `.omo/_knowledge/designs/autopoiesis-design.md`
**DoD**: 设计文档完成，评审通过

---

## 6. 执行顺序与依赖

```
Phase 0 → 建工具+校准 (T0-1/2/3)
   ↓
Phase B → 数据流 (T-B1..B7)  ← 独立于C
   ↓
Phase C → 自主运行 (T-C1..C8) ← 依赖B(数据流通)
   ↓
Phase D → 自主进化 (T-D1..D4) ← 依赖C
   ↓
Phase E → 复盘 + 清零验证
```

**可并行**: Phase 0的T0-1/2/3 · Phase B内部多个bridge
**依赖**: C依赖B · D依赖C · 不能乱序

---

## 7. 验证与复盘节奏

### 每Phase末复盘
| 阶段 | 复盘时机 | 检查点 |
|------|---------|--------|
| Phase 0 | T0完成后 | gap-verify/task-verify工具工作 |
| Phase B | 数据流通后 | 3处断裂是否闭合 |
| Phase C | Autoloop跑通 | 自主运行是否成立 |
| Phase D | 设计评审 | 自主进化是否可行 |

### 最终验证
```bash
make gap-verify          # 清零率
make task-verify         # 无虚假完成
make journey-check       # journey spec有效
make gac-local-gate      # 治理门禁
```

### 复盘文档
- 每阶段末写 `.omo/_knowledge/retros/GAP-PHASE-{X}-RETRO.md`
- 记录: 完成项/未完成项/根因/改进

---

## 8. 待用户环境 (本轮无法自动完成，标needs_env)

| gap | 依赖 |
|-----|------|
| FACE-03-SPINE-LIVE (live运行) | KOS/iris在线 |
| FACE-02-COGNITION-MOS-DATA (真实数据) | 需live journey |
| FACE-04-REFLECTION-OUTCOME (真实outcome) | 需live journey |
| META-01 (真实信号→MOS) | 需iris信号源 |
| SCENE-02 (领域场景) | 需产品决策 |

这些在用户启动运行时环境后，作为"live验证周"执行。

---

## 9. 文件清单

**新建**:
- `bin/ssot/gap-verify.py`
- `bin/ssot/task-verify.py`
- `bin/ssot/autoloop-controller.py`
- `bin/ssot/mesh-consumer.py`
- `bin/ssot/predictive-governance.py`
- `bin/ssot/alert-handler.py`
- `bin/ssot/vision-audit.py`
- `bin/ssot/rule-adapt.py`
- `docs/journey-specs/*.yaml` (3个新)
- `.omo/_knowledge/designs/autopoiesis-design.md`

**修改**:
- `bin/ssot/signal-poller.py` (MOS bridge + daemon)
- `bin/ssot/scene-outcome-recorder.py` (Trust bridge)
- `bin/ssot/scene-reflection.py` (evolution trigger)
- `bin/ssot/evolution-agent.py` (外部抓取+落地)
- `bin/ssot/dashboard.py` (实时)
- `bin/ssot/risk-gate.py` + `permission-matrix.py` (模型驱动)
- `projects/omo/src/omo/omo_agent_host.py` (KnowledgeCurator + Governor)
- `.omo/debt/gap-items/*.yaml` (4个校准)
- `Makefile` (gap-verify/task-verify target)

**SSOT更新**:
- `.omo/debt/gap-registry.yaml` (状态跟踪)
- ADR: DoD标准记录
