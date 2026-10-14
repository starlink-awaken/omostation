# Mac 本地模型全面评测 v3 实施方案(r3)

> 任务目录: `/Users/xiamingxing/mac-local-ai-task-2026-10-12/`
> 原则: R2 基础设施全量复用、零重造;r3 只新增驱动层/引擎适配层/台账层;R2 产物(`reports/raw/r2/`)只读保留作对照。
> 机器: MBP M5 Max 128G / macOS 27。以下内存与时长除已给锚点外均为规划级估算,执行时以实测覆盖。

---

## 0. 总体架构(一图流)

```
r3_driver.zsh (外层串行, 按批次文件逐 arm)
 ├─ 1. 跳过判断: reports/raw/r3/<arm>/.done 存在 → skip
 ├─ 2. r3_drain(std|full)   ← 独占加载公平性: lms 全卸 + mlai stop qwen/glm + ollama 卸载; full 再加 oMLX
 ├─ 3. mem 门禁: free ≥ mem_required_gb + 8G 余量 (大鱼臂用臂级阈值, 取代一刀切 35%)
 ├─ 4. r3_load_<engine>()    ← lms / sushi / ollama / omlx 四适配器 (失败重试 1 次 → LOAD_FAIL.txt skip)
 ├─ 5. 健康检查: GET <base_url>/v1/models (3×30s 重试)
 ├─ 6. r3_run_arm.zsh: agent_eval.py 简单 20 题 + 困难 4 题 (逐题 .done 增量 + 逐题超时)
 │     全程 guarded_run.py + memguard.py 包裹; sushi 臂再加 mlai.py watch --stop-service-on-abort
 ├─ 7. bench: microbench.py --tiers <arm 级裁剪> --states cold,new,hit --context-limit
 ├─ 8. r3_unload_<engine>() → 写 .done → 追加 r3_run.log
 └─ 台账: reports/raw/r3/ctx_ledger.json (降档记录) + skip_ledger
报告: r2_report.py --root reports/raw/r3 (三张表) + class_compare.py (r3 根) + r3_report.py (汇总/速度榜/场景推荐/R2 对照)
```

**复用不改**: `agent_eval.py`、`microbench.py`、`memguard.py`、`guarded_run.py`、`mlai.py`、`r2_report.py`、`class_compare.py`、`r2_driver.zsh`/`r2_run_arm.zsh`(原样保留)。
**新增(6 个文件,全部在 bin/ 下)**: `r3_arms.tsv`、`r3_driver.zsh`、`r3_run_arm.zsh`、`r3_engine.zsh`(适配器函数库)、`r3_ctx_ledger.py`、`r3_report.py`。

---

## 1. Arm 总表与分批

命名: arm = 短 ASCII slug;lms identifier = `mlai3-<arm>`(换前缀避免与 R2 的 `mlai-*` TTL 残留碰撞;**TTL 从 7200 提到 28800**——大鱼臂单臂 4-8h,2h TTL 会在跑分中途被卸载,这是 R2 参数在 v3 尺度下的隐患)。

### 批次 0 · 验证批(傍晚, ~3-4h)——先打通四引擎中最廉价的三条链路
| arm | 引擎 | 加载方式 | base_url / model | ctx_load | 简单/困难 ctx | max_tok | mem_need | 预估 |
|---|---|---|---|---|---|---|---|---|
| spark4b | lms | `lms load spark-splash-4b --context-length 65536 --identifier mlai3-spark4b --ttl 28800` | :1234/v1, `mlai3-spark4b` | 65536 | 32768/65536 | 8192/16384 | ~6G | 1-1.5h |
| omlx-mythos | omlx | 常驻无操作(仅健康检查) | :8000/v1, 取 `/v1/models` 实名; **参照系, 不参与公平排名, 表内单列** | 部署值(记录) | 同左(engine_fixed) | 8192/16384 | 0 | 1-1.5h |
| ollama-gemma4-31b | ollama | `OLLAMA_CONTEXT_LENGTH=65536 OLLAMA_KEEP_ALIVE=4h ollama serve`(重启无头 serve) | :11434/v1, `gemma4:31b-mlx` | 65536 | 32768/65536 | 8192/16384 | ~26G | 2.5-4h |

