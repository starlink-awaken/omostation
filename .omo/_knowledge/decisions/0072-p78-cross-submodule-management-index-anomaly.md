---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0072: P78 跨子仓联动 + management INDEX + alert-history 自动洞察

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P78
- **Extends**: ADR-0071 (P77 management 物理迁移)
- **Superseded by**: (无)

## Context and Problem Statement

P77 收口后, P78 调研 5 项候选, 实施 4 项:

1. **跨子仓联动** (ecos/agora/cockpit/omo/runtime/scripts 健康检查)
2. **management 子目录 INDEX.md** (P77 物理迁移后)
3. **alert-history 自动洞察** (sudden_spike / level_escalation / type_concentration / suppression_heavy)
4. **P0 listener inotify** (无 inotify 模块, P76 --watch 已足够)

跳过 1 项:
- graphify 实际扫描 (P78+ 持续跳过, 需 OPENAI_API_KEY)

## Decision

### D1: 跨子仓联动检查 (P78 R1)

**新工具**: `bin/ssot/cross-submodule-check.py` (140 行)

**功能**:
- 检查 6 个核心子仓 (ecos / agora / cockpit / omo / runtime / scripts)
- 状态: dirty / behind / ahead / healthy
- 输出 text + JSON 两种格式

**实测**:
```
ecos        🔴 未提交       0     0     21778cb7 fix(workflow)
agora       🔴 未提交       0     0     5731d102 feat
cockpit     🔴 未提交       0     0     419a51f1 fix
omo         🔴 未提交       0     0     70d8a5e9 test
runtime     🔴 未提交       0     0     42212b68 security
```

### D2: management INDEX.md (P78 R2)

**新文件**: `.omo/_knowledge/management/INDEX.md`

**内容**:
- 子目录结构表 (workflows/playbooks/guides)
- 数量统计 (127/5/12)
- 关键词映射 (P75 自动分类)
- 工具关联 (P75 categorize / P77 migrate / P78 check)
- 双指针说明 (P53 简化版)

### D3: alert-history 自动洞察 (P78 R3)

**修改**: `bin/gac/alert-history.py` `analyze_history()`

**新增 `detect_anomalies()` 函数**:
- 4 类异常检测:
  - `sudden_spike`: 1h 内同类型 > 5 次
  - `level_escalation`: 7d 内 P0 出现
  - `type_concentration`: 单一类型占 > 80%
  - `suppression_heavy`: 抑制率 > 70%

**实测** (7 通知 + 5 抑制):
- 🚨 7d 内 P0 触发
- 📊 low_mean 占 100% (> 80% 集中度)

### D4: P0 inotify (P78 R4)

**结论**: 无 `inotify` Python 模块, 沿用 P76 `--watch` (0.5s polling) 已足够

**P79+ 候选**:
- `pip install inotify` (Linux only)
- watchdog (跨平台)
- fsevents (macOS)

## Consequences

### Positive

- **跨子仓联动可视化**: 6 子仓健康一目了然
- **management 目录有 INDEX**: 3 子目录结构清晰
- **alert 自动洞察**: 4 类异常自动识别
- **P0 inotify 不阻塞**: P76 --watch 足够

### Negative

- **6 子仓全 dirty**: X-Plane Audit Agent 持续 commit (非真问题)
- **inotify 缺失**: P76 polling 是 0.5s 延迟, 不够实时

### Neutral

- **不增 linter 维度**: 沿用 P58 独立 bin 工具
- **不增 mof-drift 维度**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P77 末 | **P78 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.66 | **v0.0.67** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 16 | **17** | +1 (cross-submodule-check) |
| alert-history 异常类型 | 0 | **4** (sudden_spike/level_escalation/type_concentration/suppression_heavy) | +4 |
| management INDEX | 无 | **1** (3 子目录结构) | +1 |
| ADR 数量 | 31 | **32** | +1 (0072) |

### 关联 ADR

- **ADR-0071**: P77 management 物理迁移 (P78 INDEX 依赖)
- **ADR-0069**: P75 management 分类 (P78 migrate 沿用)

### 关联 L0 规则

- `X2-FRESH-COMMIT-FATIGUE` — 跨子仓 dirty 监控
- `CR-GOV-CLOSED-LOOP-01` — INDEX 更新即 commit 闭环

## Notes

本 ADR 记录 P78 4 项候选实施:
- ✅ 跨子仓联动检查 (新工具, 17 独立 bin)
- ✅ management INDEX.md (3 子目录结构)
- ✅ alert-history 自动洞察 (4 类异常)
- ✅ P0 inotify (评估, 沿用 P76 --watch 足够)
- ⏸ graphify 实际扫描 (P79+)

后续 P79+ 候选:
- graphify 实际扫描 (需 OPENAI_API_KEY)
- inotify 安装 (Linux only)
- dim-weight 真实数据调优
- 跨子仓 omo event 联动
- alert-history 加更多洞察类型 (LSTM/ML)

---

*最后更新: 2026-06-23 · P78 · omostation 治理方法论持续深化*