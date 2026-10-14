# v3 模型研究增量包执行计划(2026-10-14)

## Context

用户下发 `Mac_Local_AI_Research_Update_2026-10-14.zip`(模型研究增量,5 文件已通读),作为 2026-10-11 Mac 本地 AI 部署方案的增量更新。要求:按 P0→P6 条件顺序执行(P7 默认不执行)、不批量下载、不覆盖已工作环境或全局 provider、五项重点验证(Sushi 新版 CLI/Qwen 精度/缓存正确性;Qwen 4bpw vs GSQ-RCO IQ3_S;MiMo-V2.6-Flash 真实代码能力;按需 DeepSeek-0731/GSQ-RCO GLM 原生 MTP;mini 从轻模型开始)。公开作者数字仅作 evidence;本机没测的保持 NOT_RUN;以真实任务成功率/总耗时/稳定性选主力。

与进行中的 r3 评测(已批计划,今晚 `r3_tonight.zsh` 挂 N0+N1,全 lms 臂不碰 Sushi)**交错执行**。

### Grilling 已定八决策(两轮,2026-10-14)
1. **排程**:r3 与 v3 交错——P0 明天白天(纯只读),P1 在 r3-N1 完成后、r3-N3(Sushi 臂)前
2. **P2 零下载**:GSQ-RCO IQ3_S 本机已有(/Volumes/Model/LMStudio/ISTA-DASLab/,84.53GB=IQ3_S 两分片+projector,即 r3 臂 flashnext-gsq-rco),不重新下载
3. **题库**:复用现有 24 题 + 补 6 题多文件调试 = 30;文档/检索用现有 MIX 类映射并在报告注明
4. **下载授权**:P3 MiMo(96GiB)视为已授权直排;P4(81GiB)/P5(90GiB)条件触发且每次下载前单独确认
5. **mini 起步**:直接下 MiMo-V2.6-Distill-Qwen-9B(7.38GB)首测,Gemma QAT 作对照(用户改推荐,明确选此项)
6. **硬件包**:搁置(home-agent-plan-v3 归档,设备未到)
7. **补题回填**:新 6 题至少回填 sushi-qwen-4bpw(升级后)与 flashnext-gsq-rco 两对照臂,保证终选同题直比
8. **终选应用**:FINAL_SELECTION 只出建议+变更清单,实际切 e1d 配置/常驻 profile/LM Studio 默认前单独确认

### 已核事实
- 磁盘:/ 461Gi、/Volumes/Model 1.2Ti 可用;外置足够 P3(96GiB)分阶段
- Sushi 1.2.2 在 `~/mac-local-ai-task-2026-10-12/engine-home/.sushi`(配置);二进制定位是 P0 项
- bf16 表(102G)aria2 进程已不在跑,状态待 P0 核实(属原任务 E0,不阻塞本计划)
- v3 包关键约束:`--qwen-gdn` 现为 32|16(默认保留 32 基线,16 作附加);Sushi 升级后旧前缀缓存失效是预期(分别测重建与命中);含字面控制 token 的合成文件会话边界回归

## 执行阶段(P0→P6)

### P0 资产盘点 + CLI 核验(明天白天,纯只读,不下载)
- bf16 下载终态核实(控制文件/目录大小);GSQ-RCO 分档文件清单逐个 ls 核对
- 定位 Sushi 1.2.2 二进制、`--version`、与包内 CLI 说明对照;确定 1.2.2 备份共存方案
- 建 `~/mac-local-ai-task-2026-10-12/reports/research-v3/`;出 MODEL_MANIFEST.md 初版(已有 vs 待下)
- mini(MacMini-M4)远端可达性核查

