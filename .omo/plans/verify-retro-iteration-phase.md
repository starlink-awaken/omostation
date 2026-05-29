# Phase 6 — 验证·复盘·迭代·纠偏

> **周期**: 2026-06-02 ~ 2026-06-03 (2天)
> **负责人**: atlas (P10) + sisyphus (P9) + prometheus (P8)
> **前置**: Phase 5 (Self-Collab-Consensus 实现) 100%完成
> **性质**: **质量门禁** — 不过此关不能进入下一阶段
> **产出**: 复盘报告 + 9维健康看板 + 迭代修正清单 + 纠偏确认

---

## 门禁规则

1. Phase 5 所有 Task 必须为 `done` 才能进入 Phase 6
2. Phase 6 所有验证维度必须 >= 阈值才能关闭
3. 未通过的门禁项记录到 `AUDIT.md`，生成纠正任务
4. 纠正任务完成后重新验证

---

## Wave 6.1 — 验证门禁 (Day 9 AM)

| Task ID | 描述 | 验证方法 | 通过阈值 |
|---------|------|---------|---------|
| T084 | D1愿景验证: 检查OKR完成度，更新HEALTH_DASHBOARD | `cat .omo/HEALTH_DASHBOARD.md \| grep D1` | 综合达成度 ≥ 65% |
| T085 | D2场景覆盖度: 验证核心链路(1-5)是否全部走通 | 每条链路手动走一遍 | 链路1-5 ≥ 3条可用 |
| T086 | D3用户故事完整度: 检查所有新工具是否带--json和error code | `agora tool list` + 检查每个工具的inputSchema | 新工具100%达标 |
| T087 | D4功能点成熟度: 更新INVENTORY.md，重新计算成熟度 | `python3 .omo/scripts/health_d4.py` (新建) | 全项目平均 ≥ 3.5 |
| T088 | D5架构成熟度: 检查4+1+3各层组件是否存在 | 对照HEALTH_DASHBOARD.D5逐层检查 | 所有层至少1个组件 |
| T089 | D7安全质量: 跑ruff + 全量测试 + 渗透测试快照 | `ruff check` + `make test` + RED_TEAM_TRACKING | ruff=0, 测试全绿 |
| T090 | D8债务扫描: grep TODO/FIXME + 硬编码路径 + 测试覆盖率 | `grep -r "TODO\|FIXME\|HACK"` + 测试报告 | 债务不高于Phase 4 |

## Wave 6.2 — 复盘分析 (Day 9 PM)

| Task ID | 描述 | 方法 |
|---------|------|------|
| T091 | 对比规划与实际: 对照`self-collab-consensus-phase.md`检查每个Wave的交付 | Wave 5.1~5.4 逐条对比「计划vs实际」 |
| T092 | 提取经验教训: 什么做对了？什么做错了？下次怎么做？ | 写RETRO-PHASE5.md (格式参考RETRO-COMPLETE.md) |

## Wave 6.3 — 迭代修正 (Day 10 AM)

| Task ID | 描述 | 范围 |
|---------|------|------|
| T093 | 修复验证门禁发现的问题 | D1-D9中未达标的维度 |
| T094 | 复盘发现的问题修正 | RETRO-PHASE5.md中标记的action item |

## Wave 6.4 — 纠偏归档 (Day 10 PM)

| Task ID | 描述 | 产出 |
|---------|------|------|
| T095 | 更新HEALTH_DASHBOARD.md综合评分 | 综合健康评分 |
| T096 | 更新AUDIT.md: 记录架构债+流程失真 | 审计记录 |
| T097 | 更新STATE.md: Phase 5-6标记完成，准备下一阶段 | STATE.md |
| T098 | 决定: 进入Phase X 或 继续迭代Phase 5-6 | 决策记录 |

---

## 依赖关系

```
Phase 5 (T063-T083) 全部 done
  │
  └──→ Wave 6.1 验证门禁 (Day 9 AM)
         │
         ├── 全部通过 → Wave 6.2 复盘 (Day 9 PM)
         │                    │
         │                    └──→ Wave 6.3 迭代修正 (Day 10 AM)
         │                              │
         │                              └──→ Wave 6.4 纠偏归档 (Day 10 PM)
         │                                        │
         │                                        └──→ 下一阶段
         │
         └── 未通过 → 生成T093纠正任务 → 修正后回到Wave 6.1重新验证
```

## 门禁通过条件（全部满足）

```
☐ D1 愿景达成度 ≥ 65/100
☐ D2 核心链路 ≥ 3条可用
☐ D3 新工具100%有--json + error code
☐ D4 全项目成熟度 ≥ 3.5
☐ D5 所有层至少1个[EXISTS]组件
☐ D7 ruff=0 + 测试全绿
☐ D8 债务不高于Phase4
☐ T091-T092 复盘已记录
☐ T093-T094 修正已完成
☐ T095-T098 所有文档已更新
```
