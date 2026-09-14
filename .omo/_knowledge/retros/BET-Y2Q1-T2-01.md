---
schema: bet-retro/v1
bet_id: BET-Y2Q1-T2-01
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-06
type: ephemeral
---

# BET-Y2Q1-T2-01 retro — 语音便签转录润色与待办入库

## What changed

- **agora `tools_bos/voice.py`**（新）：`transcribe`（可插拔 ASR 按序
  探测 whisper-cli → whisper-cpp → whisper → funasr；全部缺失/失败返回
  `needs_asr_backend` + install_hint，绝不伪造转录文本）、`polish`
  （中文口语填充词表清洗 + 任务项/时间节点/责任人三类分拣）、
  `ingest_memo`（BOS 入口 bos://voice/memo/ingest，带延迟计量）。
- **cockpit `commands/voice_memo.py`**（新）：`cockpit voice-memo
  --audio <f> [--engine] [--to-spine]`——解耦调用 agora env，`--to-spine`
  将润色稿原子追加进 `.omo/state/spine-draft-pool.jsonl`（fsync +
  os.replace）；parser/cli 接线。
- 测试 8/8（agora 5：清洗/essay 分类/时责抽取/缺音频/诚实失败；
  cockpit 3：spine 入库/诚实失败不入库/缺参拒绝），ruff clean。

## Q3 (打假)

- **done_when[0]（≤1.5s）本机无法实测**：本机无任何 ASR 引擎
  （whisper/funasr 均未安装），bet 维持 candidate 不收账——引擎安装
  与真实延迟测量留待部署环境（或 M4 节点）。机制面（可插拔探测、
  诚实失败、延迟计量字段）已就位并有单测。
- mac 自带 `say` 是 TTS 不是 ASR；whisper.cpp 的 Homebrew 包名是
  `whisper-cpp`（可执行文件 whisper-cli），install_hint 已按此写。
- 首个测试断言 detail 关键词，实现把提示放进了 install_hint 字段——
  断言与实现对齐后通过（测试意图：诚实失败必须带可行动指引）。

## Q4 (遗留)

- 真实引擎安装 + 1 分钟音频端到端计时（收账门）。
- funasr 的 python API 直连路径（当前 funasr 探测到但未实现 API 调用，
  走 CLI fallback 逻辑）。
- 快捷键/手机端录音采集 UI 属部署配置。
