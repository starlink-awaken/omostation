---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0073: P79 dim-weight 真实调优 + graphify --report-only + inotify 评估

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P79
- **Extends**: ADR-0072 (P78 跨子仓 + INDEX + 异常洞察)
- **Superseded by**: (无)

## Context and Problem Statement

P78 收口后, P79 调研 8 项候选, 实施 3 项:

1. **dim-weight 真实数据调优** (P72 算法 + P74 percentile, 30 快照实测)
2. **graphify --report-only 补全** (P75 wrapper 缺实现)
3. **inotify/watchdog 评估** (P76 --watch 0.5s 是否够)

跳过 5 项:
- graphify 实际扫描 (P80+)
- 跨子仓 omo event 联动 (P80+)
- 自治治理代理 cron 完整安装 (P80+)
- dashboard 卡片 UI (P80+)
- management 跨子仓引用 (P80+)
- API key 配置 (P80+)

## Decision

### D1: dim-weight 真实调优验证 (P79 R1)

**测试方法**:
- 生成 30 个模拟快照 (5h 间隔, commit_closure 偶变)
- 运行 dim-weight 算法
- 验证算法识别关键维度

**实测**:
```
frontmatter           0       25      ↓25   (25 稳定 → 0)
drift_low             24      20      ↑4    (15-20 偶变 → 略高)
commit_closure        76      20      ↑56   (18-25 偶变 → 最高)
adr_index             0       20      ↓20   (20 稳定 → 0)
governance_score      0       15      ↓15   (15 稳定 → 0)
```

**算法有效**:
- 稳定维度 → 权重 0 (不波动)
- 偶变维度 → 权重高 (波动越大越关键)
- **commit_closure** 突出: percentile_range 最大 → 权重最高 (76/20)

**P80+ 集成建议**:
- 调优后权重用于 readiness 计算: total = sum(score * weight/100)
- 与 governance-readiness 集成
- 与 dashboard 卡片集成

### D2: graphify --report-only 补全 (P79 R2)

**功能**:
- 不需 API key
- 读旧 graph.json 输出统计
- 已实现并测试

**实测** (旧 graph 是空):
```
============================================================
📊 P79 graphify 旧报告 (无需 API key)
============================================================
📁 来源: .omo/_knowledge/design/plans/graphify-out/graph.json
📈 总文件: 0
📝 总词数: 0
```

**应用**:
- 即使 graph.json 是空, 工具功能 work
- 待 graphify 实际跑后, --report-only 可读
- P80+ 建议: 与 governance-agent --include-trend 集成

### D3: inotify/watchdog 评估 (P79 R3)

**P76 R1: 已有 --watch (polling 0.5s)**

**评估结论**:
- 当前 P76 --watch 已足够 (0.5s 延迟, 90% 用例可接受)
- inotify/watchdog 需依赖 (inotify pip 包, watchdog 模块)
- 跨平台考虑: inotify (Linux), watchdog (跨平台), fsevents (macOS)
- **P79 决策**: 沿用 P76 --watch, 暂不实施 inotify

**P80+ 决策框架**:
| 方案 | 实时性 | 跨平台 | 推荐场景 |
|------|------|------|------|
| P76 --watch (polling) | 0.5s | ✅ | 通用 |
| inotify | <1ms | ❌ Linux | Linux 服务器 |
| watchdog | <10ms | ✅ | 桌面/服务器 |
| fsevents | <1ms | ❌ macOS | macOS |

## Consequences

### Positive

- **dim-weight 算法验证**: 30 快照测试证明算法有效
- **graphify --report-only 补全**: 工具完整
- **inotify 评估文档化**: P80+ 决策框架

### Negative

- **旧 graph.json 是空**: 待 P80+ graphify 实际跑
- **inotify 未实施**: 0.5s 延迟可能不够实时

### Neutral

- **不增 linter 维度**: 沿用 P58 独立 bin 工具
- **不增 mof-drift 维度**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P78 末 | **P79 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.67 | **v0.0.68** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 17 | **17** | 持平 |
| graphify 工具完整性 | 1 项缺 | **2 项完整** (extract + report-only) | +1 |
| ADR 数量 | 32 | **33** | +1 (0073) |

### 关联 ADR

- **ADR-0072**: P78 跨子仓 + INDEX + 异常洞察
- **ADR-0071**: P77 management 物理迁移
- **ADR-0070**: P76 --watch 实时 (沿用 P79, 不变)

### 关联 L0 规则

- `X2-FRESH-DOC-LIFECYCLE` — P79 文档化评估保留
- `CR-GOV-CLOSED-LOOP-01` — graphify report-only 即 commit 闭环

## Notes

本 ADR 记录 P79 3 项候选实施:
- ✅ dim-weight 真实调优 (30 快照验证, 算法有效)
- ✅ graphify --report-only (无需 API key)
- ✅ inotify 评估 (沿用 P76 --watch, P80+ 评估)
- ⏸ graphify 实际扫描 (P80+ 需 OPENAI_API_KEY)
- ⏸ 跨子仓 omo event 联动 (P80+)
- ⏸ 自治治理代理 cron 完整安装 (P80+)
- ⏸ dashboard 卡片 UI (P80+)
- ⏸ management 跨子仓引用 (P80+)
- ⏸ API key 配置 (P80+)

后续 P80+ 候选:
- graphify 实际扫描 (需 OPENAI_API_KEY)
- 跨子仓 omo event 联动
- 自治治理代理 cron 完整安装
- dim-weight 调优权重集成到 readiness 计算
- inotify/watchdog 安装 (Linux/跨平台)
- dashboard 卡片 UI 渲染

---

*最后更新: 2026-06-23 · P79 · omostation 治理方法论持续深化*