### 批次 1 · 主力批 A(夜挂 1, ~13-18h, drain=std)
| arm | 模型 | 权重 | ctx_load | mem_need(权重+KV 估) | 预估 | 备注 |
|---|---|---|---|---|---|---|
| gemma4-12b | google/gemma-4-12b-qat | 7.15G | 65536 | ~10G | 1.5-2h | 未测新面孔 |
| qwythos-9b | qwythos-9b-...-1m-mlx-oq8-mtp | 10.7G | 65536 | ~14G | 1.5-2.5h | 1M 窗口仍按统一口径 32k/64k 测(公平), 原生窗口记录在台账 |
| bonsai2-27b | ternary-bonsai-2-27b-mlx | 8.6G | 65536 | ~12G | 2-3h | |
| qw38-27b | qwen3.8-27b-splash | 17.4G | 65536 | ~23G | 2.5-3.5h | R2 20/20+4/4 基准位 |
| sw15-qw38-27b | swift-1.5-qwen3.8-27b-splash | 17.4G | 65536 | ~23G | 2.5-3.5h | |
| qw38-27b-alis | qwen3.8-27b-alis-splash | 17.4G | 65536 | ~23G | 2.5-3.5h | |
| qwopus38-27b | qwopus3.8-27b-flash-1m | 18.5G | 65536 | ~24G | 2.5-3.5h | 未测, 1M 窗口同上 |

### 批次 2 · 主力批 B(夜挂 2, ~14-20h, drain=std)
| arm | 模型 | 权重 | ctx_load | mem_need | 预估 | 备注 |
|---|---|---|---|---|---|---|
| qw36-35b-a3b | qwen3.6-35b-a3b-splash | 20.95G | 65536 | ~27G | 2.5-3.5h | R2 速度王 154 tok/s, 速度榜锚点 |
| orn15-35b-a3b | ornith-1.5-35b-a3b-splash | 20.95G | 65536 | ~27G | 2.5-3.5h | |
| gemma4-26b-a4b | google/gemma-4-26b-a4b-qat | 15.6G | 65536 | ~21G | 2.5-3.5h | |
| gemma4-31b | google/gemma-4-31b-qat | 18.9G | 65536 | ~25G | 2.5-4h | R2 4/4 |
| nemotron3-nano | nvidia/nemotron-3-nano-omni | 26.1G | 65536 | ~32G | 3-4.5h | |

### 批次 3 · 大鱼批(夜挂 3-4, drain=**full**: lms 全卸 + sushi 双停 + ollama 卸 + **oMLX 也停**)
| arm | 引擎 | 模型 | 权重 | ctx_load | mem_need | 预估 | 备注 |
|---|---|---|---|---|---|---|---|
| gptoss-120b | lms | openai/gpt-oss-120b | 63.4G | 65536 | ~68G(MoE 滑窗 KV 极小, 估) | 4-6h | |
| sushi-qwen | sushi | `mlai.py start qwen`(先试完全驻留 ~67.8G) | 63G | 65536(部署定死) | ~68G | 2-3h | R2 未测; 驻留失败回退 `--ssd-budget-gb 44`(需求 ~47.4G), 台账记 resident_mode |
| qw3-coder-next | lms | qwen/qwen3-coder-next | 44.9G | 65536 | ~55G(80B GQA KV 估 4-8G@64k) | 5-8h | coding-next 基线欠账, dense 80B 解码慢 |
| sushi-glm | sushi | `mlai.py start glm`(先试完全驻留 ~90.1G) | 89G | 32768(部署定死) | ~91G | 3-4h | 128G 下极紧: 需 full drain + 用户应用最小化; 失败回退 ssd44, 台账记模式 |
| flashnext-rco(可选) | lms | qwen3.8-flash-next-gsq-rco | 84.5G | **32768**(降档) | ~90G | 6-9h | 10-06 实测 17-30 tok/s CPU 瓶颈; bench tiers 裁到 ≤32768; 默认挂起, 用户点头才跑 |

### 批次 4 · 扩展批(收尾, ~5-9h)
| arm | 引擎 | 说明 | 预估 |
|---|---|---|---|
| ollama-muse-30b | ollama | muse-glimmer:30b-mxfp8 32G, 未测 | 3-4.5h |
| ling30-tiny-retry | lms | ling-3.0-tiny-mlx: LOAD_FAIL(bailing_hybrid) **重试恰好 1 次**, 再败写终态 LOAD_FAIL | ≤0.5h |
| glm46v-flash | lms | **默认 SKIP_PARSER**(LM Studio 解析器不认 GLM XML 工具标签, R2 已证 0/20; 复测只烧时间)。除非给 LM Studio 换工具模板/jinja 后再入表, 表格中标注排除原因 | 0 |

