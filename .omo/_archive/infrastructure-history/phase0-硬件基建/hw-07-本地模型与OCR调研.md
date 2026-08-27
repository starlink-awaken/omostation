# 07 — 本地模型补充调研：Qwopus 与 OCR 方案

> 更新日期：2026-05-20

---

## 一、Qwopus 是什么？

**Qwopus = Qwen + Opus**，是社区蒸馏模型，非官方 Qwen 发布。

| 属性 | 说明 |
|------|------|
| 全名 | `Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled` |
| 作者 | HuggingFace 用户 `Jackrong` |
| 原理 | 将 Claude Opus 4.6 的推理能力（CoT 思维链）通过 SFT+LoRA 蒸馏到 Qwen3.5-27B |
| 量化后 | Q4_K_M ~16.5GB，可在单张 RTX 3090 / 24GB Mac 上运行 |
| 速度 | 29-35 tok/s |
| 是否推荐 | ⚠️ **社区魔改版，非官方。如果你追求稳定，优先用官方 Qwen3.6-35B-A3B** |

**结论：** Qwopus 是社区尝试，但 Qwen3.6-35B-A3B（MoE 官方版）在兼容性和稳定性上更优。不推荐作为主力模型。

## 二、Ollama 上最新的 MoE 模型总览（2026年5月）

| 模型 | 总参数 | 激活参数 | Ollama 大小 | 适合设备 |
|------|--------|---------|------------|---------|
| **qwen3.6:35b-a3b** ⭐ | 35B | 3B | ~21-24GB | **Mac mini 24GB ✅ • MBP 128GB ✅** |
| qwen3.6:27b (稠密) | 27B | 27B | ~17GB | Mac mini 24GB ✅ |
| qwen3:30b-a3b | 30B | 3B | ~19GB | Mac mini 24GB ✅ (更省) |
| **qwen3-coder-next** ⭐ | ~235B MoE | ~22B | ~52GB (量化) | **仅 MBP 128GB ✅** |
| qwen3-next | ~235B MoE | ~22B | ~52GB | 仅 MBP 128GB |
| qwen3:235b-a22b | 235B | 22B | ~142GB | 仅 MBP 128GB (勉强) |

## 三、OCR 方案推荐

### 三层方案

| 场景 | 推荐方案 | 内存 | 安装方式 |
|------|---------|------|---------|
| **中文文档/扫描件/手写** 🥇 | **PaddleOCR** | ~1-2GB | `pip install paddleocr` |
| **复杂文档/表格/印章** 🥇 | **GLM-OCR** (Ollama) | ~2.2GB | `ollama run glm-ocr` |
| **快速截图/日常 OCR** 🥉 | Apple Vision 原生 | 0 | 系统内置，零安装 |

### 详细说明

#### 1️⃣ PaddleOCR — 中文 OCR 之王

```bash
# 安装
pip install paddleocr

# 使用（一行命令）
paddleocr --image_dir 文档.png --lang ch --use_angle_cls true

# Python 调用
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='ch')
result = ocr.ocr('文档.png', cls=True)
```

- **中文精度最高**，80+ 语言
- 支持文档转 Markdown/JSON
- 支持手写识别
- Mac mini / MBP 均可，1-2GB 内存

#### 2️⃣ GLM-OCR — 复杂文档专用

```bash
# 通过 Ollama 安装（仅 2.2GB）
ollama run glm-ocr

# 或直接调 API
curl http://localhost:11434/api/generate \
  -d '{"model":"glm-ocr","prompt":"识别这张图片中的文字","images":["base64..."]}'
```

- OmniDocBench V1.5 评分 94.62，排名第一 🏆
- 支持复杂文档、表格、公式、印章
- 128K 上下文，可处理长文档
- **Mac mini 24GB 轻松跑**

#### 3️⃣ Apple Vision — 零安装快速 OCR

```bash
# macOS 原生，无需安装，一行脚本
# 1. 截图
screencapture -i /tmp/screenshot.png

# 2. 提取文字
# 通过 Shortcuts App 或 AppleScript 调用 VNRecognizeTextRequest

# 或用第三方工具如 TextSniper（App Store）
```

### 推荐集成方案

**Hermes 中集成 OCR 能力：**
- 日常中文文档 → 调 PaddleOCR
- 复杂排版/表格 → 调 GLM-OCR
- 截图提取文字 → Apple Vision

**不在本地跑 OCR 的场景（走云端）：**
- 如果图片量极大 → New API → DeepSeek V4 Flash 也支持视觉理解