### P1 Sushi 1.2.3 + Qwen 重测(夜间;r3-N1 完成后、r3-N3 前)
- 备份 1.2.2 → 装 1.2.3(回滚路径保留)
- CLI 核验:`--qwen-gdn 32` 基线(16 附加)、缓存失效重建→命中分别测;字面控制 token 合成文件会话边界回归
- Qwen 4bpw 重测:24 题 + bench 三态(cold/new/hit)三次交替;缓存正确性专测
- r3-N3 的 sushi-qwen 臂直接用 1.2.3(引擎版本记入臂表 notes)
- 产出:CLI_COMPATIBILITY.md、CACHE_CORRECTNESS.md

### P2 GSQ-RCO 对照(r3-N5 时段,零下载)
- 本机 IQ3_S 走 r3 统一口径(独占加载/65536-32768 ctx/全维度)+ v3 补充项
- 与 Sushi Qwen 4bpw 同题对照(24 题 + 回填 6 题)
- LM Studio 引擎跑不动 qwen4exp → 记 BLOCKED_ENGINE,后端选择再问用户

### P3 MiMo-V2.6-Flash(已授权,白天下载夜间测)
- 96GiB Sushi 2.3bpw 下到外置;普通/MTP 两模式分别验收(30 题全套 + bench)
- 重点:真实代码任务成功率/总耗时/稳定性

### P4 DeepSeek-0731 / P5 GLM Q2(条件触发,下载前单独确认)
- 触发条件:P1-P3 主力线不满意(简单 <17/24 或 hard 零通过或 bench 异常)才动;否则跳过保持 NOT_RUN

### P6 mini 线
- 直接下 MiMo9B(7.38GB)首测;Gemma QAT 已有模型对照;mini 口径 4K/8K→16K

### P7 不执行
Slotstream/剪枝 Coder/OptiQ/V4.1 全部保持 NOT_RUN。

## 产出(8 个新报告,reports/research-v3/)
RESEARCH_DELTA / CLI_COMPATIBILITY / MODEL_MANIFEST / LICENSE_REVIEW / BENCHMARK_MATRIX / TASK_RESULTS.jsonl / CACHE_CORRECTNESS / FINAL_SELECTION(建议+变更清单,切换单确认)。

## 全程约束
- 公开作者数字只进 evidence 区,不进 local_measurements;未测 = NOT_RUN
- token 经环境变量/文件,不进 argv 不打印;不可逆操作先确认
- 不动全局 provider/用户模型/进程;评测窗口禁 `aictl verify`(会真实调用模型)
- 评测独占口径仅夜间保证(白天用户使用触发 JIT,已实测);Write 产物必须 chmod +x(126 事故教训)

## 复用
r3 全套基础设施(r3_arms.tsv/r3_engine.zsh/r3_driver.zsh/r3_run_arm.zsh/microbench/agent_eval/guarded_run/mlai.py);v3 新臂按同列规格追加进臂表,不另起炉灶。

## 验证
- P1:升级前后 Qwen 同题对比表 + 缓存三态数据齐;1.2.2 回滚路径实测可用
- P2/P3:对照臂同题直比表;TASK_RESULTS.jsonl 每题有 result.json 证据链
- 终选:FINAL_SELECTION 每条建议附实测证据引用,无作者数字充当本机数据

## 增量维护批次(2026-10-14 追加,用户拍板)

### M1. MODEL_SPEC_MATRIX 持续维护约定
文件头加"维护约定"节:每批 r3 臂完成/每 v3 P 阶段出数后 24h 内刷新对应行(成绩列换 r3 65536 口径、速度列换 r3 bench 五档三态、评分重算);r3 全量+v3 P1-P3 完成后升版为 BENCHMARK_MATRIX 正式稿。每轮刷新在 PROGRESS 记一行。

### M2. 重复模型清单固化 + 处置跟踪
SPEC_MATRIX 加"同源/重复清单"节(上述 A/B/C 三组+边缘重叠):A 组(qwen3.8-27b 三胞胎)r3 复测后由用户拍板砍不砍 alis(省 17.4G);B 组保留(引擎对照);C 组保留(P1/P2 实验)。r3 数据出来后在该节记差异结论。

