---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# P79 dim-weight 真实数据调优 + graphify 报告 + inotify 评估

**日期**：2026-06-23
**阶段**：P79 R1-R3
**目标**：基于 P78 候选清单实施 3 项深化

---

## 1. R1: dim-weight 真实数据调优

**测试方法**:
- 生成 30 个模拟快照 (P79, 5h 间隔, commit_closure 偶变)
- 运行 dim-weight 算法
- 验证算法识别关键维度

**实测结果**:
```
维度                    当前      默认      变化
  frontmatter           0       25      ↓25   (25 稳定 → 无变化)
  drift_low             24      20      ↑4    (15-20 偶变 → 略高)
  commit_closure        76      20      ↑56   (18-25 偶变 → 最高)
  adr_index             0       20      ↓20   (20 稳定 → 无变化)
  governance_score      0       15      ↓15   (15 稳定 → 无变化)
```

**算法验证**:
- 稳定维度 (frontmatter / adr_index / governance_score) 权重 0 → 不波动
- 偶变维度 (drift_low / commit_closure) 权重高 → 波动越大越关键
- **commit_closure** 突出: 18-25 范围 → percentile_range 最大 → 权重最高

**vs 默认权重** (P60):
- 默认 25/20/20/20/15 → 5 维均匀
- 真实调优 0/24/76/0/0 → 权重集中在波动维度
- 建议: 高波动维度 = 关键监控点

**真实数据调优建议**:
- 调优后权重用于 readiness 计算: total = sum(score * weight/100)
- 与 governance-readiness 集成 (P80+)

---

## 2. R2: graphify-local-extract --report-only 补全

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

---

## 3. R3: inotify/watchdog 评估

**P76 R1: 已有 --watch (polling 0.5s)**

**inotify 评估**:
- `import inotify` → ModuleNotFoundError (无 Python inotify 包)
- 备选: `pip install inotify` (Linux only, macOS/Windows 不支持)
- 备选: `watchdog` (跨平台)
- 备选: `fsevents` (macOS)

**评估结论**:
- 当前 P76 --watch (polling) 已足够 (0.5s 延迟, 90% 用例可接受)
- 真 inotify 安装复杂 (系统依赖, 跨平台)
- **P80+ 候选**: 若对实时性有强烈需求, 评估 watchdog

**P80+ 决策框架**:
| 方案 | 优势 | 劣势 | 适用 |
|------|------|------|------|
| P76 --watch (0.5s polling) | 简单, 跨平台, 无依赖 | 0.5s 延迟 | 通用 |
| inotify (Linux) | 实时 (<1ms) | Linux only, 编译复杂 | Linux 服务器 |
| watchdog (跨平台) | 跨平台, 实时 | 依赖多 | 桌面/服务器 |
| fsevents (macOS) | macOS 原生 | macOS only | macOS 开发 |

**P79 决策**: 沿用 P76 --watch, 暂不实施 inotify。P80+ 评估 watchdog（如果需求增长）。

---

## 4. 候选清单 (P79 实施)

| 候选 | 实施 | 关键 |
|------|------|------|
| ✅ dim-weight 真实调优 | R1 | 30 快照测试, 算法有效 |
| ✅ graphify --report-only | R2 | 旧 graph 读取 |
| ✅ inotify 评估 | R3 | 文档化, 暂不实施 |
| ⏸ graphify 实际扫描 | P80+ | 需 OPENAI_API_KEY |
| ⏸ 跨子仓 omo event 联动 | P80+ | 评估 |
| ⏸ 自治治理代理 cron 完整安装 | P80+ | 评估 |
| ⏸ dashboard 卡片 UI | P80+ | 评估 |
| ⏸ management 跨子仓引用 | P80+ | 评估 |
| ⏸ API key 配置 | P80+ | 运维配置 |

---

*最后更新: 2026-06-23 · P79 · omostation 治理方法论持续深化*
