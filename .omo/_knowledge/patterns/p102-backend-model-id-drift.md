---
type: ssot
owner: governance-team
last-reviewed: 2026-09-06
---

# P102 — backend_model_id 漂移：调度器指着一个不存在的模型

**Pattern observed**: 2026-09-06，omlxc `models unload` 反复失败的真实根因。
比表面上的"派发错后端"深一层。

## Problem

调度器的 placement 用 `backend_model_id` 指向后端上的具体模型。后端上的模型清单
会变（换目录、改名、模型没加载成功、App 重启后只挂载了一部分），但配置里的
`backend_model_id` **不会自动跟着变**。

结果：placement 在配置里存在、在 catalog 里可见、在路由候选里被选中，
**但它指向的后端模型根本不存在**。所有对它的操作如实失败，
而失败信息（`operation_failed`）看不出"目标就不存在"这一层。

## Symptom

`omlxc models unload <model> --yes` 反复失败，内存纹丝不动。
job 表里 `error_code=operation_failed`，`rollback_reference` 指着一条看起来
完全合理的 placement。

## Detection

把配置里的 `backend_model_id` 和后端实际暴露的清单做交集：

```bash
python3 -c "
import tomllib, urllib.request, json
d = tomllib.load(open('$HOME/.config/omlxc/config.toml','rb'))
live = {m['id'] for m in json.load(urllib.request.urlopen('http://127.0.0.1:8000/v1/models', timeout=5))['data']}
for p in d.get('placements', []):
    if 'omlx-app' in p.get('backend_id','') and p['backend_model_id'] not in live:
        print('❌', p['id'], '→', p['backend_model_id'])
"
```

本次实测结果：omlx-app 后端 25 条 placement 里 **9 条漂移**
（`coding-fast` / `reasoning-lite` / `vision-large` / `mythos-fast` /
`qwen-3.5-9b-flash` / `qwen-3.5-9b-pro` / `gemma-4-26b-a4b-it-qat-mlx-4bit` /
`mid-local` / `qwen-3.8-27b-dflash`）。

`omlxc status` 里的 `inventory_drop <backend> 38→16` 就是这个现象的告警，
但它只报数量、不报是哪几条，容易被当成噪音略过。

## Root Cause

**配置和后端各自演化，没有对账机制。** 后端模型清单是运行时事实，
`backend_model_id` 是配置里的声明，两者之间没有任何一致性检查。

> **订正 (2026-09-06)**：本文原来这里还写了第二条"后端 `/v1/models` 不暴露
> 加载状态，信号源根本给不出这个信息"——**这句话是错的**，没有先查 adapter
> 代码就下的结论。真相：`/v1/models`（裸端点）确实没有 `state` 字段，但
> omlx_app 后端另有 `/v1/models/status` 端点给出真实的逐模型 `loaded` +
> 内存数据，Ollama 有 `/api/ps`，LM Studio 走 SSH `lms ps --json`——三个
> adapter 都已经正确实现了这些机制，不是"信号源给不出"。真实、且窄得多的
> 缺口是：这台机器的 LM Studio 后端一直没配 `control_endpoint`，所以
> **诚实地**回退成 `UNKNOWN`（这是设计对了，不是 bug）。已在
> `starlink-awaken/omostation-omlxc` 补上 mac-mini/y7000p 的 SSH control
> 配置，两边验证过 `loaded` 现在是真实值。教训见
> [[p78-triple-axis-diagnostic-pattern]]：断言"某能力不存在"前，要先读
> 三个 adapter 的实现，不能只测一个端点就下全局结论。

## Fix Pattern

### 1. 加一条 placement ↔ 后端清单的对账检查

放进 `omlxc doctor` 或启动自检里。漂移应该是**显式告警到具体条目**，
不是一句 `inventory_drop 38→16`。

### 2. `loaded` 状态要么接真实机制，要么诚实标 UNKNOWN——别猜

三个后端已经各自有正确的真实机制（见上面的订正），唯一会退化成 UNKNOWN
的情况是控制通道没配置（比如 LM Studio 的 `control_endpoint`）——这时
adapter 正确地报 UNKNOWN，而不是编一个 True/False 出来。落地新后端时
照这个标准: 有真实信号就用，没有就诚实标未知，别在两者之间瞎猜。

### 3. 诊断纪律：错误码要按字面读

`operation_failed` 字面意思是"操作失败了"，不是"派发错了"。
拿到错误码之后，先验证**目标本身是否存在**，再去找能解释它的机制。
详见 [[p101-sentinel-value-masquerading-as-progress]] 的反面教训段。

## Related

- [[p73-truth-driven-engineering-pattern]] — 声明/执行鸿沟母题
- [[p101-sentinel-value-masquerading-as-progress]] — 同批次，诊断陷阱
- [[p100-unified-memory-wired-ceiling]] — 同批次，物理约束
