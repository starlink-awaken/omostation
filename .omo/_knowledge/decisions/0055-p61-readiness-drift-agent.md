---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0055: P61 readiness 评分修复 + mof-drift v6 增量 + 自治治理代理

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P61
- **Extends**: ADR-0054 (P60 治理方法论内化)
- **Superseded by**: (无)

## Context and Problem Statement

P60 内化后立即发现 2 个 P61 必须修复的问题:

1. **readiness 维度 5 解析失败** — `omo governance` 在 subprocess 下 120s+ 超时
   (omo_audit + lint + health 全跑), 评分始终 0/15
2. **mof-drift 缺 commit_closure 维度** — P60 新增 L0 规则 CR-GOV-COMMIT-FREQUENCY-01
   缺乏机器可见的检测信号
3. **mof-drift 缺 governance 趋势维度** — governance-history.jsonl 有 1942 条审计历史,
   但无趋势分析, 无法反映 P43-P60 治理提升的积累
4. **无自治代理骨架** — 治理方法论需 cron 自动化

## Decision

### D1: readiness 维度 5 改读 health.yaml (P61 R1)

**原因**: `omo governance` subprocess 120s+ 超时 (omo_audit 完整跑), 无法用于实时评分。

**修复**: 改读 `.omo/state/health.yaml` 的 `health_score` 字段 (最近一次 omo governance 评估的 SSOT 产物)。

**结果**: readiness 评分从 80/100 升到 **95/100 (A+ L4 稳态治理)**。

### D2: mof-drift v6 — commit_closure 维度 (P61 R2)

**新增函数**: `count_commit_closure() -> (uncommitted, bumps_24h, last_age_h)`

**触发规则**:
| 工作树累积 | Severity |
|-----------|----------|
| > 500 | high (error) |
| > 100 | medium (warn) |
| > 0 | low (信息) |

**实测**: P61 自身 36 文件 → low (健康)

### D3: mof-drift v6 — governance_score_history 维度 (P61 R3)

**新增函数**: `analyze_governance_history(window=20)`

**逻辑**: 比较最近 20 次 audit 与前 20 次的 mean(total_score)
- 下降 > 1.0 → medium (declining)
- recent_avg ≥ 99 + prev_avg < 99 → low (稳态)

**实测**: 1942 条历史, P43-P60 持续提升, 当前 100 稳态

### D4: 自治治理代理骨架 (P61 R3)

**文件**:
- `scripts/omo/governance-agent.sh` — 主代理 (readiness + drift + 信号告警)
- `.omo/cron/governance-agent-crontab` — cron 配置 (每 6h)

**功能**:
1. 跑 `bin/gac/governance-readiness.py` 评估
2. 跑 `bin/mof-drift` 跨 7 维度
3. 解析结果, < 90 或 MEDIUM/HIGH 触发告警
4. (扩展) omo event emit governance_alert (P62+ 完整实施)

**实测**: 90/100 + LOW=1 → 退出码 0 (健康)

## Consequences

### Positive

- **readiness 95/100 真实反映** — 修复前 0/15 假阴性, 修复后 15/15 满分
- **mof-drift 7 维度全覆盖** — 6 (P52) + 1 (commit_closure) + 1 (governance_score_history) = 7+ 维度
- **自治代理骨架就绪** — cron 启用后真正实现 P61 自治治理

### Negative

- **readiness 改读 health.yaml** — 与 omo governance 实时性下降 (5min~1h 延迟)
- **代理未自动安装** — 需要运维手动 install (避免误操作)
- **cron 路径硬编码** — `/Users/xiamingxing/Workspace/` 需后续参数化

### Neutral

- **mof-drift LOW 增加 1 维** — commit_closure 当前 36 文件 = 信息, 不会触发报警
- **readiness 评分依赖 health.yaml SSOT** — 若 health.yaml 过期会显示旧分

## Compliance

### 验证指标

| 指标 | P60 末 | **P61 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.49 | **v0.0.50** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| mof-drift 维度 | 6 | **7** | +1 (commit_closure) |
| mof-drift LOW 计数 | 2 | **3** | +1 (commit_closure 36 files) |
| governance readiness | 80/100 | **95/100 (A+ L4)** | +15 |
| 自治代理骨架 | 无 | **scripts/omo/governance-agent.sh** | 新增 |
| ADR 数量 | 14 | **15** | +1 (0055) |

### 关联 ADR

- **ADR-0054**: P60 治理方法论内化 (L0 闭环 + frontmatter + commit frequency 规则)
- **ADR-0050**: gbrain 53 TODOs 4 类决策 (P50)
- **ADR-0051**: gbrain TODOs v5 终极 (P52)

### 关联 L0 规则

- `CR-GOV-CLOSED-LOOP-01` (强制闭环) — mof-drift v6 监控 commit_closure
- `CR-GOV-COMMIT-FREQUENCY-01` (工作树累积预警) — mof-drift v6 同源

## Notes

本 ADR 记录 P60→P61 过渡期的 4 项关键修复 + 增量, 形成"内化→验证→增强"闭环。

后续 P62+ 候选:
- governance-agent 完整事件总线集成 (omo event emit 真实路径)
- 代理自适应阈值 (根据历史趋势动态调整)
- dashboard 卡片实时显示 readiness 评分
- cron 安装脚本 (install-governance-agent-cron.sh)

---

*最后更新: 2026-06-23 · P61 · omostation 治理方法论深化*