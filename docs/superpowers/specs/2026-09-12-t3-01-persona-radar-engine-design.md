---
schema_version: specification/v1
spec_version: 1.0.0
title: 个人文风一致性多维雷达评估与语气自适应调节引擎
bet_id: BET-Y2Q2-T3-01
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-12
last-reviewed: 2026-09-12
risk_level: L1
human_gate: true
type: ssot
last_updated: 2026-09-12
decision_ref: decision://accepted/BET-Y2Q2-T3-01
---

# T3-01 — 个人文风一致性多维雷达评估与语气自适应调节引擎

## Context

本 BET 实现一个多维雷达评估引擎，用于度量个人文风一致性并提供语气自适应调节能力。
核心场景：自动输出文风雷达对齐得分（0-100 分），低于 85 分自动触发局部重写建议，
并提供三档语气滑块（"更庄严稳重"、"更犀利专业"、"更柔和温和"）调节目标画像。

## Scope

- 7 维度文风雷达：正式度、亲和力、权威感、简洁度、具体性、节奏感、原创性
- ToneProfile 数据模型：0-1 连续可调的 7 维目标画像
- ToneDirection 枚举：solemn / sharp / gentle 三档语气方向
- tone_shift() 函数：在给定方向上按强度调节目标画像
- compute_radar() 函数：全量雷达评估 + 对齐度计算 + 建议生成
- auto_rewrite_suggestion()：低于阈值时自动触发重写建议
- CLI 入口：`uv run python -m omlxc.dataplane.persona_radar_eval`
- Cockpit 集成：`cockpit spine persona-radar` 子命令

## Out of Scope

- ML 模型训练/推理（所有度量使用轻量级文本分析启发式）
- 真实 LLM 重写（仅提供差距维度分析和建议）
- 历史署名文风学习（本期不实现动态学习，使用静态目标画像）

## Acceptance Criteria

1. `uv run python -m omlxc.dataplane.persona_radar_eval` exit 0
2. 雷达评估输出 7 维度得分 + 对齐度 (0-100)
3. 低于 85 分自动输出重写建议
4. 支持 `--tone solemn|sharp|gentle` 三档语气调节
5. `make gac-local-gate` exit 0

## Architecture

```
omlxc/dataplane/persona_radar.py          # 核心引擎（数据模型 + 启发式 + 计算）
omlxc/dataplane/persona_radar_eval.py     # CLI 入口（argparse + JSON/文本输出）
cockpit/commands/spine.py                 # cockpit spine persona-radar 子命令
cockpit/_subcommands.py                   # argparse 注册
```

## Dependencies

- 无外部 ML 依赖
- 使用 Python stdlib (re, dataclasses, enum)
- cockpit 集成通过 _omlxc_python() 子进程桥接

## Risk Assessment

- L1: 低风险。所有启发式均为无状态纯函数，无外部 I/O 依赖
- ToneProfile 默认值基于通用专业写作风格，后续可按个人偏好调整
- 启发式度量精度有限（无 ML），但足以捕捉文风漂移趋势
