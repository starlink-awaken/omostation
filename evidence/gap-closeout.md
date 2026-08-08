# Gap 清零证据包 — Phase 0-4 实施

> 创建: 2026-08-08 | 验证: task-verify + gap-verify
> 原则: 每个 resolved gap 必须有可执行证据

## 本轮实施证据 (恢复后)

| Gap | 证据 | 验证命令 |
|-----|------|---------|
| META-01 | signal-poller 检测信号→写入 MOS world_snapshot | signal-poller.py --auto-trigger |
| META-02 | problem-detector --once 写 last-run + launchd plist | problem-detector.py --once |
| META-03 | evolution-agent 真实抓取 HN RSS + 提案落文件 | evolution-agent.py --deep |
| FACE-01 | signal-poller launchd plist (KeepAlive) | plutil -lint plist |
| FACE-02 | MOS 三表有真实数据 (ws+do+beliefs+cc) | trust-adjuster --show |
| FACE-04 | outcome 记录 + MOS decision_outcome | scene-outcome-recorder.py record |
| FACE-05 | mesh-consumer 消费事件 + trace | mesh-consumer.py --once |
| EVO-01 | autoloop 扫描 33 项, 分级处理 | autoloop-controller.py --dry-run |
| EVO-02 | evolution-agent 真实抓取 HN | evolution-agent.py --deep --json |
| EVO-03 | vision-audit 产出 pillars + bet 进度 | vision-audit.py |
| EVO-04 | KnowledgeCurator tick→learn, 写入 belief | agent-tick-daemon.py --once |
| EVO-05 | Governor tick 产出 high_debt_volume finding + dispatch | agent-tick-daemon.py --once |
| OBS-01 | dashboard --watch + --auto-reload | dashboard.py --auto-reload |
| OBS-02 | alert-handler 触发 2 条告警 | alert-handler.py --once |
| GOV-01 | predictive-governance 基于 138 metrics 产出推荐 | predictive-governance.py |
| GOV-02 | rule-adapt 产出 24 条降级建议 | rule-adapt.py |
| GOV-03 | constraint-gate 从 SSOT 读约束, gate 判定 | constraint-gate.py gate |
| DATA-01 | signal→MOS bridge | signal-poller.py --auto-trigger |
| DATA-02 | outcome→MOS decision_outcome + calibration | scene-outcome-recorder.py record |
| DATA-03 | reflection→evolution trigger | scene-reflection.py generate |
| THEORY-01 | outcome→MOS→Trust 反馈闭环 | trust-adjuster --show |
| AGENT-01 | agent-tick-daemon 6 agent 全 ok | agent-tick-daemon.py --once |
| SCENE-01 | 6/9 journey dry-run 全通 | make journey-check |
| MECH-01 | verify.py + gap-verify 工具 | verify.py --mode all |