未测全覆盖核对: qwopus✓ coder-next✓ gpt-oss✓ gemma4-12b✓ qwythos✓ sushi-qwen(全量)✓ sushi-glm(全量)✓ muse✓ ollama-gemma4✓; 可选: flashnext-rco、glm46v; 终态跳过: ling(重试后)。

---

## 2. r3_driver 设计(相对 r2_driver.zsh 的差异清单)

### 2.1 改动点(逐条)
1. **out-dir**: `reports/raw/r3/`,目录结构照抄 R2:`r3/<arm>/<题>/result.json`、`r3/<arm>__hard/HD0x/`、`r3/bench/<arm>.json`。R2 树只读。
2. **arm 来源**: R2 的内联 arm 列表 → 外置 `bin/r3_arms.tsv`(列: `arm,engine,model_key,identifier,base_url,api_key_env,ctx_load,ctx_simple,ctx_hard,max_tok_simple,max_tok_hard,mem_required_gb,drain_level,timeout_simple_s,timeout_hard_s,bench_tiers,bench_states,status,notes`)。驱动按 `--batch <name>` 过滤 `notes` 里的批次标签串行执行;`--dry-run` 只打印计划。
3. **ctx 策略**(见 §3): 简单档统一 `--context-limit 32768`;困难档目标 65536,由 arm 表的 `ctx_hard` 给出授权值;lms 的 `--context-length` 用 `ctx_load`(= 该臂会用到的最大 ctx)。
4. **引擎适配层**: R2 硬编码 `lms load/unload` → sourced `bin/r3_engine.zsh` 提供 `r3_load_<engine> / r3_unload_<engine> / r3_health_<engine> / r3_drain(std|full)`:
   - `lms`: `lms load <key> --context-length <ctx_load> --identifier mlai3-<arm> --ttl 28800`;卸载 `lms unload mlai3-<arm>`;placement 检查保留(`lms ps --json` 判 local, remote → `PLACEMENT_REMOTE.txt` 跳过, R2 规则原样)。
   - `sushi`: `mlai.py start qwen|glm [--ssd-budget-gb 44]`;endpoint `http://127.0.0.1:12345/v1`;鉴权 `--api-key-env LOCAL_AI_TOKEN`(token: `secrets/local_ai_token`);model 名从 `config/deployment.resolved.e1sd44.json` 读取(实现时提取, 不猜);ctx 部署定死(qwen 65536 / glm 32768), 台账记 `reason=engine_fixed`;卸载 `mlai.py stop qwen|glm`;**该臂运行期间挂 `mlai.py watch --stop-service-on-abort` 守 Sushi**(R2 语义)。
   - `ollama`: 无头 `OLLAMA_CONTEXT_LENGTH=<ctx_load> OLLAMA_KEEP_ALIVE=4h ollama serve`(先停 Ollama App/既有 serve);endpoint `:11434/v1` 无鉴权;卸载 `ollama stop <model>`(serve 保留, 常驻开销极小)。注意默认 keep_alive 5m 会在长题间隙把权重卸掉——必须设 env。
   - `omlx`: 常驻, load=健康检查 `GET :8000/v1/models` 取实名;unload=no-op(std)/手动步骤记录(full, 若无 CLI 停靠路径则与用户确认处置)。
   - `r3_drain(std)`: `lms ps` 逐个 unload + `mlai stop qwen` + `mlai stop glm` + ollama 运行中模型卸载;oMLX 保留(R2 可比条件)。`r3_drain(full)`: 再加 oMLX 停靠——≥45G 模型的硬前置。