### M3. ctx 表述修正 + P1 附加实验
- SPEC_MATRIX 已测表 Sushi 两行的 ctx 列改为"本机授予 65536/原生 262144[未测]"与"引擎定死 32768"(模型 README 证据已核:YaRN x4 over native 262,144)。
- P1 夜间窗口顺带附加实验:完全驻留档试探 ctx 98304/131072(内存门禁 free≥need+8G 过才跑,不过记 NOT_RUN+ctx_ledger),单次 2K/8K 探针级 bench 验证可用性即收(不跑全题)。

### 执行顺序
M1-M3 均为文件固化+P1 时顺带动作,随下次执行窗口(P1 前)落地;不阻塞今晚 r3_tonight.zsh。

## 增量验收分支(2026-10-14 追加,S1/S2;grilling 两决策已定)

### S1. Strata 验收分支(P2 时段并入,三引擎同题对照)

已核事实(只读侦察 2026-10-14):
- 仓库 github.com/Niko1221/Strata 实锤(23.8k 星,C++);**v0.1.44.1 = 2026-10-14 最新正式版**(hotfix:老 CPU 启动/CUDA 12.0-12.1/M2 正确性;identity tests 与 0.1.44 byte-identical,与 M5 无关)→ 基线成立,执行时锁 tag+完整 commit
- docs/MAC.md + metal/setup_mac.py 在;**官方在 M5 Max 128GB 实测过(同款机器)**,模型驻留;Metal 自研引擎同 host/server;源码构建 1-15min;独立 Python 3.12(25M,sha256 pin,无 sudo 无 brew)
- IQ3_S = 官方推荐档:GPU 映射 54.8G / 总需求 63G;n-gram 表 28.8G(SSD 随机读不占驻留);Metal 驻留上限 ~107.5/128G;默认 `--spec 2`+Q8_0 hyper-connection
- 服务:OpenAI `:8080/v1` + **Anthropic `/v1/messages`**;`--gguf-dir` 可复用已有 GGUF;`--model/--context/--port/--host/--api-key/--vision/--draft-vocab/--no-browser` 选项齐

步骤:
1. **白天(不占评测窗)**:clone @v0.1.44.1(pin commit)到 `strata-home/`;审 setup 脚本确认无 sudo/无开机服务/不动 wired limit;`./setup.sh --gguf-dir` 指向本机 GSQ-RCO——**先核文件清单与 Strata pack 定义匹配**(Strata IQ3_S=54.8G 主文件+28.8G n-gram;本机两分片 51G+27G,匹配性未证);不匹配 → 停下问用户是否下官方包(66-84G,单确认)
2. 环境:独立目录、`--host 127.0.0.1`、独立密钥(文件注入不进 argv)、`--context 32768` 起步、纯文本、单并发、`--vision no`;按服务端文档关内置 MCP/实验行为;**中文用途保留 cjk 草稿词表**(`--draft-vocab` 核 MAC.md);记录实际 KV 与精度设置;setup 前探测 8080 冲突(INVENTORY 无占用记录,实测为准)
3. **验收阶梯(P2 夜,三引擎同题:Sushi-4bpw / LMS-IQ3_S / Strata-IQ3_S)**:a) 聊天/流式/Responses/基础工具闭环;b) 30 题(24+MF6)+20-30 轮工具会话;c) TS/PY 多文件修改+测试失败修复;d) 冷加载/无前缀命中/前缀复用三态,交替×3,记成功率/总耗时/TTFT/生成速度/内存压力/交换增量
4. 对照口径:三引擎=引擎×量化**组合对比**(IQ3_S vs 4bpw 不同量化,不写成纯引擎比较;不假定 Sushi 状态)
5. UD-Q4_K_XL 条件项:IQ3_S 通过+用户点头才下;下载前核算原始分片+Metal 重打包副本(experts copy)双份磁盘
- 产出:`STRATA_ACCEPTANCE.md`(实际配置/启停命令/版本锁/测试报告/回滚=删目录);复用 agent_eval/microbench/guarded_run;评测窗口 launch guard 照旧

