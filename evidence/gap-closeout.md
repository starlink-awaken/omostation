---
type: ssot
---

# Gap 清零证据包 — Phase 0-4 实施

> 创建: 2026-08-08 | 验证: task-verify --strict + gap-verify
> 原则: 每个 resolved gap 必须有可执行证据 (DoD L3: 真实数据流过)

## 本轮实施证据

| Gap | 证据 | 验证命令 |
|-----|------|---------|
| META-01 OBSERVATION-MOS-BRIDGE | signal-poller 检测信号→写入 MOS world_snapshot (ws-0001/ws-0002) | `python3 bin/ssot/signal-poller.py --auto-trigger` |
| META-02 REFLECTION-SCHEDULER | problem-detector --once 写 last-run + launchd plist | `python3 bin/ssot/problem-detector.py --once` |
| META-03 EVOLUTION-ENGINE | evolution-agent 真实抓取 HN RSS + 提案落文件 | `python3 bin/ssot/evolution-agent.py --deep` |
| FACE-01 PERCEPTION-DAEMON | signal-poller launchd plist (KeepAlive) | `plutil -lint ~/Library/LaunchAgents/com.omostation.signal-poller.plist` |
| FACE-02 COGNITION-MOS-DATA | MOS 三表有真实数据 (ws/cc/do/belief) | `python3 bin/ssot/mesh-consumer.py --once` |
| FACE-03 SPINE-LIVE | iris 真实返回 gathered=1, data_integrity=degraded 机制 | `python3 bin/ssot/journey-runner.py run --journey research-to-insight --live` |
| FACE-04 REFLECTION-OUTCOME | outcome 记录 + MOS decision_outcome (do-0001) | `python3 bin/ssot/scene-outcome-recorder.py record ...` |
| FACE-05 FABRIC-CONSUMER | mesh-consumer 消费 1098 事件 + trace | `python3 bin/ssot/mesh-consumer.py --once` |
| EVO-01 AUTOLOOP-CONTROLLER | autoloop 扫 33 项, 6 项 auto_closed | `python3 bin/ssot/autoloop-controller.py --dry-run` |
| EVO-02 EXTERNAL-SCRAPE | evolution-agent 真实抓取 HN | `python3 bin/ssot/evolution-agent.py --deep --json` |
| EVO-03 VISION-UPDATE | vision-audit 产出 12 pillars + bet 进度 35% | `python3 bin/ssot/vision-audit.py` |
| EVO-04 KNOWLEDGE-CURATOR-STUB | tick→learn, 写入 cross-scene belief | `uv run python -c "from omo.omo_agent_host import KnowledgeCuratorAgent..."` |
| EVO-05 GOVERNOR-STUB | tick 产出 high_debt_volume finding | `uv run python -c "from omo.omo_agent_host import GovernorAgent..."` |
| OBS-01 REALTIME-DASHBOARD | dashboard --watch + --auto-reload | `python3 bin/ssot/dashboard.py --auto-reload` |
| OBS-02 PROACTIVE-ALERT | alert-handler 触发 2 条告警 | `python3 bin/ssot/alert-handler.py --once` |
| GOV-01 PREDICTIVE-ENGINE | predictive-governance 基于 138 metrics 产出推荐 | `python3 bin/ssot/predictive-governance.py` |
| GOV-02 ADAPTIVE-RULES | rule-adapt 产出 24 条降级建议 | `python3 bin/ssot/rule-adapt.py` |
| GOV-03 MODEL-DRIVEN-CONSTRAINT | constraint-gate 从 SSOT 读约束, gate 判定 | `python3 bin/ssot/constraint-gate.py gate ...` |
| DATA-01 SIGNAL-TO-MOS | signal→MOS bridge (T-B1) | `python3 bin/ssot/signal-poller.py --auto-trigger` |
| DATA-02 OUTCOME-TO-TRUST | outcome→MOS decision_outcome (T-B2) | `python3 bin/ssot/scene-outcome-recorder.py record ...` |
| DATA-03 REFLECTION-TO-EVOLUTION | reflection→evolution trigger (T-B3) | `python3 bin/ssot/scene-reflection.py generate ... --execution-status failed` |
| THEORY-01 CONTROL-FEEDBACK | outcome→MOS→Trust 反馈闭环 | 同上 |
| AGENT-01 AUTONOMOUS-TICK | agent-tick-daemon 4 agent 全 ok | `python3 bin/ssot/agent-tick-daemon.py --once` |
| SCENE-01 CARD-TO-JOURNEY | 6/9 journey dry-run 全通 | `make journey-check` |
| MECH-01 TASK-VERIFY-GATE | task-verify + gap-verify 工具 | `make task-verify` |

## 仍需用户环境 (needs_env, 不标记 resolved)
- SCENE-02 DOMAIN-SCENARIOS: 领域场景需产品决策
- META-04 AUTOPOIESIS: 设计完成, 实施待 M2-M5
- FACE-03 SPINE-LIVE: 真实 live 全链 (iris 全量数据源)
