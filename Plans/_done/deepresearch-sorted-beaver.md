# 评测窗口剩余时段推进计划:候选深调研 → 下载 → 入队测评 → 落地建议

> 状态:**终稿**(10-27 约 12:00)。scout-verify / scout-discover / scout-discover-2 / scout-local 四路调研全部交完(发现互相印证),Step 0–4、风险与回退、验证均已补齐。

## Context

- 用户 10-27 的要求:① 把 spark mf 的更正追加进 DECISIONS;② 深调研"还有哪些模型可以加入评测列表";③ 继续推进下载、测评和使用。plan mode 下只做只读调研,所有写操作在批准后执行。
- 现状(10-27 10:50 前后,均已核实):
  - benchq 09:45 随电脑重启正常退出(KEEP_WINDOW 在,aictl 仍为 create),队列 210/210 完成、未完成 0;无 HOLD/STOP;`STOP_AT=1793152800`=10-28 10:00:00。
  - 兜底还原脚本 `isolate_autorestore.zsh` 已于 10:13 重拉(pid 68861,10-28 10:02 触发);窗口态不变:magpie 隔离开、LM Studio JIT=false;multica daemon 停(未获批准不动)。
  - 本机 LM Studio 选中的 llama.cpp 已是 **2.65.0**(昨天档写的是 2.63.0),新臂跑在新运行时,需在 DECISIONS 记版本。
  - 资源:内存 free 约 75–78%,`/Volumes/Model` 可用 519GiB,GPU wired 上限 114688MB 在。
- 硬约束(用户铁律 / 项目铁律):
  - 窗口内禁编译等 CPU 重活(纯网络 IO 可以);不删模型、不重启机器(FileVault)、不改全局 provider、不 commit/push。
  - `brew install/reinstall/upgrade` 属全局变更,须先确认(相关项:独立 splash CLI `brew incoai/tap/splash`、`brew reinstall aria2`)。
  - benchq 必须从终端会话 nohup 启动(launchd 进程读 /Volumes/Model 会被 TCC 拦,DECISIONS 10-23)。
  - `agent_eval.py` / `benchq.zsh` 窗口内不改(保口径可比);改 `r3_arms.tsv` / `queue.tsv` 前先备份(`.bak-1027-<tag>`),并在 DECISIONS 追加记录。
  - 窗口实际可用到约 10-28 09:00(09:07 的 closeout 定时任务会 touch STOP),最后一条要在 08:00 前开跑。

## Step 0 — 批准后第一步:DECISIONS 更正行(只追加,不改原文)

背景:`DECISIONS.md:334`(10-26 10:41:08)把 c53 spark-splash-4b 的 mf 记成"0/6 全灭",依据是把 `stop_reason=final_message`(正常停止)当成失败标签。原始结果(`reports/raw/r3/spark-splash-4b-Pbase-k1__mf/MF0*/result.json`)是 MF01/02/04/05/06 PASS、MF03 因 32768 max_tokens 截断报 ERROR(wall 992s),即 5/6;`data_audit` 的 5/6 才对。

```zsh
cd ~/mac-local-ai-task-2026-10-12
D=reports/baseline/DECISIONS.md
[ -n "$(tail -c1 $D)" ] && echo >> $D
printf '%s\n' "[$(date '+%F %T')] 更正 10-26 10:41:08(DECISIONS.md:334)对 c53 的记录:spark-splash-4b mf 终数不是 0/6,而是 5/6 PASS(MF01/02/04/05/06 PASS;MF03 因 32768 max_tokens 截断报 ERROR,wall 992s)。原记录把 stop_reason=final_message(正常停止)误当失败标签;data_audit 的 5/6 才是对的(原始结果见 reports/raw/r3/spark-splash-4b-Pbase-k1__mf/MF0*/result.json)。'体积下限锚不认列'依据里的'mf 全灭'不成立;其余依据(easy 16/20、hard 1/4 严格 0/4)不变,是否认列留 closeout 复核。同批 mf 补档(c54-c57,已对原始结果核对):mellum 5/6(MF05 FAIL)、gpt-oss-120b 6/6、qwen3-coder-next 6/6(MF04/05 为 max_rounds 通过,严格 4/6)、ollama-muse-glimmer 6/6。" >> $D
tail -n 1 $D | cut -c1-140
```

只追加一行,不动 FINAL_BASELINE.md(由 10-28 closeout 统一复核出终稿)。

## Step 1 — 候选分级(三份调研汇总,已定稿)