5. **mem 门禁分档**: 主力/ollama 臂沿用 free≥35%(≈45G);大鱼/sushi-full 臂改用臂级 `free ≥ mem_required_gb + 8G`(35% 对 63-90G 权重无意义)。门禁只在加载前判一次,加载后不复查(否则大鱼臂必然自杀);运行期安全交给 memguard。
6. **LOAD_FAIL 重试**: R2 直接写 `LOAD_FAIL.txt` 跳过 → v3 先 `r3_drain(full)` + 等 120s **自动重试 1 次**,再败才写 `LOAD_FAIL.txt`(覆盖 ling 的"重试一次"要求和瞬时内存碎片场景)。
7. **逐题断点增强**: R2 是 arm 级 `.done` → v3 的 `r3_run_arm.zsh` 增加单题级跳过(该题 `result.json` 已存在且非 timeout/aborted 状态则跳过)。夜挂中断后恢复成本从"整臂重跑"降到"单题重跑"。
8. **每臂 bench 阶段**: eval 完成后同引擎 endpoint 跑 `microbench.py --tiers <bench_tiers> --states cold,new,hit --context-limit <ctx_load>`;`bench_tiers` 默认 `2048,8192,16384,32768,65536`,大鱼/降档臂裁剪(如 flashnext-rco 与 sushi-glm 到 `2048,8192,16384,32768`)。bench 失败不废臂——写 `bench/<arm>.json` 缺失标记, 汇总时标 N/A。
9. **白名单**: `agent_eval.py --allow-model <identifier>` 逐臂传入(fail-closed 语义不动);sushi/ollama/omlx 的 identifier 由适配器在加载成功后回填实际 model 名。
10. **超时**: 逐题包 `gtimeout`:简单 1800s/题、困难 3600s/题(用户给定);`agent_eval --request-timeout` 相应设 900/1800;臂级 wall cap `--arm-max-hours`(默认 10h)到点写 `ARM_TIMEOUT.txt` 收臂。
11. **批次边界通知**: 每臂结束 `osascript -e 'display notification ...'`(加性, 失败忽略), 提醒用户客户端/网关别名可能短暂指向被卸载模型。

### 2.2 新脚本 vs 参数化复用(汇总)
| 动作 | 对象 |
|---|---|
| 新增 | `bin/r3_arms.tsv`、`bin/r3_driver.zsh`、`bin/r3_run_arm.zsh`、`bin/r3_engine.zsh`、`bin/r3_ctx_ledger.py`、`bin/r3_report.py` |
| 原样复用 | `agent_eval.py`、`microbench.py`、`memguard.py`、`guarded_run.py`、`mlai.py`、`r2_driver.zsh`、`r2_run_arm.zsh` |
| 参数化复用 | `r2_report.py --root reports/raw/r3`;`class_compare.py` 传 r3 根。若 r2_report 标题/路径硬编码 "r2" 字样 → 最小补一个 `--label r3` 参数(预计 ≤5 行改动, 动手前先读源码确认) |

`r3_ctx_ledger.py` 职责: 汇集 arm 表申请值、引擎实际授予值(lms 回读 `lms ps --json` 的 ctx、sushi 从部署配置、ollama 从 serve env)、降档原因与实测驻留峰值(加载后/每 bench tier 后采 `memory_pressure` 一档), 产出 `reports/raw/r3/ctx_ledger.{json,md}`。

---

## 3. 宽 ctx 公平口径

### 3.1 定档规则(统一四步)
1. **简单档**: 全臂统一 `ctx=32768`(R2 的 4096/12288 混用废止)。
2. **困难档**: 目标 `ctx=65536`;授予值 = min(原生窗口, 内存可承载值, 引擎固定值)。
3. **内存可承载值**: `weights + KV(ctx_hard) + overhead(≈2G) + 安全余量(8G) ≤ 加载前空闲`。KV 估算: 27-35B GQA q4 档按 ~1-2.5G@32k / ~2.5-5G@64k;gpt-oss 系滑窗 KV 近零;**执行期以 microbench 各 tier 的实测驻留增量替换估算**(tier 间 Δmem 即实测 KV 斜率, 写入台账)。
4. **降档阶梯**: 65536 → 32768 → 16384 → 12288 → 8192;每次降档重走第 3 步;装不下且低于 8192 → 该臂困难档放弃, 记 `HARD_SKIPPED_MEM`。

### 3.2 各臂定档结果(规划值)
- 主力批 13 臂: ctx_load=65536 全部可容纳(最大 nemotron ~32G 需求 ≪ 45G 门禁)。
- coder-next: 65536(估 ~55G, full drain 后可行)。
- gpt-oss-120b: 65536(KV 近零)。
- flashnext-rco: 直接定 32768(90G 逼近上限 + CPU 瓶颈下 64k 无意义)。
- sushi-qwen 65536 / sushi-glm 32768: 引擎定死, 无降档空间, 回退路径只有 ssd44(性能特性改变, 单独记模式)。
- ollama 两臂: 65536(serve env 控制)。
- omlx-mythos: 部署值, `reason=engine_fixed`, 仅作参照。

