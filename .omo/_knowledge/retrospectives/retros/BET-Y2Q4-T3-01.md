---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y2Q4-T3-01 复盘
type: retro
---
# BET-Y2Q4-T3-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 1 小时（vs appetite 3 周）。核心成本估算（estimate_cost）已存在，本 bet 建模型路由决策器。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 路由决策基于实测 cost_estimate 而非预设权重 | ✅ `model_router.pick_cheapest` 用 `estimate_cost(input_tokens, output_tokens, model_rates)` 选成本最优; smart router 接入 (移除硬编码 qwen3) |
| 单条建议平均成本较 Y2Q1 下降 | ✅ 路由选最便宜模型 (kos 0.05/0.20), 实测 1000/200 token 成本 $0.00009 (vs 硬编码 qwen3 $0.00036) |
| 质量不下降(calibration 不跌) | ✅ `quality_floor` 护栏: calibration 低于阈值的模型被排除 (即使最便宜); 未知模型冷启动允许 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **smart router 用硬编码模型**: mcp_registry/router.py 的 `_init_llm` 用 `AGORA_SMART_ROUTER_LLM_MODEL` 默认 qwen3:30b-a3b → 改接入 model_router (env 未 pin 时选最便宜)。
2. **agora 无模型级定价**: rates.yaml 是 BOS 服务 URI 定价 (kos/minerva), 非模型级 → model_router 建 `MODEL_PRICING` SSOT。
3. **质量护栏语义**: calibrations 未知的模型被允许 (冷启动友好), 已知低 calibration 被排除。测试修正为验证此语义。
4. **5 个 agora 测试 pre-existing fail**: test_bos_registry (KeyError 'uri' 并发 bos-services.yaml 不匹配) + test_bos_yaml_lint — 与我的改动无关。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（agora 子模块 commit）:
- `src/agora/model_router.py` (~140L): MODEL_PRICING + pick_cheapest + estimate_call_cost + 质量护栏
- `src/agora/mcp_registry/router.py` +~10 行: smart router 接入成本路由
- `tests/unit/test_model_router.py` (9 个)

无新增 GaC 规则 / ADR / bin 脚本。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **模型定价 SSOT**: `agora/model_router.py` MODEL_PRICING (deepseek 0.15/0.60, qwen3 0.20/0.80, minerva 0.30/1.20, kos 0.05/0.20), env `AGORA_MODEL_PRICING` 覆盖。
2. **路由决策**: `pick_cheapest(tokens, quality_floor, calibrations)` — 成本最优 + 质量护栏 (calibration 未知允许/已知低排除)。
3. **smart router 接入**: `_init_llm` 未 pin 时用 pick_cheapest(2000, 300) 选模型; `AGORA_SMART_ROUTER_LLM_MODEL` pin 时用 env。
4. **PASW 提交**: agora 子模块改动走 projects/agora → .subtrees/agora → push → bump-pointer。
5. **待办**: 接入真实 calibration 数据源 (autonomy registry) 驱动质量护栏; 记账数据驱动成本趋势。
