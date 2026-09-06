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

两个独立事实叠加：

1. **配置和后端各自演化，没有对账机制。** 后端模型清单是运行时事实，
   `backend_model_id` 是配置里的声明，两者之间没有任何一致性检查。
2. **后端的 `/v1/models` 不暴露加载状态。** oMLX App 返回的是标准 OpenAI
   模型列表（`id` / `object` / `created` / `owned_by` / `max_model_len`），
   **没有 `state` 字段**。而 omlxc 的探测逻辑依赖
   `model.state is ModelRuntimeState.LOADED` 来判定 `loaded`——
   信号源根本给不出这个信息，下游一切基于 `loaded` 的调度决策都建立在猜测上。

第 2 条是更根本的：**调度器要求的可观测性，后端没有提供。**

## Fix Pattern

### 1. 加一条 placement ↔ 后端清单的对账检查

放进 `omlxc doctor` 或启动自检里。漂移应该是**显式告警到具体条目**，
不是一句 `inventory_drop 38→16`。

### 2. 后端必须暴露加载状态，否则 loaded 就是假信号

要么后端加 `state` 字段，要么 adapter 用别的手段（进程内存、专用端点）
判定，要么**诚实地把 `loaded` 标成未知**，让调度器知道自己不知道——
而不是默认成 True/False 然后基于它做决策。

### 3. 诊断纪律：错误码要按字面读

`operation_failed` 字面意思是"操作失败了"，不是"派发错了"。
拿到错误码之后，先验证**目标本身是否存在**，再去找能解释它的机制。
详见 [[p101-sentinel-value-masquerading-as-progress]] 的反面教训段。

## Related

- [[p73-truth-driven-engineering-pattern]] — 声明/执行鸿沟母题
- [[p101-sentinel-value-masquerading-as-progress]] — 同批次，诊断陷阱
- [[p100-unified-memory-wired-ceiling]] — 同批次，物理约束
