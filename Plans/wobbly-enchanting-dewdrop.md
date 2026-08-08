# Agent生态体系 — P4-P6全面落地方案

> 更新: 2026-08-08 | P1-P3已完成 ✅ | 覆盖P4(A2A)+P5(PI)+P6(协作)
> 原则: 复用现有基建 + 本体驱动 + 每Phase验证+复盘

---

## 0. Context

P1-P3已落地并验证:
- ✅ P1: 5个Agent本体yaml + gen-agent-constraints.py + SHACL验证
- ✅ P2: MOS记忆扩展(record_skill/record_experience/forget_expired/update_memory)
- ✅ P3: AutonomyAssessmentAgent(自主度82/100, 5维度, 6 agents全ok)

本plan覆盖P4-P6剩余3个Phase。

每Phase必须:
1. 实施代码
2. 验证(运行时证据, 非dry-run)
3. 架构审议(本体一致性 + 约束验证)
4. 复盘文档(`.omo/_knowledge/retros/AGENT-PHASE-{X}-RETRO.md`)
5. 可观测性检查(日志+指标+告警)

---

## P2: MOS记忆扩展 (技能库+经验库+遗忘)

### P2-T1: 技能库
**改动**: `projects/omo/src/omo/omo_belief.py` (+record_skill方法 ~20行)
**DoD**: agent tick后能记录1条可复用技能到MOS
**复用**: MOSBeliefManager的_load_state/_persist_state

### P2-T2: 经验库
**改动**: `projects/omo/src/omo/omo_belief.py` (+record_experience方法 ~20行)
**DoD**: outcome记录后自动产出经验条目

### P2-T3: 遗忘机制
**改动**: `projects/omo/src/omo/omo_belief.py` (+forget_expired方法 ~25行)
**DoD**: 超过TTL的记忆被标记archived
**参考**: SAGE的Ebbinghaus遗忘曲线

### P2-T4: 记忆操作(Mem0模式)
**改动**: `projects/omo/src/omo/omo_belief.py` (+update_memory方法 ~30行)
**DoD**: ADD/MERGE/UPDATE/DELETE四种操作可用

### P2验证
```bash
python3 -c "
import sys; sys.path.insert(0,'projects/omo/src')
from omo.omo_belief import MOSBeliefManager
from pathlib import Path
m = MOSBeliefManager(root=Path('.'))
m.record_skill('advisor', 'telos_alignment_check', 'code...', 'test')
m.record_experience('governor', 'debt_volume_alert', 'positive')
m.forget_expired(max_age_days=365)
print('skills:', len(m._load_state().get('agent_skills',[])))
print('experiences:', len(m._load_state().get('agent_experiences',[])))
"
```

---

## P3: AutonomyAssessmentAgent (5维度评估)

### P3-T1: 评估Agent类
**改动**: `projects/omo/src/omo/omo_agent_host.py` (+AutonomyAssessmentAgent ~80行)
**维度**: Adaptivity(学习曲线) / Retention(遗忘率) / Generalization(跨域) / Efficiency(资源) / Safety(合规)
**DoD**: tick产出0-100自主度评分

### P3-T2: 评估指标采集器
**改动**: `bin/ssot/collect-metrics.py` (新建 ~60行)
**数据源**: MOS四表 + verify.py + agent-tick-daemon + metrics-store
**DoD**: 采集5维度指标并写入metrics-store

### P3-T3: 评估框架SSOT
**改动**: `.omo/_truth/registry/autonomy-metrics.yaml` (新建)
**内容**: 5维度指标定义 + 权重 + 阈值
**DoD**: gen-agent-constraints.py能读取指标定义

### P3验证
```bash
python3 bin/ssot/agent-tick-daemon.py --once  # 6 agents含Assessment
# Assessment输出: autonomy_score=XX, dimensions={adaptivity:XX,...}
```

---

## P4: A2A适配器 (agora BOS扩展)

