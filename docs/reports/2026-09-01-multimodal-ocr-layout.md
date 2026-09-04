---
schema_version: report/v1
lifecycle: history
type: delivery-report
owner: governance-team
created: 2026-09-01
last_updated: 2026-09-01
bet: BET-Y1Q4-T2-03
---

# 纸质公文扫描件多模态 OCR 结构化提取与版面保真还原（交付报告）

## 交付概览

| 项 | 结果 |
|----|------|
| 识别引擎 | macOS Vision framework（pyobjc，zh-Hans+en-US，accurate 档） |
| 版面引擎 | 纯 Python 几何重建（行聚类/元数据带/表格检测/印章/手写），零第三方依赖 |
| 命令面 | `cockpit spine ingress --source ocr --file <path>` ✅ |
| 服务面 | `bos_ocr_extract()` BOS 工具（bos://perception/agora/ocr） ✅ |
| 数据红线 | 100% 本地识别，无任何扫描件上传（non_goal 兑现） ✅ |
| verify 契约 | `test_document_layout` layout_fidelity=1.0, exit 0 ✅ |

## 实测结果（合成红头文件 A4@150dpi）

- Vision 识别 17-20 boxes，中文标题/文号/日期/正文/表格全部命中
- 表格还原：4 行 × 3 列完整重建（对齐容差 12px）
- 印章锚定：红底圆形印章文字（Vision 置信度 0.5）经词典通道锚定，
  输出 `{type: seal, bbox, nearby_text, confidence}` 元数据
- 手写签批：低置信度短文本通道输出 `{type: handwriting, bbox, text, confidence}`

## 关键工程决策

1. **pyobjc CGImage 路径**：CFURL 直喂 VNImageRequestHandler 在 pyobjc 下静默失败
   （perform=False, error=None）；改走 CGImageSource → CGImage →
   `initWithCGImage_options_` 后稳定。Swift 原生对照验证排除了环境问题。
2. **印章双通道检测**：实测红章文字 Vision 常只回 1 个低置信框，纯"聚集 ≥2"
   启发式会漏锚；补充印章词典（专用章/之印/公章/印章/盖章/戳记）单框通道。
3. **环境标记依赖**：`pyobjc-framework-Vision; sys_platform == 'darwin'` ——
   Linux CI 跳过安装，运行时惰性 import 失败自然降级 stub 源，几何引擎照常测试。
4. **circuit_breaker**：>16M 像素图按 2×2 Quartz 切片，逐块识别后坐标平移拼接。

## 验证记录

- 单测 10/10 通过（tests/test_ocr_layout.py，0.21s，Linux 兼容）
- stub fixture 全项 fidelity 1.0（标题/元数据/表格/印章/手写/正文 7 检查）
- 真图端到端：`/tmp/redheader-test.png`（无章版）+ `/tmp/redheader-seal.png`（红章版）
- cockpit 命令面端到端 exit 0

## 已知边界（诚实记录）

- 印章区域被圆环遮挡的文字 Vision 可能整段丢失（红章"医保专用"4 字未识别）——
  锚点元数据仍成立（bbox + 已识别片段），完整印章文字还原需要图像增强前置。
- 手写体判定依赖置信度启发式；印刷宋体模拟手写（高置信度）不会误报，
  但真实手写照片的置信度分布需后续真实样本校准。
