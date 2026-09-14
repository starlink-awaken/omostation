# 归档 — 基建架构过程文件

> 本目录存放从各 Phase 中移入的过程性文件（审计/复盘/红队/中间版本/一次性计划）
> 这些文件包含当时的分析过程，但核心结论已被提取到体系目录或沉淀到宪法/机制中
> 保留以供历史追溯，不主动引用

---

## 归档清单

| 原位置 | 文件 | 类型 | 归档原因 |
|--------|------|------|---------|
| phase0-硬件基建/ | ret-00-phase0-retrospective.md | 复盘 | 结论已融入宪法 |
| phase0-硬件基建/ | ret-00-phase0-verification-report.md | 验证报告 | 一次性验证 |
| phase1-架构工程/ | rin-08-AEC-retrospective.md | 复盘 | 结论已融入 AEC v1.1 |
| phase1-架构工程/ | rev-09-架构Review与机制设计.md | 复盘 | 结论已体现 |
| phase1-架构工程/ | rt-11-全量回顾与红队分析.md | 红队 | 已通过 v3 架构方案 |
| phase1-架构工程/ | res-10-OpenHuman分析报告.md | 调研 | 结论融入生态宪法 |
| phase2-Hermes解耦/ | rev-13-Hermes依赖分析.md | 分析 | 结论已体现在 pat-16 |
| phase2-Hermes解耦/ | rt-15-hermes解耦深度分析与红队报告.md | 红队 | 已通过解耦方案 |
| phase3-AAMF审计/ | rev-19-Phase1深度复盘债务审计红队.md | 审计 | 债务已修复 |
| phase3-AAMF审计/ | rev-22-Phase2深度复盘债务审计红队.md | 审计 | 债务已修复 |
| phase3-AAMF审计/ | rev-23-Phase3深度复盘债务审计红队.md | 审计 | 结论已融入 |
| phase3-AAMF审计/ | pat-19-AAMF迭代方案v2.md | 中间版本 | 被 pat-32/met-31 替代 |
| phase3-AAMF审计/ | pat-20-AAMF迭代方案v3.md | 中间版本 | 被 pat-32/met-31 替代 |
| phase4-AAMF迭代/ | rev-26-Phase5深度复盘热插拔审计.md | 审计 | 一次结论 |
| phase4-AAMF迭代/ | rev-28-Phase6深度复盘依赖维护视图审计.md | 审计 | 一次结论 |
| phase4-AAMF迭代/ | rev-29-AAMF全面复盘Phase7修订方案.md | 复盘 | 已规约到最终方案 |
| phase4-AAMF迭代/ | rev-30-Phase7深度复盘AAMF最终审计.md | 审计 | 最终结论 |
| phase5-Workspace对齐/ | rev-33-Phase8深度复盘.md | 复盘 | 过程记录 |
| phase5-Workspace对齐/ | rev-34-Phase9深度复盘.md | 复盘 | 过程记录 |
| phase5-Workspace对齐/ | rev-35-Phase10深度复盘.md | 复盘 | 过程记录 |
| phase5-Workspace对齐/ | rev-35-产品愿景执行偏差复盘.md | 复盘 | 纠偏已完成 |
| phase6-完成化/ | deb-38-PhaseA辩论复盘.md | 辩论记录 | 辩论结束 |
| phase6-完成化/ | rt-38b-PhaseA红队分析.md | 红队 | 已通过 |
| phase6-完成化/ | old-41-L1-契约版本化策略.md | 旧版 | 被 pat-41 替代 |
| phase6-完成化/ | old-42-X3-价值堆栈策略.md | 旧版 | 被 pat-42 替代 |
| phase6-完成化/ | mgr-37b-PhaseA详细任务分解.md | 任务分解 | 一次性计划 |
| phase6-完成化/ | mgr-40-ai-tools迁移计划.md | 迁移计划 | 已执行完成 |
| 根目录 | 44-Agora服务全面审计报告.md | 审计 | 与 phase6 中副本重复 |
| 根目录 | 45-16服务场景分析与验证.md | 场景 | 与 phase6 中副本重复 |


---

## 第二批归档（2026-06-03 深层榨取）

| 原位置 | 文件 | 类型 | 归档原因 |
|--------|------|------|---------|
| phase1-架构工程/ | pat-09-实施方案细化方案.md | 实施方案 | 一次性执行计划，已被实际执行取代 |
| phase2-Hermes解耦/ | mgr-14-Hermes解耦蓝图Roadmap.md | 路线图 | 已执行完毕，核心模式在 pat-16 |
| phase4-AAMF迭代/ | mgr-27-Phase6细化方案.md | 执行计划 | 被 mgr-41 替代 |
| phase3-AAMF审计/ | pat-24-AAMF-v2全面架构补全方案.md | 中间版本 | 被 met-31/pat-32 替代 |
| phase6-完成化/ | 44-Agora服务全面审计报告.md | 专项审计 | 结论已融入 aud-44 |
| phase6-完成化/ | 45-16服务场景分析与验证.md | 场景验证 | 一次性验证，结论已确认 |
| reference/ | sum-00-ARCHITECTURE_INVENTORY_SUMMARY.md | 摘要 | 一次性盘点 |
| reference/ | ss-20260522.md | 日志 | 一次性截图说明 |
| reference/ | 截图_20260522.jpg | 图片 | 一次性截图 |

## 汇总

- **第一批（结构清理）**: 29 个过程文件
- **第二批（深层榨取）**: 9 个冗余文件
- **总计**: 38 个文件已归档

---

## 备注

- 归档不删除——所有文件保留在 archive/ 下
- 如需恢复，移回原目录并更新 INDEX.md
- 引用已归档文件时，使用 `archive/` 前缀路径
