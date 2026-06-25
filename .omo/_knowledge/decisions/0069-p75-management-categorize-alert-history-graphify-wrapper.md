---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0069: P75 management 142 分类 + alert-history 多维深化 + graphify 重生 wrapper

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P75
- **Extends**: ADR-0068 (P74 事件驱动 + percentile + 多维)
- **Superseded by**: (无)

## Context and Problem Statement

P74 收口后, P75 调研 4 项候选, 实施 3 项:

1. **management/ 142 实施拆分** (P71 评估 60% 中等, P75 优先 — 沿用 P53 双指针)
2. **alert-history 加更多维度** (P74 3 维 → P75 5 维: by_hour_detail + by_type_by_level)
3. **graphify 重生 wrapper** (P29 旧 graph 133 files, 需 OPENAI_API_KEY)

跳过 1 项:
- P0 listener 实时 API (P76+ 评估)

## Decision

### D1: management 142 frontmatter 分类 (P75 R1)

**新工具**: `bin/management-categorize.py` (90 行)

**策略**:
- 不物理迁移 144 文件 (P53 双指针)
- 仅加 frontmatter `category` 字段
- 基于文件名+note 自动分类

**3 类目**:
| 类目 | 关键词 | 数量 |
|------|--------|------:|
| `workflows/` | audit / closeout / hardening / playbook / migration / phase / final-state | 127 |
| `playbooks/` | append-only-log / schemas / ssot / manifest | 5 |
| `guides/` | architecture / explainer / analysis / deep | 12 |

**实测**: 144 文件 → 127/5/12 分类 ✅

**未来扩展**:
- `mograte management/*.md --category workflows/` (P76+)
- 物理迁移 (沿 P53 双指针)

### D2: alert-history 多维深化 (P75 R2)

**新增 2 维度**:
- `by_hour_detail`: 全小时桶, 24h 分布
- `by_type_by_level`: 按类型按级别交叉

**沿 P74 持续深化**: 7 维 → 9 维

**实测**: 4 天 P1 数据 → 9 维度完整输出

### D3: graphify 重生 wrapper (P75 R3)

**新工具**: `bin/graphify-local-extract.py` (90 行)

**策略**:
- 检测 OPENAI_API_KEY 配置
- 如有, 调 graphify 0.8.46 `extract` 命令扫描 .omo/_knowledge/management/
- 如无, 提示配置方法 + 留 P76+ 评估 API 成本

**实测**: 无 API key → 提示配置, 不报错

**vs P29 旧 graph**:
- 旧: 133 files (2026-06-03, P29 时期)
- 新: 144 management files (P75 候选)
- 差异: +8% (P31-P74 新增 management)

## Consequences

### Positive

- **management 142 分类**: frontmatter 字段, 不物理迁移
- **alert-history 9 维**: 按级别+时间+类型+小时+高峰 5 个角度
- **graphify wrapper**: 0.8.46 工具就绪, 待 API 配置

### Negative

- **management 实际迁移未做**: 144 文件仍在原位
- **graphify 实际扫描未跑**: 需 OPENAI_API_KEY

### Neutral

- **不增 linter 维度**: 沿用 P58 独立 bin 工具
- **不增 mof-drift 维度**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P74 末 | **P75 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.63 | **v0.0.64** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 13 | **15** | +2 (management-categorize + graphify-local-extract) |
| management 分类 | 0 | **144** | +144 (category 字段) |
| alert-history 维度 | 10 | **12** | +2 (by_hour_detail + by_type_by_level) |
| ADR 数量 | 28 | **29** | +1 (0069) |

### 关联 ADR

- **ADR-0068**: P74 事件驱动 + percentile + 多维 (P75 直接扩展)
- **ADR-0064**: P70 跨级别 + rich (alert-history 沿用)
- **ADR-0053**: doc-lifecycle 4 类 (management category 沿用)

### 关联 L0 规则

- `X2-FRESH-DOC-LIFECYCLE` — 7 天保鲜 + frontmatter 字段
- `CR-GOV-CLOSED-LOOP-01` — graphify 写日志即 commit

## Notes

本 ADR 记录 P75 3 项候选实施:
- ✅ management 142 分类 (新工具, 沿 P53 双指针)
- ✅ alert-history 多维深化 (12 维)
- ✅ graphify 重生 wrapper (0.8.46 extract 集成)
- ⏸ P0 listener 实时 API (P76+)

后续 P76+ 候选:
- management 物理迁移 (沿 P53 双指针, 分类后迁移)
- P0 listener 实时事件 API (替代轮询)
- graphify 实际扫描 (需 OPENAI_API_KEY 配)
- alert-history 加更多维度 (自动洞察 + 高峰日预测)
- 自治治理代理 cron 完整安装
- 跨子仓联动 (ecos / agora / cockpit)

---

*最后更新: 2026-06-23 · P75 · omostation 治理方法论持续深化*