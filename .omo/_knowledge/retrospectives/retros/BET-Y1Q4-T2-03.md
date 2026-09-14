---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-01
last-reviewed: 2026-09-01
bet: BET-Y1Q4-T2-03
title: 纸质公文扫描件 OCR 版面还原
symptom: 无（按计划交付，无故障）
solution: pyobjc CGImage 通道 + 印章词典双通道 + 几何版面引擎
type: ephemeral
status: archived
---

# BET-Y1Q4-T2-03 复盘

## 做对了什么

1. **Swift 原生对照验证**：pyobjc performRequests 静默失败（返回 False + error None）
   时，没有在 Python 侧瞎猜 API 组合，先写 10 行 Swift 排除环境问题，锁定
   pyobjc CFURL 桥接缺陷，再换 CGImage 通道一次成功。
2. **几何引擎与识别源解耦**：版面重建（行/列/表/章/手写）是纯几何逻辑，
   完全不依赖 Vision——stub 源让 CI/Linux 全量测试，真模型只测端到端。
3. **实测驱动的启发式修正**：红章实测发现"聚集 ≥2"漏锚（红底文字 Vision 常
   只回 1 框），当天补印章词典通道；文号印刷体 0.5 置信度实测确认不误报。

## 踩了什么坑

| 坑 | 修复 | 耗时 |
|----|------|------|
| pyobjc 类名 VNRequestHandler 不存在 | VNImageRequestHandler（dir() 确认） | 小 |
| initWithURL_options_error_ 签名漂移 | init 试错 → 最终换 CGImage 通道 | 中 |
| CGImageRef 无 .width() 方法 | CGImageGetWidth() 函数式 API | 小 |
| Edit 重构时变量名 b/box 混用 | NameError → 单点修复 | 小 |

**根因**：pyobjc 的 API 面与 Swift/ObjC 文档存在桥接漂移（类名、init 签名、
CG 类型方法），文档不能照抄。对策已入报告：Swift 对照法。

## 模板病复发（第 3 次）

台账 write_surfaces 的 report 路径又写成未来日期（2026-10-06）。T7-03、T2-03
已两次触发 WORK_PACKET_SCOPE_MISMATCH。建议：16 个新 BET 批量校正
report/retro 路径日期为真实开工日期。

## 下一步

- 真实扫描件（手机拍照）校准手写置信度阈值
- 印章区域图像增强（红色通道提取）提升章内文字还原率
- PDF 影印件接入（当前只吃位图）
