---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0056: P62 readiness 阈值优化 + mof-drift v7 stale_governance + install 脚本

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P62
- **Extends**: ADR-0054/0055 (P60-P61 治理深化)
- **Superseded by**: (无)

## Context and Problem Statement

P61 收口后, P62 调研发现 3 项可深化:

1. **readiness 阈值偏粗**: 4 档 (≤10/≤50/≤100/>100) 难以反映治理成熟度梯度
   - P61 阶段 37 文件 → 15/20 (低区分度)
2. **mof-drift 缺治理累积检测**: 7 维度未覆盖 `.omo/_control/` 任务/历史累积
   - P49 PLANNED 清零 + P51 drafts 清零 的稳态需机器可见
3. **governance-agent 缺 install 脚本**: cron 配置需要运维手动编辑

## Decision

### D1: mof-drift v7 — stale_governance 维度 (P62 R1)

**新增函数** `count_stale_governance() -> dict`:
- `drift_history` 累积文件数 (`.omo/_control/evolution/drift-history/`)
- `planned_tasks` planned 任务数 (`.omo/tasks/planned/`)
- `done_tasks` done 任务数
- `drafts` 草稿数
- `registry_size` M1 节点总数
- `age_days` .omo 目录最近文件 mtime 距今天数

**触发规则**:
| 阈值 | Severity |
|------|----------|
| planned > 5 (P49 历史清零) | medium |
| drafts > 0 (P51 历史清零) | medium |
| drift_history > 30 (累积待归档) | low |
| 其他 | low (信息) |

**实测**: planned=1, drafts=0, drift_history=5 (健康, 5 档细分)

### D2: readiness 阈值 5 档优化 (P62 R2)

**commit_closure 4→5 档**:
| 阈值 | 旧分 | 新分 |
|------|-----:|-----:|
| ≤ 5 | 20 | 20 |
| ≤ 30 | 15 | 18 |
| ≤ 80 | 15 | 15 |
| ≤ 300 | 10 | 10 |
| ≤ 500 | 10 | 5 |
| > 500 | 0 | 0 |

**drift LOW 4→5 档**:
| 阈值 | 旧分 | 新分 |
|------|-----:|-----:|
| ≤ 2 | 20 | 20 |
| ≤ 5 | 15 | 18 |
| ≤ 8 | 15 | 15 |
| ≤ 12 | 10 | 10 |
| > 12 | 0 | 5 |

**实测**: 95/100 → **96/100** (drift=4 → 18/20, commit=14 → 18/20)

### D3: governance-agent install 脚本 (P62 R3)

**文件**: `scripts/omo/install-governance-agent-cron.sh`

**功能**:
- `install` — 写入 crontab (每 6h)
- `--uninstall` — 移除
- `--status` — 显示状态 + 最近 5 次运行日志

**实测**: `--status` 返回 "❌ 未安装" (符合当前状态)

## Consequences

### Positive

- **mof-drift 8 维度**: 7 (P61) + 1 (stale_governance) = 全覆盖 P43-P62 治理方法
- **readiness 区分度提升**: 5 档区分让治理成熟度变化更敏感 (37 文件旧 15/20 → 新 18/20)
- **install 脚本可操作**: 运维可一键安装/卸载, 减少配置错误

### Negative

- **mof-drift 维度 7→8**: 略超 P57 维度饱和律阈值 (15) 的子集
- **stale_governance 阈值需校准**: 30 阈值是估算, 实际可能需 50

### Neutral

- **crontab 硬编码路径**: /Users/xiamingxing/Workspace 需 WORKSPACE_ROOT env
- **不触动 linter**: 沿用 P58 独立 bin 工具模式

## Compliance

### 验证指标

| 指标 | P61 末 | **P62 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.50 | **v0.0.51** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| mof-drift 维度 | 7 | **8** | +1 (stale_governance) |
| mof-drift LOW 计数 | 3 | **4** | +1 (stale_governance 信息) |
| governance readiness | 95/100 (A+ L4) | **96/100 (A+ L4)** | +1 |
| governance-agent install 脚本 | 无 | **scripts/omo/install-governance-agent-cron.sh** | 新增 |
| ADR 数量 | 15 | **16** | +1 (0056) |

### 关联 ADR

- **ADR-0055**: P61 readiness 修复 + mof-drift v6 (P62 直接扩展)
- **ADR-0054**: P60 治理方法论内化 (6 层落地)
- **ADR-0053**: P57 doc-lifecycle 100/100 + 维度饱和

### 关联 L0 规则

- `CR-GOV-DIMENSION-SATURATION-01` — mof-drift 维度 8 ≤ 15 阈值, 仍属合理范围

## Notes

本 ADR 记录 P62 治理深化:
- **mof-drift v7**: stale_governance 维度让 P49/P51 清零稳态机器可见
- **readiness 5 档**: 反映治理成熟度梯度, 区分度提升 15→18
- **install 脚本**: 自治治理代理可一键部署

后续 P63+ 候选:
- install 脚本实际安装 + 验证 cron 触发
- 5 档阈值的实际工作流校准
- governance-agent 事件总线集成 (omo event emit 真实路径)
- dashboard 卡片实时显示 readiness 评分
- 维度 9+: stale_drafts (P51 清零持续监控)

---

*最后更新: 2026-06-23 · P62 · omostation 治理方法论深化*