### 3.3 降档记录格式(`ctx_ledger.json` 单条)
```json
{"arm":"flashnext-rco","tier":"hard","requested_ctx":65536,"granted_ctx":32768,
 "reason":"mem","evidence":"free_gb=96.2 weights_gb=84.5 kv_est_gb=4.0 margin_gb=8",
 "measured_resident_gb":null,"resident_mode":"full","ts":"2026-10-16T02:11:00+08:00"}
```
`reason ∈ {mem, native_window, engine_fixed, manual}`;sushi 臂额外 `resident_mode ∈ {full, ssd44}`。
**公平性口径声明**(写进报告头): 引擎固定 ctx 的臂(sushi/omlx)与降档臂在质量表中标注授予 ctx, 速度榜按同 tier 对齐比较;其余变量(题集、temperature、max_tokens 档内统一、独占加载、placement=local、超时策略)全臂一致。

---

## 4. 执行顺序与时长

**总时长估算: 55-80h 纯机器时间 ≈ 5 个夜挂批次(+白天补跑), 跨 3-4 天。**

| 夜 | 批次 | 内容 | 估时 | 前置 |
|---|---|---|---|---|
| N0(当晚) | 验证批 | spark4b → omlx-mythos → ollama-gemma4-31b;跑完立即 `r3_report.py` 验证三张表+台账落盘 | 5-7h | aictl mode create; 磁盘 ≥80G 空闲(ollama 权重); secrets/local_ai_token 可读; lms daemon 在线 |
| N1 | 主力 A | gemma4-12b → qwythos-9b → bonsai2 → qw38 → sw15 → alis → qwopus(由快到慢, 前半夜多跑几个) | 13-18h | N0 全绿 |
| N2 | 主力 B | qw36-35b → orn15 → gemma4-26b → gemma4-31b → nemotron3 | 14-20h | |
| N3 | 大鱼 1 | `r3_drain(full)` → gptoss-120b → sushi-qwen(完全驻留首试) | 6-9h | **用户整夜不用机**; oMLX 停靠路径确认 |
| N4 | 大鱼 2 | qw3-coder-next → (可选)flashnext-rco | 5-8h / +6-9h | |
| N5 | 收尾 | sushi-glm(full 首试, 失败回退 ssd44) → ollama-muse-30b → ling 重试 → 补跑断点 | 7-13h | |
| 白天 | 补跑 | 逐题断点恢复 + `r3_report.py` 增量出表 | — | |

**看门狗/守卫配置**:
- 每批外层: `guarded_run.py` 包 `r3_driver.zsh --batch <name>`(swap 守卫)。
- 全程: `memguard.py` 阈值不动(swap +2G warn / +4G abort / 压力 4 终止)。
- sushi 臂: 叠加 `mlai.py watch --stop-service-on-abort`。
- 驱动心跳: `reports/raw/r3/run.log` 逐臂逐题一行(时间戳/arm/题/状态/耗时), 断点续跑与事后复盘共用。
- 到点止损: `--arm-max-hours 10` + 逐题 gtimeout;夜里到 wall cap 自动收臂写 `.done`(部分完成标记 `PARTIAL`), 不硬杀正在写的题。

---

## 5. 报告生成

1. **三张表**: `python3 bin/r2_report.py --root reports/raw/r3`(简单/困难/bench 三表, 结构与 R2 同构;若标题硬编码 r2 → 加 `--label`)。
2. **分类对比**: `class_compare.py` 指 r3 根, 输出分类维度对比。
3. **总对比报告** `bin/r3_report.py` → `reports/r3_summary.{md,json}`, 结构:
   - **§0 公平口径与执行总览**: 口径声明(§3.3)、arm×引擎矩阵、ctx 台账摘要(申请 vs 授予 vs 原因)、LOAD_FAIL/skip 台账、memguard 事件数、运行时间线。
   - **§1 质量分层**: 简单 20 题总分+分类, 困难 4 题, 分层 S/A/B(建议 S 线: 简单≥19 且困难≥3);omlx 参照系单列不排名;glm46v 标注 SKIP_PARSER。
   - **§2 速度榜**: decode tok/s@8192(hit)、TTFT@32768、prefill tok/s、缓存收益(hit−new);per-tier 曲线表直接来自 `bench/<arm>.json`;标引擎与授予 ctx。
   - **§3 场景推荐**: 日常主力(质量×速度合成)、coding agent(困难分+工具回路完成率)、长上下文(32k/64k bench 衰减)、批量吞吐(decode@长 decode);每场景给 top3 + 一句理由。
   - **§4 R2 对照**: 双侧共有臂的 Δ 分数表, 头部大字注明"ctx 口径已换(4096/12288→32768/65536), 数字不可直接比, 仅看方向";新面孔标 NEW。
   - **§5 附录**: 完整台账、异常事件、sushi resident_mode 记录。
