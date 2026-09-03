---
schema_version: specification/v1
spec_version: 1.0.0
title: Gov-standard DOCX / PPTX / vector diagram renderer
bet_id: BET-Y1Q4-T8-03
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-01
last-reviewed: 2026-09-01
type: ssot
last_updated: 2026-09-03
---

# Gov-standard DOCX / PPTX / vector diagram renderer (T8-03)

## Intent

初稿 Markdown 一键渲染为符合 GB/T 9704-2012 的红头 DOCX、16:9 高管技术汇报
PPTX 与矢量架构图。排版参数 100% 走模板契约（BET non_goal：无未经模板
校验的随意排版）。

## Architecture (KISS, two-day appetite)

```
projects/cockpit/src/cockpit/renderers/gov_docx.py（GB/T 9704-2012 DOCX 引擎）
├─ parse_markdown(md) → DocModel(heading/meta/body/lists/quote)
├─ GOV_SPEC 常量: A4; 页边距上 3.7cm/下 3.5cm/左 2.8cm/右 2.6cm;
│   标题 方正小标宋简体 二号(22pt) 居中; 正文 仿宋_GB2312 三号(16pt);
│   行距 固定值 28.95pt; 正文首行缩进 2 字符; 每页 22 行 × 28 字
├─ render_docx(model, output) — python-docx 声明式排版（字体名为
│   XML 声明，不依赖本机安装付费字体；Word/WPS 渲染时按声明解析）
└─ degrade(md, output) — circuit_breaker: 模板/解析异常 → 干净
    Markdown + 普通 PDF 降级输出（exit 0 不阻塞）

projects/cockpit/src/cockpit/commands/render.py（命令组 + 轻渲染器）
├─ cockpit render docx --input <md> --output <> --template standard-gov
├─ cockpit render pptx --input <md> --output <> --template dark-business|minimal-tech
│   PPTX: python-pptx 16:9; 深色商务（深蓝底/白字/accent 金）/
│   极简科技（白底/深灰字/蓝 accent）; heading→封面, h2→分节页, 列表→要点页
├─ cockpit render svg --input <md> --output <>（矢量架构图:
│   ```diagram 代码块 → 框图 SVG，boxes+arrows 简排布）
└─ cockpit render test_export_formats — verify 契约（exit 0）:
    合成 Markdown → DOCX/PPTX/SVG 三产物全断言（存在/可解析/
    GB/T 关键参数抽查），产物落 .omo/state/render-test/（不入库）
```

## Template contracts (done_when 映射)

- DOCX 字体/行距/页边距 100% 国标: GOV_SPEC 常量单源 + test 断言
  （XML 层检查 w:eastAsia 字体名、页边距 twips、行距 exact 值）
- PPTX 模板匹配: dark-business / minimal-tech 双模板色板常量
- 命令面: cockpit render docx/pptx --input --template

## Degradation (circuit_breaker)

模板解析异常（未知 template / Markdown 结构异常）→ 降级输出标准干净
Markdown 文件 + 提示，exit 0。

## Dependencies

cockpit pyproject += python-docx, python-pptx（纯 Python，Linux CI 可装）。

## Verify (BET contract)

- `uv run python -m cockpit.cli render test_export_formats` → exit 0
- `make gac-local-gate` → exit 0
