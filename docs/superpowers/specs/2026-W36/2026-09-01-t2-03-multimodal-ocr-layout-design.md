---
schema_version: specification/v1
spec_version: 1.0.0
title: Multimodal OCR & layout-faithful restoration
bet_id: BET-Y1Q4-T2-03
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-01
last_updated: 2026-09-01
type: ssot
last_updated: 2026-09-03
---

# Multimodal OCR & layout-faithful restoration (T2-03)

## Intent

对拍照扫描件 / PDF 影印件红头公文做本地 OCR、版面分析（表格、盖章、手写签批）
与 Markdown 结构化还原。100% 本地执行，不上传任何扫描件至外部公网
（BET non_goal 红线）。

## Architecture (KISS, two-day appetite)

```
projects/agora/src/agora/server/tools_bos/ocr.py（BOS OCR 域模块，引擎内聚）
├─ 识别源
│   ├─ _recognize_via_vision(image) — macOS Vision framework (pyobjc 惰性
│   │   import，VNRecognizeTextRequest zh-Hans)。CI/Linux 无 pyobjc 时不炸。
│   └─ _recognize_stub(image) — 合成降级源（fixture/测试几何引擎）
├─ 几何版面引擎（纯 Python 零依赖，可离线全量测试）
│   ├─ _cluster_lines(boxes)      — y 重叠聚类成行（跨列合并约束）
│   ├─ _group_columns(rows)       — x 间隙切列（红头文号/日期双栏还原）
│   ├─ _detect_tables(lines)      — 等距 x 对齐 + 分隔行检测 → Markdown 表格
│   ├─ _detect_seals(boxes)       — 独立锚定区（远离正文列、孤立成块）→ 印章锚点
│   └─ _classify_handwriting(boxes) — 低置信度 + 楷体特征 → 手写签批元数据
├─ render_markdown(layout)        — 版面保真 Markdown（标题/段落/表格/锚点）
├─ bos_ocr_extract(file_path)     — BOS 服务调用：本地引擎直调，产出 JSON+MD
├─ circuit_breaker                — 图片超过阈值像素 → 切片分块识别再拼接
└─ main(argv)                     — `python -m agora.server.tools_bos.ocr
                                    test_document_layout`（verify 契约，exit 0）

projects/cockpit/src/cockpit/commands/spine.py（扩展）
└─ `cockpit spine ingress --source ocr --file <path>` 子命令：
   subprocess 调 `python -m agora.server.tools_bos.ocr extract --file <path>`，
   Rich 渲染还原结果（命令行入口契约 done_when）
```

## Layout engine contracts (done_when 映射)

- 排版还原度 ≥95%：行/列聚类后按 (column, row) 序输出，段落间距保持
- 表格结构还原度 ≥90%：≥3 行连续 x 对齐 + 列间隙一致 → Markdown 表格
- 印章锚定：独立锚定区输出 `{type: seal, bbox, nearby_text}` 元数据
- 手写签批：低置信度框输出 `{type: handwriting, bbox, text}` 元数据

## Degradation (circuit_breaker)

- 非 macOS / 无 pyobjc → stub 识别源（几何引擎照常工作，测试不依赖真模型）
- 图片过大（>circuit_breaker 阈值）→ 切片分块 + 逐块识别 + 坐标平移拼接

## Verify (BET contract)

- `uv run python -m agora.server.tools_bos.ocr test_document_layout` → exit 0
- `make gac-local-gate` → exit 0