### S2. Swift1.5 对照分支(下载排队 MiMo 后,验收排 P3 后夜)

已核事实:
- Dankpaws/Swift1.5-Qwen3.8-Flash-Next-MLX-4.7bpw:sha `13839b71…`,**106.8G 总**(safetensors 74.7G)115 文件,license:**other(非标,下载前必审)**;**无 MTP/draft 头文件**(MTP 对照受限,核 mlx-serve draft 机制)
- ddalcu/mlx-serve:MIT、Zig 原生单二进制、macOS 26.2+(本机 27.0.1 OK)、OpenAI+Anthropic 双 API `:11234`;作者指定加载路径,**不交给普通 mlx-lm**;PC `--family swift` ≠ Mac 支持证据(用户警告在案,按 mlx-serve 文档实证)

步骤:
1. 下载(已授权排队):fetch_v3_prereq.zsh 追加第三段(revision pin),MiMo 完自动接上(~18.5h,后天下午完);下载期间完成 LICENSE_REVIEW(license:other+模型卡条款,审出问题终止分支)
2. 版本锁:mlx-serve release tag+commit+Swift 包 revision+文件 sha256(与包内 release-manifest.json 对照,防回退原版误报)
3. 部署:独立目录/回环 11234/独立密钥;**不照抄作者大窗口与系统内存设置**;32K/64K 起步纯文本单并发
4. 验收阶梯(P3 后夜):工具闭环+真实 TS/PY 任务→128K→160K 长会话;MTP 开关对照同模型同量化(引擎不支持则记 NOT_RUN)
5. 计量明细:总输入/缓存复用输入/实重算输入/输出;预填充/客户端首有效 token/解码时间;工具时间/任务墙钟/重试/测试通过;内存压力/交换增量/取消与恢复
6. 防作弊:前缀稳定但指令变化照实发;不跳过失败测试/不隐式截断/不自动回退云端
7. 对照:Swift(mlx-serve+MLX-4.7bpw)vs 原版 Qwen(Sushi+EXL3-4bpw)= 组合对比,报告标明;终选按任务成功率+端到端耗时
- 产出:`SWIFT_ACCEPTANCE.md`(同 S1 格式)

### 排程总览(2026-10-14 更新;午间窗口=用户报 11:30-14:00 空闲)

- **午间窗口(每日 11:30-14:00,用户不用机)**:今天 = Strata clone+构建+`--gguf-dir` 匹配核(S1 步骤 1 提前)+顺利则冒烟;后续每日按需排轻量臂/单臂重放,**14:00 硬截止还原 aictl daily**(结束前留 10min 收尾),guard 白名单照旧
- 今晚:r3 N0+N1(不变)· MiMo 下载在磨(~100MB/min)
- 明日白天:Strata 收尾(若午间未完)· MiMo 下载收尾
- 明夜:P1(Sushi 1.2.3+Qwen 重测)
- P2 夜:**三引擎对照**(Sushi-4bpw / LMS-IQ3_S / Strata-IQ3_S)+ MF 六题回填
- MiMo 完→自动接 Swift 下载(后天下午完);P3 夜 MiMo 验收;P3 后夜 Swift 验收
- 磁盘:外置 1253G − MiMo 96G − Swift 107G ≈ 余 1050G 充裕

### S1/S2 风险
- Strata `--gguf-dir` 与 ISTA 分片格式不匹配 → 停下问用户(官方包 66-84G 单确认)
- license:other 审出问题 → S2 终止,已下文件存档不删
- 端口 8080/11234 冲突 → setup 前探测,冲突改 `--port`
- 夜间窗口污染:全部 launch guard 白名单照旧,白名单外模型在场即拒跑
