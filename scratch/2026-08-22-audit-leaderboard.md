# 织星算力池 — 全量注册审计榜单 (2026-08-22)

> 方法: 受控模式 — LM Studio 侧逐个显式加载(`-c 8192` 锁死上下文)→80token 请求→立即卸载;
> omlx-app 侧逐个请求, 依赖其后端内存守护自管加载/驱逐。
> 全程内存护栏 (每步检查真实可用内存, 不足即 SKIP), 零事故。
> 对比 08-20 榜单: 那轮裸打 API 触发 JIT 失控加载导致多次系统卡死, 本轮已根治。

---

## LM Studio 侧 (10 OK / 0 乱码 / 0 失败 / 3 SKIP)

| 排名 | Placement | 后端模型 | TTFT | 备注 |
|---|---|---|---|---|
| 1 | gemma-4-e2b | google/gemma-4-e2b | **107ms** | 响应最快 |
| 2 | vision | qwen3-vl-8b-instruct-mlx | 134ms | 视觉+文本都快 |
| 3 | ornith-9b | ornith-1.0-9b | 528ms | 带 Thinking 前缀 |
| 4 | qwen-3.8-27b | qwen3.8-27b-mlx | 814ms | 输出干净 |
| 5 | ornith-35b | ornith-1.5-35b-a3b | 818ms | 1.5 版工作正常 |
| 6 | gemma-4-31b | gemma-4-31b-it-mlx | 941ms | |
| 7 | coder-precise | qwopus3.6-27b-coder | 1.25s | |
| 8 | coding | qwopus3.6-27b-coder | 1.72s | 与 coder-precise 同权重 |
| 9 | reasoning | zai-org/glm-4.7-flash | 3.32s | 冷加载开销 |
| 10 | nemotron-omni | nemotron-cascade-2-30b-a3b | 4.73s | 冷加载开销 |
| — | coding-fast/coding-next | qwen3-coder-next (55GB) | SKIP | 内存闸门拦截 |
| — | mistral-medium | mistral-3.5-128b (75GB) | SKIP | 内存闸门拦截 |

## omlx-app 侧 (9 OK / 0 乱码 / 0 失败 / 4 SKIP)

| 排名 | Placement | TTFT | 备注 |
|---|---|---|---|
| 1 | coder-precise-local | **1.49s** | 唯一进入秒级 |
| 2 | vision-local | 8.27s | TTFT 含请求触发的模型加载 |
| 3 | ornith-9b-local | 10.1s | |
| 4 | gemma-4-e2b-local | 12.7s | |
| 5 | ornith-35b-local | 23.4s | |
| 6 | coding-local | 30.2s | |
| 7 | reasoning-local | 35.8s | |
| 8 | gemma-4-31b-local | 41.9s | |
| 9 | mythos-local | 58.5s | 最慢但输出正常 |
| — | qwen-3.8-27b / nemotron-omni / coding-next / mistral | SKIP | 内存不足 |

> ⚠️ 两侧 TTFT 不完全等价: LM Studio 侧是"加载完成后发请求"的纯推理首 token;
> omlx-app 侧 TTFT 含请求触发的冷加载 (它靠驱逐换驻留)。真实使用中 omlx-app
> 常驻模型会快得多, 本轮数值代表其冷启动成本。

## 关键结论

1. **零乱码零失败** — 08-21 发现的 qwen3.6-35b-a3b 乱码模型已清除后, 当前 19 个
   placement 全部输出正常中文, 没有新的坏模型。
2. **LM Studio 是冷启动之王** — 显式受控加载下 TTFT 全部 <5s; omlx-app 冷启动
   8-60s。双后端分工建议: LM Studio 承接交互式/冷启动场景, omlx-app 承接
   常驻后台任务 (其 idle_timeout 1800s + 驱逐机制适合长驻)。
3. **巨无霸模型在 128GB 机器上需要专属窗口** — qwen3-coder-next(55GB) 和
   mistral-medium(75GB) 在常规并行负载下基本无法安全加载, 只能在近乎空载时用。
4. **审计方法本身是成果** — 受控加载模式 (显式 -c + 立即卸载 + 内存闸门) 根治了
   08-21/22 反复系统卡死问题, scratch/safe_audit.py / safe_audit_omlx.py 可复用。

## 新发现的运维注意事项

- omlx-app 连续测试大模型会把 free 压到 ~2GB (模型驻留 + 30min idle timeout),
  审计后需重启 oMLX App 或等待超时。本轮结束时已重启, 内存恢复 83.7GB。
- daemon 周期探测会触发 LM Studio JIT 加载成 262144 失控上下文并驻留 1h
  (08-22 多次观察), 根因是 LM Studio defaultContextLength.type="max", 需在
  LM Studio GUI 中改为固定值。
