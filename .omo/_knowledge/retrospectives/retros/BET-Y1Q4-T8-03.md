---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-01
last-reviewed: 2026-09-01
bet: BET-Y1Q4-T8-03
title: 红头 DOCX/PPTX/SVG 渲染引擎
symptom: 无（按计划交付）；外围 gate 债务两处随车清理
solution: GOV_SPEC 单源 + cockpit venv 依赖隔离 + subprocess 委派测试
type: ephemeral
status: archived
---

# BET-Y1Q4-T8-03 复盘

## 做对了什么

1. **GOV_SPEC 单源常量**：国标全部参数（页边距/字体/字号/行距/缩进）集中一处，
   测试直接断言常量 + DOCX XML 双层验证——参数漂移不可能静默发生。
2. **依赖隔离策略**：python-docx/pptx 只进 cockpit venv；workspace 测试用
   subprocess 委派 cockpit CLI——CI 不需要装重依赖，测试仍然全量真实执行。
3. **从源头修而非断言放水**：sldSz 的 screen4x3 残留是改 XML type 标签，
   不是 `or True` 豁免（初版犯过 `... or True` 的懒病，当场清掉）。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| python-docx Cm→twips 取整与断言 int() 截断差 1 twip | 断言用同源 round() |
| python-pptx 默认模板 sldSz type 残留 screen4x3 | 设尺寸时同步改写 type |
| with zipfile 块外再用 z.read → archive closed | 读全移入 with 块 |
| ci-surfaces YAML 追加到文件尾进了 workflow_triggers 区块 | 按 anchor 插入 surfaces 列表尾 |
| E741/N806/N812 风格违规初版 12 处 | 全部清理（ruff gate 零容忍是对的） |

## 治理发现（随车修复的 main 预存债）

1. **governance-ratio 分类缺陷**：bet-execution（功能 BET 交付）被 claim 的
   .omo locks 判成 governance → 30 天治理占比虚高。加 FLEX_OVERRIDE_WORKFLOWS
   治本。根因：locks 判断在 workflow 判断之后，功能交付带治理面写文件就误判。
2. **#2863 的 CI 面欠账**：harness-* 5 项 workflow 检查未登记 ci-surfaces
   registry——"加检查不登记"是复发模式（此前 architecture-check 也是）。
   建议：新 workflow PR 模板加 ci-surfaces 登记检查项。

## 模板病计数

T8-03 台账 report 路径未来日期（2026-10-11）——**第 4 例**。前例 T7-03、T2-03。
建议剩余 13 个新 BET 批量校正。
