---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-26
last_updated: 2026-08-26
bet_id: BET-Y1Q3-T7-02
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Health Domain P1 Design — 健康域最小契约闭环

- spec_version: 1.0.0
- date: 2026-08-26
- bet: BET-Y1Q3-T7-02
- track: T7-SCENE
- status: accepted (用户 2026-08-26 面授授权)

## 1. 背景与问题

健康域 (health) 当前为零资产: docs/scene-cards/ 与 docs/journey-specs/ 无任何 health
条目, 全库仅 risk_engine DOMAIN_OVERRIDES 预留一条 health 分级
(`generate:report=L0`, `send_email:doctor=L2`), 协作标准
(.omo/standards/agent-cli-worker-collaboration.md) 将 health domains 列入受限敏感域
(与 WeChat/NAS/高自主触发同列)。

需求: 把健康域从零资产推进到最小契约闭环 — 先落场景卡与 journey spec (draft),
运行时实现留 P2。复用 admin 域已验证的 v3 flat schema 模式。

## 2. 范围 (P1)

1. journey spec: `docs/journey-specs/health-medical-workflow.yaml` (journey-spec/v1,
   flat transitions, 4 状态分叉结构)
2. 场景卡 x4: `docs/scene-cards/health-{intake,visit-prep,visit,archive}.yaml`
   (scene-card/v2, 全部 status: draft — 场景准入先于实现)

## 3. Journey 状态机

```
recorded (health-intake)
   ├─ needs_doctor_visit == true ──▶ prepared (health-visit-prep)
   │                                    │ visit_completed == true
   │                                    ▼
   │                                 visited (health-visit)
   │                                    │ records_received == true
   │                                    ▼
   └─ needs_doctor_visit == false ──▶ archived (health-archive) [terminal]
```

- recorded: 症状/指标/医嘱结构化记录
- prepared: 就诊准备包 (症状时间线 + 历史摘要 + 问题清单)
- visited: 就诊结果记录 (诊断/处方/医嘱)
- archived: 报告归档 + 复查/用药节点提取 (挂 deadline-tracker 属 P2, 卡片先声明)

## 4. 风险与数据分级 (硬边界)

| 动作 | 分级 | 依据 |
|------|------|------|
| 记录/归档/报告生成 | L0 自动 | risk_engine health.generate:report=L0 |
| 对医生/医院外发 (邮件等) | L2 强 HITL | risk_engine health.send_email:doctor=L2 |

- 场景卡 data_classification: confidential (全库最敏感个人数据, 高于 admin 的 internal)
- 协作标准敏感域约束: 不接自动采集源, 不外发未经人审内容

## 5. Non-goals

- 场景卡运行时实现 (bin/ssot/health_*.py) — P2
- 健康数据自动采集源接入 (穿戴设备/体检 API) — P2+
- mail-agent 新增健康类目 (无邮件触发源, YAGNI)
- deadline-tracker 健康节点挂载 — P2

## 6. Done-when

1. `make journey-check` 对 health-medical-workflow 通过
2. `make scene-card-check` 对 4 张 health 卡通过
3. 每张卡显式声明 L0/L2 风险边界与 confidential 数据分级

## 7. Verify

```bash
make journey-check
make scene-card-check
```

## 8. 参考

- 模板: docs/journey-specs/admin-notification-workflow.yaml (v3 flat schema)
- 卡片模板: docs/scene-cards/admin-inbox.yaml (scene-card/v2)
- 风险预留: bin/ssot/risk_engine.py DOMAIN_OVERRIDES.health
- 敏感域约束: .omo/standards/agent-cli-worker-collaboration.md
