---
schema_version: report/v1
lifecycle: history
type: delivery-report
owner: governance-team
created: 2026-09-01
last_updated: 2026-09-01
bet: BET-Y1Q4-T8-03
---

# GB/T 红头 DOCX / 16:9 PPTX / 矢量图渲染引擎（交付报告）

## 交付概览

| 项 | 结果 |
|----|------|
| DOCX 引擎 | `renderers/gov_docx.py` — GOV_SPEC 单源常量，GB/T 9704-2012 全参数 |
| PPTX 引擎 | `commands/render.py` — 16:9，dark-business / minimal-tech 双模板 |
| SVG 引擎 | ```diagram 代码块 → 框图矢量 SVG（边端点自动入节点） |
| 命令面 | `cockpit render docx/pptx/svg --input --template` ✅ |
| circuit_breaker | 模板异常 → 干净 Markdown 降级，exit 0（实测 bad-template 走通）✅ |
| verify 契约 | `render test_export_formats` fidelity **1.0** (10/10 checks) ✅ |
| gac-local-gate | PASS 56 checks ✅ |

## GB/T 9704-2012 参数落地（XML 层断言验证）

- 页边距：上 3.7 / 下 3.5 / 左 2.8 / 右 2.6 cm（twips 层断言）
- 标题：方正小标宋简体 二号 (22pt) 居中
- 正文：仿宋_GB2312 三号 (16pt)，首行缩进 2 字符（firstLineChars=200）
- 行距：固定值 28.95pt（lineRule=exact，每页 22 行国标网格）
- 字体为 DOCX XML 声明（w:eastAsia），渲染端 Word/WPS 解析——不依赖本机付费字体

## 关键工程决策

1. **sldSz type 修正**：python-pptx 默认模板残留 `type="screen4x3"`，设 16:9 尺寸时
   同步改写 type 标签为 `screen16x9`（从源头修，不做断言放水）。
2. **依赖隔离**：python-docx/pptx 只进 cockpit venv；workspace 层测试纯逻辑直跑
   （GOV_SPEC/parse/SVG）+ subprocess 委派 cockpit CLI 测重依赖路径——CI 环境无感。
3. **SVG 节点推断**：diagram 块只有边（`A -> B`）时端点自动收集为节点。

## 验证记录

- tests/test_render_formats.py 6/6 通过
- verify 契约 10 检查项全绿（含降级通道实测）

## 附带修复（main 预存债务）

- ci-surfaces registry 补登 5 项（#2863 Phase 8 harness-* 与 architecture-check 未登记）
- governance-ratio 分类修正：`bet-execution` 加入 FLEX_OVERRIDE_WORKFLOWS
  （功能 BET 被 .omo locks 误判 governance，30 天窗口占比虚高 50%→40%）
- ADR 0401 reserved 占位（#2852 signal 迁移后 INDEX 幽灵行清理）