4. **增量出表**: 每批结束跑一次, 部分数据标 PARTIAL, 不等全量。

---

## 6. 风险与止损(逐类)

| 风险 | 检测 | 处置 |
|---|---|---|
| 大鱼加载爆内存 | 加载前 mem 门禁(free < mem_need+8G) | 不加载 → full drain + 等 120s 重试 1 次 → 仍败写 `LOAD_FAIL.txt` 跳臂;系统层兜底是 memguard abort |
| 运行中 KV 增长顶爆 | memguard(swap +4G abort / 压力 4) | 当前题标 `MEMABORT`, `r3_ctx_ledger` 记降档, 困难档按阶梯降 ctx 重跑该臂剩余题;同臂连续 3 次 MEMABORT → 收臂写 `PARTIAL` |
| 单题超时 | gtimeout 1800s/3600s | `result.json` 标 `timeout`, 继续下一题;不重试(超时本身是数据点) |
| 引擎崩溃(lms/sushi/ollama 挂) | 题间健康检查 `/v1/models` | 重载 1 次(引擎适配器重走 load);二连败写 `ENGINE_FAIL.txt` 收臂, 驱动继续下一臂;sushi 崩溃由 `mlai.py watch --stop-service-on-abort` 先止损 |
| sushi-glm 完全驻留失败(90.1G 装不下) | 启动后健康检查/驻留内存采样 | 回退 `--ssd-budget-gb 44`(需求 ~47.4G), `resident_mode=ssd44` 单列, 不与 full 模式混排名 |
| TTL 中途过期卸载(R2 隐患) | 健康检查 | v3 已改 `--ttl 28800`;若仍发生按引擎崩溃路径重载 |
| ollama keep_alive 中途卸载 | 健康检查 | serve env `OLLAMA_KEEP_ALIVE=4h`;仍发生则重载 |
| placement remote(R2 规则) | `lms ps --json` | `PLACEMENT_REMOTE.txt` 跳臂, 不重试 |
| 用户/客户端干扰 | — | 夜间批 + 批界通知;别名短暂指向被卸模型为已知可接受项 |
| 磁盘不足(ollama 权重 52G) | 预检 `df` | <80G 空闲则 ollama 批降级为只跑 muse 或先清理, 报告标注 |
| ling-3.0-tiny 复现 LOAD_FAIL | 加载失败 | 恰好重试 1 次(§2.1-6), 再败终态 `LOAD_FAIL`(bailing_hybrid 为 MLX 能力缺失, 不再尝试) |
| 数据污染/覆盖 R2 | — | r3 全部写 `reports/raw/r3/`;驱动启动时 assert r2 树未被修改(比对 mtime 快照, 简单 find+shasum 清单) |

---

## 7. 实施步骤(给执行 agent 的清单)
1. 读 `bin/r2_driver.zsh`/`r2_run_arm.zsh`/`agent_eval.py`/`microbench.py`/`r2_report.py`/`mlai.py` 源码, 校准本方案的旗标名与 model 名提取点(尤其 sushi 的 deployment.resolved.e1sd44.json、r2_report 是否硬编码 r2、ollama serve 管辖方式)。
2. 写 `r3_arms.tsv`(§1 三张表落数据)。
3. 写 `r3_engine.zsh` 四适配器 + drain 两档;`r3_drain(full)` 里 oMLX 停靠若无 CLI 路径, 停下来问用户。
4. 写 `r3_driver.zsh`/`r3_run_arm.zsh`(差异清单 §2.1 全部落实;先 `--dry-run` 输出计划人审)。
5. 写 `r3_ctx_ledger.py`、`r3_report.py`。
6. N0 验证批: spark4b 冒烟(单臂全程: drain→load→20+4 题→bench→unload→.done→报表), 修完问题再放 omlx/ollama 两臂。
7. 按夜挂计划放批;每晨跑 `r3_report.py` 增量出表 + 检查 `run.log`/台账异常。
8. 全量完成后出 `reports/r3_summary.md` 终版。

**不做的事(范围闸)**: 不测 1M ctx(1M 窗口模型仍按 32k/64k 统一口径);不加新题;不改 R2 脚本与 `reports/raw/r2/`;flashnext-rco 默认挂起待用户点头;glm46v 默认跳过除非换了工具模板。