### P4-T1: BOS路由扩展
**改动**: `projects/agora/etc/bos-services.yaml` (+a2a://路由条目)
**路由**: a2a://message/send, a2a://task/delegate, a2a://agent/discover
**DoD**: agora能路由A2A消息

### P4-T2: Agent Card生成
**改动**: `bin/ssot/gen-agent-constraints.py` (已有gen_agent_cards, 扩展输出)
**格式**: JSON-LD Agent Card (A2A标准)
**DoD**: Agent Card写入`.omo/state/agent-cards/`供发现

### P4-T3: 异构agent适配器
**改动**: `bin/ssot/a2a-adapter.py` (新建 ~100行)
**适配**: Claude Code(MCP→BOS), Claude Desktop(SSE→BOS), 龙虾(HTTP→BOS)
**DoD**: 至少1种外部agent能通过A2A发现omo agent

### P4验证
```bash
python3 bin/ssot/gen-agent-constraints.py --json | jq '.agent_cards[0]'
# Agent Card: id, name, capabilities, bos_uri (A2A发现)
```

---

## P5: PI集成 (深判引擎)

### P5-T1: PI适配器
**改动**: `bin/ssot/pi-adapter.py` (新建 ~80行)
**功能**: omo agent调用PI做LLM深判
**DoD**: Advisor agent能通过PI适配器做复杂判断

### P5-T2: Agent tick里的LLM调用
**改动**: `projects/omo/src/omo/omo_agent_host.py` (AdvisorAgent扩展 ~20行)
**逻辑**: 规则confidence < 0.8时调PI深判
**DoD**: 规则+LLM混合判断工作

### P5-T3: 学习反馈
**改动**: `bin/ssot/trust-adjuster.py` (扩展 +adjust_rules方法 ~30行)
**逻辑**: Trust反馈→调整agent的规则阈值
**DoD**: 规则阈值随Trust数据动态调整

### P5验证
```bash
# 规则判断confidence不足时触发PI深判
python3 bin/ssot/agent-tick-daemon.py --once
# Advisor输出含"deep_eval"字段
```

### P5备注
PI集成依赖PI SDK接口。如果PI不可用，退化为纯规则判断(当前状态)。

---

## P6: 多agent协作 (Governor调度+消息)

### P6-T1: Governor调度扩展
**改动**: `projects/omo/src/omo/omo_agent_host.py` (GovernorAgent +dispatch_task ~40行)
**逻辑**: Governor发现finding→匹配agent能力→分发任务
**DoD**: Governor能向其他agent发送任务

### P6-T2: Agent间消息
**改动**: `bin/ssot/agent-message.py` (新建 ~60行)
**功能**: agent间消息发送/接收(基于文件队列, 复用jsonl)
**DoD**: 2个agent能互相发消息

### P6-T3: 互相评价
**改动**: `bin/ssot/pr-review-matrix.py` (扩展 +peer_review ~30行)
**逻辑**: agent审查其他agent的tick输出→评价质量→反馈到Trust
**DoD**: agent间能互相评价

### P6验证
```bash
# Governor发现debt_volume→向advisor发送评估任务
python3 bin/ssot/agent-tick-daemon.py --once
# Governor输出含"dispatched_to": ["advisor"]
```

---

## 架构审议与复盘节奏

### 每Phase末
1. **本体一致性**: `python3 bin/ssot/gen-agent-constraints.py --validate`
2. **约束验证**: `python3 bin/ssot/verify.py --mode all`
3. **Agent tick**: `python3 bin/ssot/agent-tick-daemon.py --once`
4. **复盘文档**: `.omo/_knowledge/retros/AGENT-PHASE-{X}-RETRO.md`

### 可观测性检查点
- 日志: `agent-tick-daemon.jsonl`心跳
- 指标: `metrics-store.jsonl`
- 告警: `alerts.jsonl`
- 面板: `dashboard.py --auto-reload`
- MOS: 四表计数(应有技能库/经验库)

---

## 执行顺序

```
P2(记忆扩展) → P3(评估Agent) → P4(A2A) → P5(PI) → P6(协作)
```

P2是基础（记忆层是所有agent的共享基础设施）。
P3依赖P2（评估需要读取记忆数据）。
P4依赖P1（Agent Card从本体生成）。
P5可独立（PI适配器）。
P6依赖P4（协作需要A2A通信）。

---

## 文件清单

**新建**:
- `bin/ssot/collect-metrics.py` (P3)
- `.omo/_truth/registry/autonomy-metrics.yaml` (P3)
- `bin/ssot/a2a-adapter.py` (P4)
- `bin/ssot/pi-adapter.py` (P5)
- `bin/ssot/agent-message.py` (P6)

**修改**:
- `projects/omo/src/omo/omo_belief.py` (P2: +技能库/经验库/遗忘/Mem0)
- `projects/omo/src/omo/omo_agent_host.py` (P3: +AssessmentAgent, P5: +LLM, P6: +dispatch)
- `projects/agora/etc/bos-services.yaml` (P4: +a2a路由)
- `bin/ssot/gen-agent-constraints.py` (P4: +Agent Card输出)
- `bin/ssot/trust-adjuster.py` (P5: +规则调整)
- `bin/ssot/pr-review-matrix.py` (P6: +peer_review)
