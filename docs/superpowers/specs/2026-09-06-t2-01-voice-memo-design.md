---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y2Q1-T2-01
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T2-01 语音随想转录、结构化润色与待办入库设计

## 1. 目标

`cockpit voice-memo` 命令面：音频 → 可插拔 ASR 引擎转录 → 口语冗余
清洗与结构化润色 → 任务项/时间节点/责任人抽取 → 入 Cockpit Spine
备选池。macOS 快捷键/手机录音流的采集属部署配置（本 bet 消费音频文件）。

## 2. In scope

1. `projects/agora/src/agora/server/tools_bos/voice.py`（新文件）：
   - `transcribe(audio_path, engine)`：可插拔 ASR——`whisper-cli` /
     `whisper-cpp` / `funasr` 检测可用则真实转录；全部缺失 →
     `needs_asr_backend` 诚实失败（不伪造文本）。
   - `polish(text)`：口语冗余清洗（口水词/重复段删除，规则表）+
     结构化分拣（任务项 / 时间节点 / 责任人 / 随笔正文四类）。
   - `ingest_memo(audio_path)` → BOS 工具入口 `bos://voice/memo/ingest`。
2. `projects/cockpit/src/cockpit/commands/voice_memo.py`（新文件）：
   - `cockpit voice-memo <audio>` 命令：调用 BOS 服务，展示润色稿 +
     分拣结果；`--to-spine` 追加进 Spine 备选池
     （`.omo/state/spine-draft-pool.jsonl`）。
3. `projects/cockpit/src/cockpit/_subcommands.py`（增量）：注册。
4. 测试：polish 清洗规则、分拣抽取、needs_asr_backend 诚实失败、
   spine 入库（agora/cockpit 两侧）。

## 3. Out of scope

- 不安装/不捆绑 ASR 模型权重（引擎检测与调用约定为交付面）。
- 录音采集 UI（快捷键/手机端）属部署配置。
- done_when 的 ≤1.5s 与任务抽取以"可插拔引擎可用 + 样例文本"验证；
  引擎缺失时如实报 needs_asr_backend，不达标不收账。

## 4. 验收（对齐 ledger done_when）

1. ASR 引擎可用时端到端耗时计量输出（≤1.5s 目标，实测值如实记录）。
2. 任务项/时间节点/责任人抽取（规则样例集断言，与 T7-02 同口径）。
3. 润色稿可追加进 Spine 备选池（JSONL 原子追加）。
4. 单测全部通过。
