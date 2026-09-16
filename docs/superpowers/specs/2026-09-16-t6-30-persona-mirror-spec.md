---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
bet_id: BET-Y1Q4-T6-30
decision_ref: decision://accepted/BET-Y1Q4-T6-30
track: T6-EVOLUTION
priority: P2
risk_level: L2
window: Y1Q4
owner: engineering-agent
created: 2026-09-16
last-reviewed: 2026-09-16
---

# BET-Y1Q4-T6-30: 夏明星数字化 Persona 心智镜像微调与主权分身共生体系

## 1. Problem

当前 omostation 多 agent 协作中，agent 缺乏对夏明星（创始人）决策偏好、表达风格、价值判断的
结构化感知。导致：

- Agent 输出风格与创始人不一致，需要反复修改
- 决策建议未对齐创始人认知框架，置信度低
- 无法在创始人离线时提供"近似创始人视角"的辅助判断

## 2. Goal

构建一个**本地主权**的数字化 Persona 心智镜像系统，通过：

1. 从夏明星历史修改 diff 中提取决策模式（extract-persona-diffs）
2. 训练轻量对齐模型/规则引擎（persona_trainer）
3. 提供对齐度校验门禁（>= 0.90）
4. 敏感数据清洗门禁（circuit_breaker）

实现 agent 输出与创始人风格对齐度 >= 0.90，同时确保零敏感数据出域。

## 3. Out of Scope (non_goals)

- ❌ 不将夏明星个人修改与敏感偏好数据上传至外部公有云
- ❌ 不在未达到对齐度门禁（>= 0.90）前对外启用代行权限
- ❌ 不替代创始人最终决策权（仅辅助）
- ❌ 不在清醒相执行大算力耗时图谱蒸馏

## 4. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Persona Mirror System                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │  Diff Extract │───▶│  Circuit     │───▶│  Persona   │ │
│  │  (local git)  │    │  Breaker     │    │  Trainer   │ │
│  │              │    │  (sanitize)  │    │  (align)   │ │
│  └──────────────┘    └──────────────┘    └────────────┘ │
│        │                                        │        │
│        ▼                                        ▼        │
│  ┌──────────────┐                      ┌────────────┐   │
│  │  Raw Diffs   │                      │  Alignment │   │
│  │  (local)     │                      │  Score     │   │
│  └──────────────┘                      │  (>= 0.90) │   │
│                                        └────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 4.1 Circuit Breaker — 敏感数据清洗门禁

在 diff 进入 trainer 前，强制经过 circuit_breaker 清洗：

| 类别 | 规则 | 动作 |
|------|------|------|
| API Key / Token | 正则匹配 `[a-zA-Z0-9]{32,}` | 替换为 `<REDACTED_SECRET>` |
| Email | 邮箱正则 | 替换为 `<REDACTED_EMAIL>` |
| Phone | 手机号正则 | 替换为 `<REDACTED_PHONE>` |
| 个人偏好关键词 | 匹配偏好配置文件中的关键词 | 替换为 `<REDACTED_PREFERENCE>` |
| 文件路径中的用户名 | `/Users/<username>/` | 替换 with `<REDACTED_PATH>` |

### 4.2 Alignment Score — 对齐度校验

对齐度计算维度（加权平均）：

| 维度 | 权重 | 计算方式 |
|------|------|----------|
| 表达风格 | 0.30 | 句式长度分布 + 标点使用频率 |
| 决策模式 | 0.25 | 修改类型比例（add/delete/modify） |
| 价值偏好 | 0.25 | 关键词频率分布 |
| 技术栈偏好 | 0.20 | 技术选型一致性 |

门禁：加权得分 < 0.90 时，拒绝输出并告警。

## 5. Implementation Plan

### Phase 1: Diff Extraction (extract-persona-diffs.py)

- 解析 git log 中夏明星的 commit diff
- 提取修改模式（文件类型、修改类型、时间分布）
- 输出结构化 JSON

### Phase 2: Circuit Breaker (内置)

- 实现敏感数据检测与清洗
- 可配置规则集
- 审计日志

### Phase 3: Persona Trainer (persona_trainer.py)

- 加载清洗后的 diffs
- 计算 persona 特征向量
- 提供对齐度评分 API

### Phase 4: Gate Integration

- 对齐度门禁 CLI 接口
- 与 agent-workflow 集成

## 6. Verification

```bash
# 工具可用性
python3 bin/evolution/extract-persona-diffs.py --help
# expect: exit 0

# 对齐度门禁
python3 bin/evolution/persona_trainer.py --gate-check
# expect: exit 0 (when alignment >= 0.90)

# 台账一致性
python3 bin/plan/bet-ledger.py lint
# expect: exit 0
```

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 敏感数据泄露 | Low | Critical | circuit_breaker 强制清洗 + 本地处理 |
| 对齐度不足 | Medium | High | 门禁拦截 + 持续迭代 |
| 过度拟合个人风格 | Low | Medium | 保留多样性阈值 |
| 性能开销 | Low | Low | 增量处理 + 缓存 |

## 8. Dependencies

- T6-29 (done): 仿生清醒-睡眠双相记忆巩固 — 提供夜间蒸馏基础设施
- T8-23 (done): 风险-置信度矩阵自适应授权 — 提供授权门禁模式参考
