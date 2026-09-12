---
schema: bet-retro/v1
bet_id: BET-Y2Q2-T3-01
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-12
type: ephemeral
---

# BET-Y2Q2-T3-01 Retro — 个人文风一致性多维雷达评估与语气自适应调节引擎

## What Changed
- 新增 `persona_radar.py` 核心引擎：7 维度文风雷达（正式度/亲和力/权威感/简洁度/具体性/节奏感/原创性）
- 新增 `persona_radar_eval.py` CLI 入口：支持文本评估、JSON 输出、语气方向调节
- `cockpit spine persona-radar` 子命令集成：通过 _omlxc_python() 桥接 omlxc 引擎
- 7 维度启发式度量：formality / warmth / authority / brevity / concreteness / rhythm / originality
- 三档语气方向：solemn / sharp / gentle，支持强度参数 (0-1)

## Key Decisions
- **无 ML 依赖**: 所有度量使用轻量级文本分析启发式（词表匹配 + 句长分析 + 词汇多样性）
- **对齐度计算**: 基于维度差距的逆加权平均，lower gap = higher score
- **自动重写触发**: 对齐度 < 85 时自动生成差距维度分析和调整建议
- **cockpit 桥接**: 通过 subprocess 运行 omlxc Python snippet，保持 cockpit 与 omlxc 解耦

## Verification
- `uv run python -m omlxc.dataplane.persona_radar_eval` → exit 0
- JSON 输出验证通过
- Tone shift (solemn/sharp/gentle) 三方向均验证通过

## Scope
- 5 files:
  - `projects/omlxc/src/omlxc/dataplane/persona_radar.py` (核心引擎)
  - `projects/omlxc/src/omlxc/dataplane/persona_radar_eval.py` (CLI)
  - `projects/omlxc/src/omlxc/dataplane/__init__.py` (导出)
  - `projects/cockpit/src/cockpit/commands/spine.py` (cockpit 集成)
  - `projects/cockpit/src/cockpit/_subcommands.py` (argparse 注册)
  - `docs/superpowers/specs/2026-09-12-t3-01-persona-radar-engine-design.md` (spec)
  - `.omo/_knowledge/retros/BET-Y2Q2-T3-01.md` (this retro)
  - `docs/plans/3y-bet-ledger.yaml` (status→done)
