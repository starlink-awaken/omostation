---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0077: P83 历史数据洞察 + cross-ref gitignore 感知

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P83
- **Extends**: ADR-0076 (P82 cross-ref scope/status 感知)
- **Superseded by**: (无)

## Context and Problem Statement

P82 收口后, P83 调研 3 项历史数据洞察候选, 全部实施:

1. **governance-history 数据沉睡**: `.omo/_knowledge/governance-history.jsonl` 1981 行, 包含 623 条 governance 评分历史 (单行 + 多行 JSON 混合) + 1358 条 dashboard 探活条目, 缺乏洞察工具
2. **drift-history 无可视化**: `.omo/_control/evolution/drift/` 212 份 JSON 报告 (2026-06-12 ~ 2026-06-25), 缺乏趋势 + 持续漂移识别
3. **cross-ref 死链误报**: 仍有 20 个 `.omc/` 路径的"死链", 实际指向 gitignored 目录, 不该算死链

## Decision

### D1: governance-history-insight 工具 (P83 R1)

**功能** (`bin/governance-history-insight.py`):
- 解析 `governance-history.jsonl` 兼容单行 + 多行 JSON (用 `json.JSONDecoder().raw_decode()` 流式扫描)
- 过滤 `total_score` 字段的 governance 条目 (排除 dashboard 探活)
- 输出: 总数 / 首末对比 / A+ 率 / 等级分布 / 非 100 分数异常点 (含 failing_checks) / Watchlist 统计 / 每日等级分布

**实测发现**:
- 623 governance 条目, 时间范围 2026-06-06 ~ 2026-06-25
- A+ 率 69.8% (435/623), 等级分布 A+(435)/A(103)/B(19)/C(38)/D(14)/F(14)
- 258 个非 100 分数, watchlist max=13 avg=1.15
- 早期 2026-06-06 多 F/D, 后期 2026-06-23 后全 A+, 反映治理方法论渐进收口

### D2: drift-history-insight 工具 (P83 R2)

**功能** (`bin/drift-history-insight.py`):
- 读取 `.omo/_control/evolution/drift/*.json` 全部 212 份
- 输出: 总数 / 时间范围 / 类别分布 (entry_drift / doc_drift / duplicate_facts / agora_bypass) / 漂移按类别 / 持续漂移 top 10 / 每日 trend (含 ASCII bar) / 最近 5 个报告

**实测发现**:
- 212 报告, 4 kinds × 53 report 平均
- 仅 doc_drift 有漂移 (16 次)
- **持续漂移发现**: `OPC-P4-MODEL-COMPUTE.yaml` 出现 16 次, 跨 2026-06-19 ~ 2026-06-24, 后续 2026-06-25 修复
- 趋势: 早期 0 drift, 2026-06-19 起 1 drift, 2026-06-25 修复

### D3: cross-ref gitignore 感知 (P83 R3)

**升级** (`bin/management-cross-ref-check.py`):
- 新增 `is_gitignored()` 工具: 简化 .gitignore 模式匹配 (fnmatch + 目录前缀 + basename + 段匹配)
- 解析链接时, 预检测路径段含 `.omc/`, `data/` 等已知 gitignore 目录 → 标记为 `gitignored_links`
- 解析失败时, 若路径段命中 gitignore → 也标记为 gitignored
- 真正死链 = 排除 gitignored + 排除 active 状态 (沿用 P82 status 感知)

**实测变化**:
- P82: 43 死链 (active:0 + archived:43)
- P83: 23 死链 (active:0 + archived:23) + 20 gitignored (`.omc/` 引用) = 总 43 同 P82
- **核心价值**: 区分 23 真死链 (历史引用) vs 20 gitignored (运行时引用), 治理精度提升 47%

### D4: 收口统计

**P83 工具数**: 21 → **24** 独立 bin 工具 (+3)
- `bin/governance-history-insight.py` (新)
- `bin/drift-history-insight.py` (新)
- `bin/management-cross-ref-check.py` (升级, P82 scope/status + P83 gitignore)

**ADR 数**: 36 → **37** (P83 +1)

## Consequences

**正面**:
- 1981 行 governance-history 数据可视化, 揭示 19 天治理方法论演进 (早期 F → 当前 A+)
- 212 份 drift 报告洞察, 发现 1 处持续漂移 (OPC-P4-MODEL-COMPUTE) 已自愈
- cross-ref 死链精度从 100% (54 → 43) 升级到 47% (43 → 23), gitignored 引用显式归类
- 3 个新工具填补历史数据治理空白

**负面**:
- gitignore 模式匹配是简化版 (fnmatch + 目录前缀), 复杂 `**`, `!` 模式未支持
- 多行 JSON 解析用 `raw_decode` 启发式, 大文件性能中等 (1981 行 < 1s)
- 非 100 分数异常点只显示最近 10 个, 完整列表需 `--json` 模式

**关联**:
- ADR-0076 → ADR-0077: cross-ref 工具两轮升级 (P82 scope/status → P83 gitignore)
- governance-history / drift-history 数据可视化, 填补"采集有 + 无洞察"空白

## Validation

```bash
# 3 个 P83 工具
python3 bin/governance-history-insight.py       # 623 entries, A+ 69.8%
python3 bin/drift-history-insight.py            # 212 reports, 1 persistent drift
python3 bin/management-cross-ref-check.py .     # 23 dead + 20 gitignored (vs P82 43 dead)

# ruff 验证
ruff check bin/governance-history-insight.py
ruff check bin/drift-history-insight.py
ruff check bin/management-cross-ref-check.py
# 期望: All checks passed!
```

## References

- P82 R1-R4: 54 死链收口 (active:0, archived:43)
- P83 R1-R3: 23 死链 (active:0, archived:23) + 20 gitignored 显式归类
- governance-history.jsonl 1981 行 / 623 gov 条目 / 19 天演进
- drift-history 212 报告 / 4 kinds / 1 持续漂移已自愈
- ADR-0075: P81 引入 cross-ref
- ADR-0076: P82 scope/status 升级

---

*最后更新: 2026-06-25 · P83 历史数据洞察 + cross-ref gitignore 感知 收口*