| 候选 | 优先级 | 结论 | 关键门槛 / 风险 |
|---|---|---|---|
| Qwen3.8-27B 官方 + mmproj(unsloth UD-Q4_K_XL 17.56G + mmproj-F16 0.93G = 18.5G) | **P0** | 视觉锚,零引擎风险,本机 27B 系同格式已验证 | sha256 已拿到(见 Step 2) |
| Nanbeige4.3-33B(bartowski Q6_K 29.0G) | **P0**(带速度警告) | 稠密 33B、8 KV 头(GQA,KV 低效),ctx 512K;工具格式 Qwen3-Coder 式 XML,低风险 | 估算 7–12 tps(按本机 gemma-4-31b 类推);**Q1b 实测分档修正:easy+hard+mf 全链路约 2.3h,不是之前粗估的 5–8h,窗口内可以跑完整三档**;官方推荐 max_new_tokens 65536,远超评测上限 12288/32768,**TRUNC 是头号风险**;存活线 hard ≥14/16 |
| Sage-A1.5(InternScience Q4_K_M 21.7G + mmproj 0.9G) | **P0** | 基座勘误:**Qwen3.6-35B-A3B**(昨天档写 3.5)+ Agents-A1;qwen35moe 路径本机已实证可载;**本地已下的 mmproj 与官方 sha256 逐位一致** | 社区实测警报:难题可连出 30,000 思考 token 不出答案,需 reasoning_budget 约 10k 才截住,还会把分析写进 Python 注释无限续写;存活线 easy 20/20 或 hard≥3/4 或 tps>111 |
| KAT-Coder-V2.5-Dev(Kwaipilot,Apache-2.0,bartowski Q4_K_M ≈21.4G) | **P1** | qwen3_5_moe(与本机极速锚 ornith-1.5-35b-a3b 同底座),零引擎风险;A3B 速度档的质量升级候选 | 自报 SWE-V 69.4 / Pro 45.96 / TB2.1 41.02,但 HF 讨论 #12 社区自跑把排序翻转(Qwen3.6 73.4 / Ornith-1.0-35B 75.6);r/LocalLLaMA 有正面帖、YouTube 实测 token 用量 1/7;发布 3 个月无独立复现 |
| Groot-19B-A3B-261023(Apache-2.0,Q4_K_M 11.7–12.5G) | **P1/P2** | 有力档里最小;qwen3_5_moe 零引擎风险;质量若接近 ornith-1.5-35b-a3b 即 Pareto 改进 | 两份报告体积口径略有出入(11.66G vs 12.5G),下载前以文件树为准;团队来历不明(19 赞)、发布 4 天、全自报 |
| Qwen3.5-122B-A10B(mlx-community 4bit 69.6G,14 分片) | P1(对照) | ornith-122b 的同架构原版对照 + 原生 VL | MLX 转换时间 02-24 早于 03-05 的 chat_template 修复,装载前核对模板 |
| Flint(unsloth UD-Q4_K_XL 25.05G) | **P1(条件:先冒烟定路径,别再默认走 LM Studio)** | LM Studio 的 OpenAI 端点这条路证据不足:①UI 模板校验报错只是 UI 自带 JS Jinja 的问题(引擎侧 hex 转义 PR #30929 早在 2.63.0/b11803 就合了,2.65.0=b11908 更有),经端点走 `--jinja` 大概率能渲染,只是 UI 预览会报错[推断,未实测];②**真正的硬伤在解析层**:GLM 式 arg_key/arg_value 标签,LM Studio 是否解析未证实,而且本项目 harness 自己的兜底正则(`agent_eval.py:346` 的 `_TEXT_CALL`,只认 function=NAME 风格)同样不认这套标签——已亲验源码确认。DECISIONS 10-22 15:13 记过 mimo-9b 连 Qwen 式 XML 都要靠兜底才救回 | **新增可行路径:Splash 官方 README 把 Flint 的 unsloth UD-Q4_K_XL 明列为支持家族**(自动配对 DFlash2),而本项目 benchq 已通过 `r3_engine.zsh` 的 splash 分支接入独立 Splash 1.4.1(端口 8765),不需要新造引擎接入;但 Splash 对 GLM 式 arg_key/arg_value 标签的工具调用解析同样**未验证**,要先冒烟。备选:ollama(本机疑似已有 ollama 引擎的臂,待 scout-local Q1a 确认接法)、或原生 llama-server(需 grammar + `--reasoning-budget` + 4 个 stop token;社区实测无约束 85 次工具调用失败 41 次,加约束后 0/50,但 benchq 目前没接过这条路径,窗口内不建议新造)。默认必思考、无开关,推荐 temp 1.0(评测默认 0.2,行为未验证);存活线 easy ≥19/20 且 tps>111 |
| LFM2.5-24B-A2B(LiquidAI,官方 GGUF Q4_0 16.7G) | P2 | 速度+体积极值档(自报 184 tps @ M5 Max) | 工具格式是 Pythonic `[{...}]`(本机解析链未验证);许可非 OSI;先冒烟再下大档 |
| Kolibri-1(Aleph Alpha,bartowski Q4_K_M 49.76G) | P2 末位 | 编码-代理指标全面低于 Qwen3.6-35B-A3B 且体积 2.4×,接近被支配 | llama.cpp PR #30673(10-17 合入),2.65.0 应可载仍需加载冒烟;MLX 路径 PR #1945 未合 |
| Nemotron-3.5-Lightning-30B-A3B(NVIDIA) | P2(不占下载预算) | NVIDIA 自家表里编码-代理全面输 Qwen3.6-35B-A3B(SWE-V 51.56 vs 70.12) | nemotron_h 族本机零风险;qwen3_coder XML;社区 114 tps @ M5 Max |
| Nemotron-3.5-Super-VL-120B-A12B(lmstudio-community Q4_K_M 70.1G) | **P2 / 不测** | AA 独立智能指数 26(低于 Qwen3.6-35B-A3B 的 32,仅高于 gpt-oss-120b 的 24),AA Terminal-Bench 0%;被 ornith-122b 与 gpt-oss-120b 夹击;视觉唯一性不成立(更便宜的 Qwen3.8-27B+mmproj 已在列) | 视觉路径其实已支持(PR #30520 在 tools/mtmd 新增 `nemotron-omni.cpp`,补上昨天档"未验证");若用户坚持要测,取 lmstudio-community Q4_K_M,**不要 NVFP4** |
| Step-3.7-Flash(201.4B)/ MiniMax-M2.7(228.7B) | P2 / 不测 | 只有 2–3bit 能进门禁,自报数字仍被 Qwen3.8-27B 支配且体积 7–8× | MiniMax 工具格式走 PEG(master `chat.cpp` 有 `peg-minimax-m3` mapper,2.65.0 是否含未验证) |
| nerkyor Coder390(点名条目③) | **P1(用户 10-27 拍板:排 easy+hard,不排 mf)** | 卖点正是"修过度思考/空答",对上本库 hard 档 TRUNC 病灶(QUALITY.md §2.3 第 3 条);easy 档对头部已饱和,区分度看 hard | 训练数据未公开、无 SWE-bench/Terminal-Bench 数字、无独立复现、全自报;GGUF Q4 LynnStyle 19.6G / Q6_K 23.1G / Q8_0 29G(内嵌 MTP);工具模板推断沿用 Qwen3.8,需冒烟;判据 = hard 的 TRUNC 率是否真低于 swift-1.5-27b(hard TRUNC×5) |

### 本机亲验补充(直接核过原始记录,非转述)

1. **Flint 判死的依据已亲验**:`reports/QUALITY.md:43` 记着 glm-4.6v-flash easy 0/20 的根因是"LM Studio 不解析 GLM 原生 XML 工具调用标签(tool_call / arg_key / arg_value 三件套),残留在 content 里",并注明"不是对该模型能力的评价"。Flint 的 chat_template 用的正是同一套标签,所以经 LM Studio 极可能重演 0/20,而这个 0/20 也说明不了 Flint 本身的能力——这正是它只能走 llama-server/ollama 路线的原因。
2. **Coder390(条目③)的价值比"观察项"更实**:QUALITY.md §2.3 第 3 条写明"主要失败模式是失控思考,不是做不对"——hard 档 2/4 以下的模型,失分几乎都是 ERROR(截断@32768),单次回复写满 32K token 还没出工具调用。Coder390 的主打卖点正是修"已有答案仍重推到 94K 空答",直接对上这个病灶。风险没变(数据未公开、无独立复现、全自报),但**若只挑一个社区微调来赌,这个赌注有本机数据支撑**,不是纯凭名字好听。
3. **KAT / Groot 都是 A3B 档,评的时候别只看 tps**:QUALITY.md §2.3 第 4 条:MoE-A3B 类(ornith、qwen3.6-35b-a3b)快 3–10 倍(173、140 tps),但困难档里正是它们最容易失控思考,"快不等于省时间,任务时间优先于 token/s"。所以这两个的存活线要按**墙钟任务时间 + hard 通过率**判,不能只因为 tps 高就留。

### 点名条目①:已核完,要享受 82.5G 常驻必须重下 111.3G,但有更便宜的第一步

scout-local 数了盘上分片(`/Volumes/Model/hf-cache/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/766911a6…/UD-Q4_K_XL/`):四分片是 00001(10MB,头/收尾小片)+ 00002(49.86G)+ 00003(49.38G)+ 00004(12.09G),**没有独立的 n-gram/PLE 表分片**——unsloth 这个打包把 PLE 表跟权重混编在 00002/00003 两片 49G 里,运行期靠 Splash 的 `--ple-memory`(帮助原文:"RAM row cache of the PLE n-gram table … rest from the SSD")做 SSD 流式。而 `R3_SPLASH_EXTRA` 这个唯一能传 `--ple-memory/--expert-memory/--max-cache-disk` 的口子,**评测链从来没设置过**(全 bin 目录 grep 只在 r3_engine 注释里出现过)——splash14-flash-next 两臂一直跑的是默认内存策略,这正是它 free 从 81% 掉到 7%、门禁被校准到 96/101G 的原因。

结论:社区 Vardaan97 的重打包(把 PLE 表拆成独立分片,常驻从 111G 降到 82.5G)**不是"换个加载配置"就能享受的**,现有 blobs 拼不出那套新文件树,要用就得完整重下 Q4-PLE4(111.3G)。好消息是本机 `/opt/homebrew/bin/splash` 已经是 **1.4.1**(满足 Vardaan97 要求的 ≥1.4.0),`r3_engine.zsh:110-131` 的 splash 分支本来就走这个独立 CLI(端口 8765,`--offline` 只读 HF cache),不需要新造引擎接入。

**更便宜的第一步**:先给现有 splash14-flash-next 臂设一次 `R3_SPLASH_EXTRA`(比如带上 `--ple-memory`),看默认策略下压不下来的常驻能不能靠这个旋钮压低——这比重下 111.3G 便宜得多,而且旋钮本来就在,只是从来没用过。值不值得花 111.3G,取决于:①HD03/04 的 Metal OOM 是否真因常驻口径(111G vs 82.5G)而不是别的(比如 32K KV 本身);②下载要花多久(待 scout-local Q3 的实测速率)。

### 点名条目②:已核完,基本是冗余,不建议单独下

scout-local 直接查了盘:本机 `ornith-1.5-35b-a3b-splash`(`/Volumes/Model/LMStudio/ezoushen/ornith-1.5-35b-a3b-splash`,19.51G,yuzu 格式)**目录里本来就带一个 `draft/` 子目录(0.45G)**,manifest 记着 `architecture: DFlash2DraftModel`、6 层、来源 `incoai/Qwen3.6-35B-A3B-DFlash2@8e713508`。`r3_engine.zsh:82` 加载这条臂时只传了 `--context-length --identifier --ttl -y`,没有任何 speculative 参数——也就是说,111 tps 那个极速锚成绩,用的就是这个**内嵌草稿**,不是无草稿裸跑。

`felkhayer/Ornith-1.5-35B-A3B-DFlash2-Splash`(1.05G)跟它是同一条技术路线的另一次打包(权重同样源自 jzinno 的社区草稿,felkhayer 只改了 config 的 block_size 16→8、sliding_window 4096→2048 以过 Splash 校验),没有证据表明它比本机已内嵌的那个更快或接受率更高。**换上去基本是冗余**,而且要换也不轻松:LM Studio 内嵌 splash 运行时(1.3.0)的 `serve-native` 命令行**没有外挂草稿的参数**(草稿只能来自 yuzu 包内的 `draft/` 目录,是打包时的 manifest 契约);`lms load` 层面倒是有 `--speculative-draft-model` 系参数,但对 yuzu/splash 后端是否透传**无文档、未验证**。真要换,要么重新打包 yuzu(把 draft/ 换掉),要么走独立 splash CLI(本机 brew 里已经装着 1.4.1,大概率不用重装,待确认 `/opt/homebrew/bin/splash` 与 `brew incoai/tap/splash` 是不是同一个东西)。

**结论:不建议为这 1.05G 单独开一条臂**,除非之后有证据表明 felkhayer 的草稿接受率明显高于 incoai 内嵌的那个(目前没有)。

### 排除清单(一句话理由,scout-discover / scout-discover-2 一致)

Raon-1-mini-preview(llama.cpp 上游无 raon1 架构,PR #31107 已关闭未合,转监控)· Underdog-Saluki-27B-1.0(不是新模型,只是 Qwen3.8-27B 的 IQ2-mix 极限量化 7.89G)· Qwen3.8-Flash-Next-Gyro-Coder(需 agentionai 定制 llama.cpp,TQ 格式 LM Studio 不可载,且被本机 flashnext-gsq-rco 支配)· Granite-switch-4.1-30B(决策/语音组合模型,非编码)· Hy-Memory-30B-A3B(记忆写入器组件)· Carbon-X(DNA/基因组)· Tess-4.5-27B(Qwen3.8-27B 微调,无独立证据)· AREX-2 / LBS-27B / clef / JEV-27B-VL(27B/9B 特定任务后训练,非编码 agent)· Ling-3.0-flash 与 Ling-3.0-flash-Sante(bailing_hybrid,llama.cpp 无此架构)· Xing4.0-29B-A4B(custom_code 新架构、无 GGUF;**若社区出 GGUF 值得回看**)· JetBrains Qwen3.8-3.6-27B-blend(官方 50/50 权重插值,P2 备选未入短名单)· 以及 Step-5/Hy4/Laguna-M.1/Kimi-Linear/LongCat/Muse-Spark-Open/Beam-1.0/Inkling/MiMo-V2.6-Pro/MiniMax-M3 等体积或代际不可行项。

**Qwen4 截至 10-27 仍未发布**(组织页 / collections / GitHub 三处核验),首日监控照旧。

**纪律性结论**:所有新候选的能力数字全是厂商自报,无一有 SWE-rebench 级独立复现;SWE-rebench 独立口径下 Qwen3.6-35B-A3B 仅 24.7、Qwen3.6-27B 31.2,与各家自报差距极大——继续坚持"以本机同口径实测为准"。

### 两条要写进制度的发现

1. **DFlash2 有一道本机自己的许可闸门,加任何新草稿前先查**:`bin/load_report.py:123-130` 把 DFlash 当受限项——Qwen 日志里出现 `[dflash]` 字样会直接判 FAIL("its license gate is closed"),GLM 必须带 `--no-drafter`;Sushi 侧的 manifest 显式 `exclude DFlash2/`;`config/deployment.resolved.e1d.json` 的 glm profile 里有 `dflash_license_approved_for_intended_use / dflash_license_evidence_path / enable_dflash` 三个键(scout-local 只读了键名,没读值)。**注意**:现有 splash14-* 与 ornith-splash 臂本来就一直在用 DFlash2(自动配对/包内嵌),而且跑出了正常成绩,说明这道闸门大概率只作用于 Sushi/GLM 那条路径,不拦 Splash/benchq——但这条推断没验证过,真要新增或替换任何 DFlash2 草稿前,先读一眼这三个键的值和 load_report.py 的判定分支,别默认它不拦。
2. **启用投机解码的臂,tps 不能跟无草稿的臂直接比**:Splash 官方文档明确投机解码在采样口径下分布无损(temp 0.2 的通过率期望不变),但速度会被草稿显著抬高(官方自报 M5 Pro:27B 从 llama.cpp 16 tps 到 Splash 74 tps;35B-A3B 从 69 到 175)。本机已有先例:swift-1.5-27b-splash 回路 51 tps 对探针 38.6 tps 就是两套口径。BENCHMARK.md 第 6 行的记录字段本来就含"MTP/drafter",DECISIONS 10-15 也有"DFlash2 关闭"的先例标记——建议沿用:**凡是启用投机的臂(不管 Splash 自动 DFlash2 还是 llama.cpp draft-mtp),在 r3_arms.tsv 加一列 spec 标记,bench 记录里落 drafter 字段**;顺带把 harness 的 `text_call_fallback` 计数(agent_eval.py:448,已亲验)也记进口径,因为它同样是"引擎解析缺口靠 harness 兜底"的代偿,不记就等于把解析问题藏进了通过率里。

## Step 2 — 下载方案(已定稿,Q3 实测)

**带宽是硬顶,不是 CDN 的问题**:对 hf-mirror(→cas-bridge.xethub.hf.co,CloudFront)和 ModelScope(→cdn-lfs-cn-1.modelscope.cn,Tengine/OSS)两条完全无关的 CDN、直连与走 7890 代理、单连接与 4 并发,全部实测下来聚合速率都钉在 **~3.4MB/s**(约 27–28Mbps)。加并发、换源、走代理都不提速——瓶颈是本机线路总带宽,"xethub 限单连接"这个说法不成立,已证伪。换算:Nanbeige 剩余 21.2GiB≈1.8h;Sage 主文件 21.7GB≈1.8h;Qwen3.8-27B UD-Q4_K_XL+mmproj 18.5G≈1.6h。

**aria2c 没坏,10-26 那次根因归因是错的**:DECISIONS 记的"aria2c(链接 OpenSSL 4.0.0c)对 xethub CDN 握手失败",今天用同一条 URL、同一套 aria2c 1.37.0 + OpenSSL 4.1.0 复测,**7/7 全部成功**(含 `--dry-run` 走完整个 302→CDN 链路);openssl s_client 用默认组(协商 X25519MLKEM768)、强制 X25519、强制 X25519MLKEM768 也都握手成功。"ClientHello 过大被中间设备丢弃"这个假说没被证实(错误原文是 protocol error 不是超时,且今天同栈全通),更像是 CDN 边缘/链路的时段性劣化(10-22 也发生过一次,中间夹着成功轮次)。**结论:不用换下载器、不用调 TLS 组、不用 brew reinstall aria2;再遇到批量失败,当场换源或换下载器即可,别预设这是永久性问题。**这是 DECISIONS 里第二处事后被推翻的判断(第一处是 spark mf 的记数错误,这次是根因归因错误)。

**Nanbeige 的续传有个坑,别踩**:`bin/hf_fetch.py`(标准库、8MiB 块 × 12 线程 + IP 轮转、块级断点续传、sha256 校验后原子改名)总体仍是首选下载器,但它**探测到目标目录有 `.aria2` 文件时,会把 `.aria2` 和目标文件一起删掉重下**(`hf_fetch.py:259-262`)。Nanbeige Q6_K 已经有 28.98% 进度(aria2c 的续传文件),**这一件必须继续用 `aria2c -c` 续传,不能换成 hf_fetch.py**,否则白白丢掉已下的 8.4G(约 40 分钟带宽)。其余没有 `.aria2` 残留的候选,继续用 hf_fetch.py。

**ModelScope 可作备用源,但不会更快**:bartowski/Nanbeige、InternScience/Sage-A1.5、unsloth/Qwen3.8-27B-GGUF、unsloth/flint-GGUF 在 ModelScope 上都有镜像(HTTP 200),字节数与 sha256 跟 hf-mirror 完全一致(Nanbeige Q6_K 29,016,857,728B,`b11c9f21e69d896a…`)。速率同样卡在 ~3.4MB/s 本机带宽,价值只在"多一条可交叉校验 sha256 的备用链路",不是提速手段。

**下载与评测可以并行,不必串行**:benchq 的门禁只看内存(`r3_free_gb` ≥ 臂表第 10 列 + 8),不看磁盘 IO;aria2c/hf_fetch.py 本身几乎不占内存。所以完全可以一边让 benchq 跑当前模型的评测,一边后台 nohup 下载下一个模型——这对排期很关键(见 Step 3)。

- **通用规则:含 NVFP4 张量的 GGUF 在 Apple Silicon 会回退 CPU**(llama.cpp master `ggml-metal-device.m` 的 `ggml_metal_supports_mul_mat_op` 对 `GGML_TYPE_NVFP4` 返回 false,MUL_MAT / MUL_MAT_ID / GET_ROWS 均不支持,10-15 后无补),一律选常规 K-quant。本机 bolt-74b-a9b(5.3 tps、llama-server CPU 1135%)即此因,按 BASELINE_ANCHORS 第 0 步应归为格式问题而非能力问题(bolt 已于 10-26 删除,是否用 K-quant 重测留用户定)。
- 已核实的 sha256 / 大小(hf-mirror HEAD 均 200):
  - Qwen3.8-27B:unsloth UD-Q4_K_XL 17,559,178,144B `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`;mmproj-F16 927,607,488B `cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e`(另有 mmproj-BF16 931,146,432B 可选)
  - Nanbeige4.3-33B(bartowski):Q6_K 29,016,857,728B `b11c9f21e69d896a1c20b12f88174f069e0e15623140733a49ff8e47c5541fbc`;Q5_K_M 25,073,368,192B `2b10206e3ba0a6a8f88b8c23fdbc49e9efccb3331564e711e4fc2901b18288cc`;Q4_K_M `2cef79855ca47ee6571e166db32a07089e34f3cf78e0397b262d124ddb814c37`
  - Sage-A1.5(InternScience):Q4_K_M 21,713,463,520B `a64fe0bbf936db3eb54f66f142c2b2eee569ade83673649f549a21daef8ca395`;mmproj 899,282,880B `51cd4410057e8dc4152ca771a726fbfb34856f047e7049018c757d42ddd481f2`(**本地已下完的 mmproj 与此逐位一致**)
  - Flint:unsloth UD-Q4_K_XL 25,054,688,704B `63c2ecc461ca545134b670c660e76fa20f47240f8d39b6510bfd21c4dd6e072f`;lmstudio-community Q4_K_M 24,166,841,184B `20c89707f762af73f0840f7b2c2911193617e60cac2ae30a96cb2cda7c15927e`
  - KAT-Coder-V2.5-Dev / Groot-19B-A3B:**sha256 待补**(下载前用 HF API 的 tree 接口取)
  - Nemotron-3.5-Super-VL(lmstudio-community Q4_K_M,两片):39,730,340,416B `7e8ccf2e…ee0fb214` + 30,372,951,904B `6d256028…3628ed02`(scout-verify 只给了首尾片段,下载前用 HF API 补全)
- 下载完成判据:文件大小 + LFS sha256 全对上(不能只看完成标记);下载目录新建,脚本放别处。

【待填:Q1b 的各 tier 实测耗时回来后,在 Step 3 补"能塞进窗口的候选组合"排期数学。初步估算(纯下载时间,按 3.4MB/s):核心六件(Qwen3.8-27B+mmproj 18.5G、Nanbeige 剩余 21.2G、Sage 21.7G、KAT 21.4G、Groot 12G、Coder390 19.6G)合计约 114G ≈ 9.4h;加 Flint(25G)≈ 11.4h;再加 Qwen3.5-122B(69.6G)≈ 17.1h,已经逼近窗口剩余总时长(约 21h),几乎不给评测留时间——**122B 这一件大概率要砍掉或延后**,待 Q1b 实测耗时数据确认后跟用户敲定】

## Step 3 — 入队与测评(已定稿)

**新臂的标准流程**(Q1a/Q1d 实证):
1. 文件落盘到对应位置:LM Studio 走 `/Volumes/Model/LMStudio/<org>/<repo>/<file>.gguf`,mmproj 放同目录即自动配对(qwopus 目录实证);Splash 走 `/Volumes/Model/hf-cache/hub/models--<org>--<repo>/snapshots/<sha>/<variant>/`;Sushi 走 `config/deployment.resolved.e1d.json` 里 profile 指定的路径。**LM Studio 不需要 `lms import`/注册,文件落盘即自动索引**——反面提醒:aria2 预分配的残file也会被索引成"模型"(Nanbeige 现在 29.02G 的"模型"其实是 28.98% 半成品),别被 `lms ls` 骗了。
2. `r3_arms.tsv` 加一行(14 列,格式见下方"已确认"节);col3(model_key)用 `lms ls` 里实际显示的 key。
3. ctx4096 冒烟(DECISIONS 10-20 10:55 先例):小上下文试加载 + 一轮工具调用,确认能跑通、工具调用格式能被正确解析(尤其 Flint/Coder390 这种格式存疑的),再排队列。
4. `queue.tsv` 追加标准套餐(实证模板,c1/c2/c3/c5 批模式):`easy(base,k1,-,-)` + `hard(base,k1,-,-)` + `sp bench(proto=sp,k1)`;强臂可再补 `hard/mf k2/k3`(easy 不重复);64K 臂单独一行 easy 只跑 MIX04;mf 可写 MF01-06 或 `-`(全跑)。**同臂条目要连排**,否则 benchq 反复装卸。
5. 改 `r3_arms.tsv`/`queue.tsv` 前先备份(`.bak-1027-<tag>`),改完在 DECISIONS 追加一行记录。

**已确认**(Q1a/Q1b/Q1c):
- `queue.tsv` 7 列 TAB:`id | arm | tier(easy|hard|mf,另有 bench=速度复测) | proto | k | body(JSON 或 -) | tasks(空格分隔或 -)`,所有列非空;benchq 取"文件顺序第一条无 `done/<id>` 的行",追加到末尾即可,不会重排。现状:非注释 208 行全部 done(另有 2 个孤儿 done:c6-north-mini-1.0-easy/hard),未完成=0,累计 15 个 LOAD_FAIL;末条 c57。
- `r3_arms.tsv` 14 列:`臂名 | engine | model_key | identifier | base_url | api_key_env | model_id | ctx_load | ctx_hard | mem_required_gb | drain_level | bench_tiers | batch | notes`。engine 五种:`lms`(llama.cpp GGUF/MLX/yuzu 都走这个,`lms load`,identifier 一律 `mlai3-` 前缀)、`ollama`(curl POST `http://127.0.0.1:11434/api/generate` 触发加载,`keep_alive:8h`,卸载 `keep_alive:0`;base_url 仍是标准 `/v1`)、`omlx-resident`(常驻直测,不 load/unload)、`sushi`(`mlai.py start/stop`)、`splash`(独立 splash CLI 1.4.1,前台进程后台化)。ctx_hard 有降档阶梯 65536→32768→16384→12288→8192,每笔记 ctx_ledger。
- 内存门禁:`r3_free_gb`(memory_pressure 的 free% × hw.memsize)≥ 第 10 列 + 8;不够先 `stray_unload` + 20s 复测;装载失败重试 3 次、冷却 300s,之后标 LOAD_FAIL;跑动中 rc=3(swap+4G guard)冷却 150s 重试;`foreign_busy`(有非 `mlai3-` 本地模型在生成)挂起不占重试,`stray_unload` 卸 idle 的非 `mlai3-` 本地模型。
- **当前 free≈53%(约 68G),比一小时前低了 ~22%,原因是日常栈 llm_gateway 在 10:59 前后重新拉起了 `swift-1.5-qwen3.8-27b-splash`(RSS≈17.2–18.1G,pid 43724)——不是评测在吃内存,是日常栈自己的行为**。它的 identifier 不带 `mlai3-` 前缀,benchq 重启后会按 foreign_busy/stray_unload 规则处理(idle 就卸,在生成就等)。mem_required≥88G 的臂现在进不去(free 68G < 88+8)。
- benchq 重启命令(RESUME.md 原文):`cd ~/mac-local-ai-task-2026-10-12 && nohup zsh bin/benchq.zsh > logs/benchq.nohup 2>&1 & disown`。**已确认从本类 agent 会话启动不会踩 TCC 坑**(DECISIONS 10-23 有 pid 97490 连跑 4 天的先例,且本次会话实测 ls/du/读 `/Volumes/Model` 全通)。
- 窗口实际可用到约 10-28 09:00(09:07 的 closeout 会 touch STOP),最后一条要在 08:00 前开跑。

**实测耗时**(Q1b,195 个 `meta/*.json` 样本,按臂的 easy 档 tps 分档;数字是"整个 tier 跑完"的墙钟均值,不是单题):

| tps 档 | easy(20题) | hard(4题) | mf(6题) |
|---|---|---|---|
| >80 | ~5min(3-7) | ~14min(2-42) | ~2min(1-2) |
| 40-80 | ~22min(0-48) | ~34min(0-98) | ~8min(2-20) |
| <40 | ~42min(0-90) | ~82min(0-150) | ~14min(1-61) |

**据此重排各候选耗时**(比一小时前那版"排期警报"乐观,因为当时用的是粗估,现在有真实分档数据):

| 候选 | 下载 | 评测 | 备注 |
|---|---|---|---|
| Ling-3.0-tiny Q8_0 GGUF | **0h(已在盘上,完整)** | 速度未知,先冒烟定档;bailingmoe3 是小 MoE,大概率 >80tps → easy+hard ≈ 19min | **免费收尾项**:现臂 key 指向 MLX 变体(bailing_hybrid LOAD_FAIL),换成 GGUF key(`ling-3.0-tiny`)即可冒烟 |
| Nanbeige4.3-33B Q6_K | 1.8h(剩 21.2G,**必须 `aria2c -c`**) | 稠密 33B,估 7-12tps → <40 档:easy+hard+mf ≈ 42+82+14 = ~2.3h(慢的话到 4h) | 比之前粗估的"5-8h"乐观很多;用户既定验收线 hard≥14/16 |
| Sage-A1.5 Q4_K_M | 1.8h(21.7G,mmproj 已在且校验一致) | qwen35moe A3B,大概率 >80tps → easy+hard+mf ≈ 21min | 盯 30K 思考循环(社区实测警报) |
| KAT-Coder-V2.5-Dev Q4_K_M | 1.8h(21.4G) | qwen3_5_moe A3B,大概率 >80tps → ~21min | — |
| Groot-19B-A3B Q4_K_M | 1h(12G) | qwen3_5_moe A3B,大概率 >80tps → ~21min | 最便宜的新下载 |
| Coder390 Q4 LynnStyle | 1.6h(19.6G) | Qwen3.8-27B 稠密微调,大概率 40-80tps → easy+hard ≈ 56min | 用户已拍板只排 easy+hard |
| Qwen3.8-27B 官方+mmproj | 1.6h(18.5G)——**但 hf-cache 已有 `unsloth/Qwen3.8-27B-GGUF` 15.33G,先核对是否同一件/是否够用,别重复下载** | 40-80tps → easy+hard ≈ 56min | 文本能力已被 qwen3.8-27b-splash/swift-1.5-27b/qwopus 三条同底座臂覆盖(全部 easy 40/40);真实价值是给"视觉锚"备料,而视觉锚专项题库(≥12题/3类)窗口内建不完。**建议:可以下载备料,但不必在本窗口排文本复测**,省时间给更有区分度的候选 |
| Flint(条件) | 2h(25G) | 速度不确定(32K 上下文衰减到 ~32tps,可能落 <40 档)→ easy+hard ≈ 2.1h,**前提是冒烟能过** | 先冒烟(Splash 路径优先,其次 ollama——已确认 ollama 是现成引擎,`r3_engine.zsh:88-95` 有完整接法),不过就放弃 |
| Qwen3.5-122B-A10B(P1对照) | 5.7h(69.6G) | 40-80tps(对标 ornith-122b)→ easy+hard+mf ≈ 64min | 下载是最大头;纯对照价值(不是升级),窗口紧张时可砍 |

**排期结论**:下载是串行硬约束(带宽 ~3.4MB/s 封顶,并发不提速),但**下载和评测可以并行**(门禁只看内存不看磁盘 IO)。核心六件(Ling 免费 + Nanbeige + Sage + KAT + Groot + Coder390)总下载 ~8h,总评测 ~4h(Nanbeige 2.3h 是大头)。流水线跑下来(下载下一件的同时评测上一件),墙钟约等于"总下载时间 + 最后一件的评测时间" ≈ **9h**;窗口还剩约 21h(现在 ~11:50 → 明天 09:00),**富余约 12h**,够再塞 Flint(~4.5h:下载+冒烟+评测)或 Qwen3.5-122B(~6.7h:下载+评测)其中一个,但两个都塞不下(11.2h,理论上刚好卡在富余线上,没余量应对装载失败重试)。**建议:Flint 和 Qwen3.5-122B 二选一,或都放到"核心六件提前跑完还有富余"的机动位,不预先承诺。**

**要主动说清楚的冲突**:`PLAN_WINDOW_1019-1028.md` 的 Phase 4(10-27→10-28 10:00)原文写"不再启动新条目"。这次需求跟它冲突——不是不能做(10-26 09:15 你授权 P0 下载时已突破过类似约束,DECISIONS 331),但这次范围更大(KAT/Groot/Coder390/Flint 都是当时没有的新候选),按你这次的明确指令推进,同时如实标出冲突;要改主意、把这批推到窗口后,现在还来得及。

**要提前打招呼的局限**:hard 档只有 4 题(HD01-04),"hard+ 扩题"计划(DEEP_ANALYSIS §5,≥8 道新题)至今没有实物,窗口内也来不及出题+验证。即便新候选都跑完 hard,**n=4 不足以在统计上区分"真比 swift-1.5-27b 强"和"运气好"**(FINAL_BASELINE 自己的口径:"小样本 CI 宽,只分梯队不排名次")。能看出明显好坏(easy 20/20 vs 15/20),看不出细微高下,别对结果抱太细的期待。

**nemotron-omni 35.2G / glm-4.7-flash-mlx 31.8G 的更正**:DECISIONS 10-26 09:15 提过"现成未测大件...冒烟后立臂",但 Q2b 查实这两件**不在本机盘上**,`lms ls` 里只是挂在远端设备(bogon)的条目,`r3_load` 对远端落点会直接卸载判失败——要测必须先下载,不是"现成"的。

## Step 4 — "使用"(落地)(已定稿)

"落地"不是改全局配置,是更新两份只读的推荐文件 + 一条软链接刷新,最终取舍权在你(PLAN_WINDOW §5:"队列 owner=主控,唯一能改队列/脚本/STOP 者"):
- `reports/baseline/integrations/bos_models.json`:BOS 路由注册表(`bos://local-ai/models/`),记 retained 模型的 tier/ram/成绩/tps/recommended_for,加 eliminated 名单和 protocol_recommendations;消费方是 BOS/Magpie/omlxc。
- `reports/baseline/integrations/pulse_dashboard.json`:Pulse 分层(daily-driver=swift,speed-demon=qwen3.6+ornith-35b,lightweight=mellum,long-context=qwopus,heavy-duty=flashnext)。
- ROADMAP Phase3 的"刷新 `omlx/models-active` 软链接,使性能卓越的最新模型进入系统常驻分流"——这一步真的会改变日常栈行为(哪个模型常驻),按 RESUME 铁律和 PLAN_WINDOW §5,**要你点头才做,不会自己动**。

版本口径差:`integrations/` 里的 eliminated 名单是 10-21 版,跟 FINAL_BASELINE(10-26 版)有出入,以 10-26 为准。

**窗口内只做**:测评出结果 → `bench_stats.py` 自动更新 DATA_AUDIT/data_audit.json → 给一份"哪些新候选值得进 retained/eliminated 名单"的建议,**不直接改 bos_models.json / pulse_dashboard.json / omlx/models-active**,留给 10-28 closeout 或你单独拍板。

顺带核到的当前落地现状(Q4b):`lms server` 1234 在跑;`omlx :8000` 常驻 10 个端点(mythos-fast、qwen-3.6-35b、coding-next、embedding 系、tts/asr);日常栈 llm_gateway 在 10:59 前后自己拉起了 `swift-1.5-qwen3.8-27b-splash`(RSS≈18G,非 `mlai3-` 前缀)——这就是 11:43 那次 free% 从 75% 掉到 53% 的原因,不是评测在吃内存。

## 风险与回退

- **日常栈会被 benchq 挤掉(已知,不是新问题)**:llm_gateway 常驻的 `swift-1.5-qwen3.8-27b-splash`(RSS≈18G)会在 benchq 需要内存装载新臂时,按 foreign_busy/stray_unload 规则被卸掉(idle)或等待(busy)。这是窗口内一直以来的既有行为(DECISIONS 多次记录),不是新风险,但窗口期间日常用 swift 会时断时续。
- **Nanbeige 续传踩坑**:hf_fetch.py 见到 `.aria2` 会连目标文件一起删掉重下;这一件必须 `aria2c -c` 续,其余没有 `.aria2` 残留的候选才用 hf_fetch.py。
- **NVFP4 一律不用**:含 NVFP4 张量的 GGUF 在 Apple Silicon 会回退 CPU(bolt-74b-a9b 5.3tps 就是这么来的),下载前认准量档。
- **Flint 可能整个白测**:LM Studio 路径基本判死,harness 自己的兜底正则(`agent_eval.py:346`)也不认它的工具标签;Splash/ollama 路径能不能解析它的 GLM 式标签没验证过,冒烟不过就是 2h 下载 + 冒烟时间白花。
- **hard 档分辨力不够**:n=4,别指望精细排名(见 Step 3)。
- **PLAN_WINDOW Phase4 冲突**:原文写"不再启动新条目",这次是有意偏离,已如实标出,不是疏忽。
- **窗口终点是硬边界**:10-28 09:07 的 closeout 会 touch STOP,10:00 兜底脚本还原隔离/JIT;所有新条目必须在 09:00 前跑完,排期留缓冲。
- **回退**:改 `r3_arms.tsv`/`queue.tsv` 前先备份(`.bak-1027-<tag>`);DECISIONS 只追加不改历史;下载失败/校验不过就删掉重来,不覆盖已有完整文件。

## 验证

- **下载**:每件都用 HF API 的 `lfs.sha256` 逐文件核对(不能只看完成标记);Nanbeige 用 aria2c 自己的完整性校验 + 最终 sha256 双保险;Sage 的 mmproj 已核过(逐字节一致)。
- **新臂上队列前**:先按 DECISIONS 10-20 10:55 的先例做 ctx4096 冒烟(小上下文试加载 + 一轮工具调用),确认能跑通、工具调用格式能被正确解析(尤其 Flint/Coder390),再追加 queue.tsv。
- **benchq 重启**:`cd ~/mac-local-ai-task-2026-10-12 && nohup zsh bin/benchq.zsh > logs/benchq.nohup 2>&1 & disown`(RESUME.md 原文);已确认从本类会话启动不踩 TCC 坑(10-23 有 pid 97490 连跑 4 天的先例,本次会话实测 `/Volumes/Model` 读写全通)。
- **每轮评测跑完**:`python3 -I bin/bench_stats.py` 重算 DATA_AUDIT,确认 rc=0;`benchq_tick.zsh --dry` 可随时干跑验证分支逻辑,不写文件。
- **收尾**:所有动作(改臂表/队列、下载、冒烟结果)都按 `[YYYY-MM-DD HH:MM:SS] 内容` 格式追加进 DECISIONS.md,不删不改历史记录。
