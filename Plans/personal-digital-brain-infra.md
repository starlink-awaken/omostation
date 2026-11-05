---
schema: md/v1
status: active
lifecycle: plan
owner: principal+da
last-reviewed: 2026-11-03
type: doc
title: 个人数字大脑基础设施总纲（PDB-Infra Blueprint v1.0）
---

# 个人数字大脑基础设施总纲（PDB-Infra Blueprint v1.0）

> 数据基础：2026-10-29 全量审计（92,672 请求/25 台机器）+ 2026-11-03 六轮治理实测（双 Studio 接入/L3 清理/model_dir 护栏/文档治理）。
> 业内校准：LiteLLM cache-aware routing / SRE SLO-burn-rate 体系 / Brain Stack 三层记忆架构（§7 参照索引）。
> 本文是纲领不是快照——资产数字以 `cluster-diff`/`usage 日报` 的每日输出为准，本文只维护结构与决策。

---

## 0. 定位与设计原则

**一句话**：把散落的 25 台机器、7 套配置清单、6 层防线，收敛成一台"个人数字大脑的机体"——推理是它的肌肉，记忆是它的海马体，治理是它的免疫系统，而它的每一个器官都必须能被观测、被替换、被升级。

**六原则**（全部来自实打过的坑）：

1. **单一真源（SSOT）优先于任何优化**——四份节点清单互斥的代价（M2 盲区）比任何单点故障都大。任何新组件落地的第一问：它的真源在哪，谁生成，谁校验。
2. **资产只进不出是慢性病**——每一项资产（机器/模型/provider/订阅）必须有明确消费者，否则进待命池或退役。今天 y7000p 的"薛定谔 GPU"教训：定位模糊比没有更糟。
3. **防线即代码**——每一次人肉排障（Decision 499、Clash 黑洞、端口漂移）都必须沉淀为一条自动化防线（cluster-diff 断言/日报阈值/drift-guard 幂等自愈），否则必然复发。
4. **路径脆弱性用间接层消灭**——model_dir 硬编码版本路径、"~/.omlxc vs ~/.config/omlxc"路径混乱，全部用稳定指针（current symlink）+ 单点配置消灭。
5. **本地优先、云端溢出**——2% 本地流量不是失败，是结构的结果；但 Decision-v2 本机 0.42s vs Studio 挤兑 3-8s 证明：高频小决策必须本地化，云端是长尾与重负载的溢出池。
6. **治理跟着事实走**——文档生命周期（08-28 快照标 ssot）、登记版本（ACTIVATION.json 0.1.1265→2752）必须与实测对齐；漂移的治理比没有治理更危险。
7. **复用优先，绝不重复造轮子**——每个新需求先问三遍：已有设施能不能扩一档解决？成熟开源能不能直接采纳？只有两者都不行才自建。选型选最长远的方案（宁可贵一周上手，不便宜三月返工）。§7 的决策表是这条原则的落地。

---

## 1. 现状盘点（2026-11-03 实况）

### 1.1 硬件资产（按角色，非按购置）

| 角色 | 设备 | 规格 | 状态 | 定位 |
|---|---|---|---|---|
| **主控+移动** | MBP | M5 Max 128G / 1.13T 模型盘 | 日常主力 | 交互面 + 控制面 + 高频推理（Decision/router） |
| **家庭重推理** | mac-studio | M5 Max 64G / SHAREDMODEL 1.9T（779G 模型库） | 体系骨干 | magpie 网关(:3425) + 模型冷库 + 每日备份链 |
| **单位推理** | unit-studio-01 | M5 Max 64G / Model 盘 931G(空) | 隧道接入 | vision 双模型 + whisper ASR + gemma-26B（7 模型进 magpie） |
| **常驻兜底** | mini | M4 Pro 24G | 常开 | embedding 兜底 + magpie 同步服务器 + 备份拉取点 + 家庭代理网关(共享出口) |
| **待命 GPU** | y7000p | RTX4070 8G | 待命资产 | ASR/OCR 按需点名（27B 死表已摘，6 个可行模型保留） |
| **编译池** | compute-i9-01 | i9-14900HX 24C/32T / 435G 空闲 | LocalBrain worker | 编译/容器外溢承接（"评测窗口禁跑 CPU 重活"的目的地） |
| **算力池** | bot-01~08 | 8 台买断 VPS | 零负载 | 待开发：常驻服务/CI runner/评测执行器 |
| **代理节点** | bwg2/阿里云双节点/hk-vm 等 | ~9 台 VPS | 部分在用 | Clash SSOT 的出口池（2 死成员待处置） |
| **外置存储** | Model 2T / SHAREDMODEL 1.9T / Model-Store | RTL9210B 10Gbps + TB504 雷电 | 在用 | 模型库/冷库（桥是瓶颈非盘：4MB 块才出 0.88GB/s） |

### 1.2 软件栈（已收敛后的现状）

- **路由网关**：magpie（0.1.2752，三台部署，webdav auto off 各机独立）——对标 LiteLLM：session 亲和 + smart 策略 + 端点分派（chat/embedding/rerank）
- **推理引擎**：oMLX 0.7.2（**三机同版**，cluster-diff 每日盯）+ LM Studio（54 模型哑资源待救）+ Ollama（兜底）
- **记忆层**：funes（会话记忆，163→3.3 核时/天已治理）+ gbrain（知识图谱）+ Cortex（LifeOS Knowledge Archive）——对标 Brain Stack
- **操作系统层**：LifeOS 7.40.4（identity/TELOS/工作流）+ omostation（治理 GaC/SSOT/ADR）
- **网络层**：Tailscale tailnet（7 节点）+ Clash SSOT（repo→build→deploy 三场景）+ 单位双向隧道（LaunchAgent 守护）
- **已建防线六层**：usage 日报(06:07) / cluster-diff(06:13) / 周归档(周日06:47) / clash-drift-guard(×30min) / 隧道守护 / model_dir 护栏断言

### 1.3 病灶与债务登记（未解决项）

| # | 债务 | 严重度 |
|---|---|---|
| D1 | omlxc 源码 3.4.0 vs 部署 v3.0.14（升级事务，current 指针已就绪） | 中 |
| D2 | embedding keep/pinned 三处三义（omlx_keep/resident_models/is_pinned） | 低（有 cluster-diff 盯） |
| D3 | Studio LM Studio 54 模型无 API server（哑资源） | 中（评估完成待试点） |
| D4 | magpie 无 /v1/audio/speech（TTS 能力断层，只能直连 oMLX） | 中 |
| D5 | bot 集群 8 台零用途 | 低（零边际成本） |
| D6 | tailscaled 依赖 Clash 系统代理（切网瞬态瞎） | 低 |
| D7 | 阿里云双节点翻脸（智能路由组2 悬案） | 低 |
| D8 | gac stale_locks=4 + gen-help-docs epoch-0 bug | 低 |

---

## 2. 目标架构：四层一环

```
┌─────────────────────────────────────────────────────────────┐
│  L4 数字大脑层（Being）                                        │
│  LifeOS(identity/TELOS) · agent 群(Hermes/omp/...) · 决策     │
├─────────────────────────────────────────────────────────────┤
│  L3 记忆与知识层（Memory —— Brain Stack）                      │
│  funes(会话) · gbrain(图谱) · Cortex(档案) · 单一 MEMORY 真源  │
├─────────────────────────────────────────────────────────────┤
│  L2 推理与路由层（Muscle）                                     │
│  magpie 网关(统一入口) · oMLX×3 · LM Studio · 云端 provider 池 │
│  能力路由: chat/embed/rerank/vision/ASR/TTS · 本地优先云溢出   │
├─────────────────────────────────────────────────────────────┤
│  L1 基础设施层（Body）                                         │
│  硬件 9 类角色 · Tailscale mesh+隧道 · Clash SSOT · 存储分层   │
└─────────────────────────────────────────────────────────────┘
  ◀──── 治理与可观测环（Immune System，贯穿四层）──▶
  SSOT 生成/校验链 · 六层防线 · SLO 告警 · 飞轮迭代
```

**设计依据**：
- 分层对标 [Brain Stack](https://vectorize.io/articles/brain-stack-second-company-single-brain)（second brain → shared brain → multi-agent memory 三层记忆）与 SRE 控制面/数据面分离
- L2 的 session 亲和 + prefix cache 复用对标 [LiteLLM cache-aware routing](https://docs.litellm.ai/blog/cache-aware-routing)（同会话同节点 → prompt prefix 命中 → TTFT 下降）
- 治理环对标 [SLO 中心告警体系](https://openobserve.ai/blog/set-meaningful-slos)：面向体验不面向阈值

---

## 3. 十维规划

### 3.1 环境（Environment）

**现状**：三处物理环境（家/单位/云）；配置散在 dotfiles/local-ops/Clash SSOT；路径脆弱性已用 current 指针部分消灭。
**目标**：环境即代码，三处环境一键描述、可重建。
- 家：主阵地（mini 常开 + Studio + MBP）；单位：内网孤岛已通（隧道），待 Tailscale 化；云：按角色收敛。
- **动作 A1**：`~/.config` 配置面清单化（cluster-diff 已覆盖 60%，补齐 aetherforge/aliases 等 5 处）
- **动作 A2**：环境描述文件（env-manifest.yaml：每机角色/端口/服务/依赖），cluster-diff 的 A 节升级为消费它
- **动作 A3**：单位台 Tailscale 化（sudo 一步），隧道降级为备份链路

### 3.2 设备（Devices）

**现状**：9 类角色已定型（§1.1），全部进四清单；剩余摇摆：y7000p 待命、bot 集群零用途。
**目标**：每台设备一个唯一角色、一个健康判据、一个退役条件。
- **动作 B1**：bot 集群用途拍板（建议：2 台 CI runner 承接编译外溢 + 2 台评测执行器 + 4 台保留池）——等待用途构思确认
- **动作 B2**：每机"健康判据"落 cluster-diff（如 mini=同步服务心跳、Studio=常驻 3 模型字节基线、单位台=隧道 :18081）
- **动作 B3**：设备退役流程文档化（四清单除名 + 备份链除名 + ssh 别名清理，gcp 先例）

### 3.3 架构（Architecture）

**现状**：四层一环成型；最大架构债：M2 治理盲区（多清单）已用 cluster-diff 盯住但未 SSOT 化。
**目标**：`cluster.yaml` 单一真源（10-29 战略总纲 M-1 的正式落地）。
- **动作 C1**：cluster-diff 从"只读校验器"进化为"生成器"（先做 env-manifest 消费，再生成 aictl/omlxc 面）——90 天项
- **动作 C2**：记忆层统一 MEMORY 权威（funes/gbrain/Cortex 各司其职边界写入 LifeOS 文档）
- **动作 C3**：决策链路协议化（router-brain → 本机 Decision-v2 的模式推广：高频小决策必须 <500ms 本地闭环）

### 3.4 部署（Deployment）

**现状**：Clash 已是声明式（ssot→build→deploy）；oMLX/服务靠 plist+launchd 手工；rsync 大包有 40 分钟教训。
**目标**：GitOps 化——一切部署可从 git + manifest 重建。
- **动作 D1**：plist 清单纳入 local-ops git（已有大部分），补 unit-studio 侧
- **动作 D2**：模型分发协议：大 bundle 用 ditto 压缩管道不走 rsync --delete；版本一致性由 cluster-diff D 节把门（422 事故防线）
- **动作 D3**：升级 runbook 模板化（omlxc 升级=装新 release+改 current 指针+cluster-diff 验证——护栏已就绪）

### 3.5 路由（Routing）

**现状**：magpie 57 provider/35 组；smart 策略 + session 亲和；L3 僵尸清理完（commandcode-plan 7 引用摘除）。
**目标**：能力路由 + SLO 路由双维度。
- **动作 E1**：**SLO 加权路由**——把 usage 日报的失败率/延迟数据回灌路由权重（M-5 落地）：失败率>30% 自动降权，连续 7 天健康自动恢复
- **动作 E2**：能力端点补全：TTS 断层（D4）→ 直连 oMLX 封装 `aictl tts`（单位台有 Kokoro）或评估 magpie 插件
- **动作 E3**：决策路由本地化推广（C3 同源）：router-brain 模式复制到其它高频小模型场景

### 3.6 拓扑（Topology）

**现状**：Tailscale mesh（7 节点）+ 单位内网隧道 + Clash 三场景；混合分层代理架构已定型（固定设备共享 mini 出口 / MBP 移动自带）。
**目标**：mesh 优先、隧道备份、出口池化。
- **动作 F1**：单位台 Tailscale（A3 同源）→ mini 备份链可拉单位台
- **动作 F2**：derper 自建评估（mini 已有 exit node 气质；relay "bjc" 8.4ms 已够用，不急）
- **动作 F3**：代理出口健康化：阿里云双节点处置（换节点或 parked 进 SSOT）

### 3.7 监控（Monitoring）

**现状**：usage 日报（业务指标）+ cluster-diff（结构漂移）+ Vitals（系统层）——三支柱雏形已成。
**目标**：可观测性三支柱对齐 OTel 心法（instrument once, consume anywhere）：业务/结构/系统三层指标全部结构化、可回溯。
- **动作 G1**：usage.jsonl 归档已建（周快照 9 份）→ 补月度合成报表（90 天项）
- **动作 G2**：cluster-diff 输出 JSON 化（供趋势对比：漂移数按日序列）——30 天项
- **动作 G3**：每机健康判据（B2）纳入 cluster-diff A 节 → 单文件全体系结构健康

### 3.8 告警（Alerting）

**现状**：osascript 通知（Clash drift）+ 日报异常信号节（499 风暴/失败率>30%/探针风暴阈值 10）。
**目标**：SLO 分级告警——只在该找人的时候找人（[SRE 心法](https://openobserve.ai/blog/set-meaningful-slos)：page on symptoms, not causes）。
- **动作 H1**：**SLO 定义表落地**（本次落地项，见 §4）
- **动作 H2**：burn-rate 双窗口告警（快窗 1h 慢窗 6h，抗告警疲劳）——日报脚本升级
- **动作 H3**：告警分级 P0(即时通知)/P1(日报)/P2(周报) 三档，现有防线全部映射入档

### 3.9 运维（Operations）

**现状**：六层防线 + 幂等自愈器（drift-guard）+ runbook 散落在 ADR/patterns。
**目标**：自愈优先、人兜底、每次人肉必沉淀防线（原则 3 的制度化）。
- **动作 I1**：runbook 索引页（.omo/_knowledge/ops/ 已有 zhixing runbook，补总索引）
- **动作 I2**：排障→防线转化清单（Decision 499→已转化✓、Clash 黑洞→已转化✓、端口漂移→cluster-diff 待补端口断言）
- **动作 I3**：月度演练：拔一台机器（如 unit-studio）看防线是否按预期报警/自愈——chaos day 微型版

### 3.10 运营（Operations-Business）

**现状**：37+ 订阅、成本感模糊；本地 2% 流量 vs 2.4T 模型资产的投入产出倒挂（M1）。
**目标**：成本可见、利用率可审、资产进出有据。
- **动作 J1**：订阅/provider 季度审计（usage 日报已有数据，补成本列——价格表进 providers.json 或独立 manifest）
- **动作 J2**：模型库进出机制：评测驱动（eval/ 体系）→ 零调用 90 天的模型进冷库/退役（10-28 P1 删除的机制化）
- **动作 J3**：本地利用率月报（本地占比趋势：当前 1.9-20.7% 波动，目标场景化——日常交互本地化、重负载云端）

---

## 4. SLO 定义表（本次落地）

| 等级 | SLI | 目标 SLO | 测量源 | 告警档 | 现状 |
|---|---|---|---|---|---|
| P0 | magpie 网关可用性（:3425 响应） | 99.5%/日 | 探针+usage | 即时（osascript） | 无监控 → **本次补** |
| P0 | 决策链路延迟（router-brain 端到端） | p50<1s / p99<5s | usage ms 字段 | 日报 | 0.42s ✓（修复后） |
| P1 | 整体请求成功率 | >95%/日 | usage 日报 | 日报 | 92.9-94.8% ⚠️ 差 2pp |
| P1 | 结构漂移数（cluster-diff） | ≤2/日 | cluster-diff | 日报 | 2 ✓（白名单后） |
| P1 | oMLX 三机版本一致 | 100% | cluster-diff D 节 | 即时 | 一致 ✓ |
| P2 | 本地流量占比 | >10%/月 | 日报周报 | 周报 | 1.9-20.7% 波动 |
| P2 | 探针噪音量 | <50/日 | 日报 | 周报 | 60 ⚠️ |
| P2 | 备份链新鲜度（快照间隔） | ≤25h | mini pull 记录 | 日报 | 健康 ✓ |

---

## 5. 路线图

### 30 天（低风险，全部已有雏形）
- [x] 六层防线（11-03 完成）
- [x] 双 Studio 接入 + 四清单对齐（11-03 完成）
- [ ] P0 可用性探针 + SLO 表自动化（H1/G3 续）
- [ ] unit-studio Tailscale 化（等 sudo）
- [ ] 阿里云双节点处置
- [ ] cluster-diff 端口断言（I2 遗留）
- [ ] kimi-work/trae-global 重登

### 90 天（结构性）
- [ ] env-manifest.yaml + cluster-diff 消费（A2）
- [ ] SLO 加权路由回灌（E1，M-5 落地）
- [ ] cluster-diff JSON 化输出 + 漂移趋势（G2）
- [ ] TTS 能力补齐评估（E2）
- [ ] Studio LM Studio server 轻量试点（D3/R8）
- [ ] bot 集群首批 2 台用途落地（B1）
- [ ] burn-rate 双窗口告警（H2）

### 365 天（体系级）
- [ ] cluster.yaml 生成器全链（C1，M-1 收官）
- [ ] 记忆层 Brain Stack 边界协议化（C2）
- [ ] 月度成本审计自动化（J1）
- [ ] 模型库评测驱动进出机制（J2）
- [ ] chaos day 常态化（I3）

---

## 6. 风险登记

| 风险 | 缓解 |
|---|---|
| 多机版本漂移（422 同型） | cluster-diff D 节每日盯 + 升级 runbook（D3） |
| 隧道单点（unit-studio 依赖 MBP 在线） | Tailscale 化（A3）后 mesh 冗余 |
| 配置面漂移（~/.config 盲区） | cluster-diff 覆盖扩展（A1） |
| 告警疲劳 | SLO 分级 + burn-rate 双窗口（H2/H3） |
| 单人运维带宽 | 自愈优先 + 防线沉淀制度化（原则 3） |
| 订阅成本失控 | 季度审计（J1） |

## 7. 复用与选型决策表（keep / adopt / build）

> 每个环节三选一：**keep**=已有设施扩一档（首选）· **adopt**=采纳成熟开源（次选，选最长远的）· **build**=自建（最后手段，必须先证明前两者不行）。

| 环节 | 决策 | 依托什么 | 为什么不选另一个 |
|---|---|---|---|
| 推理网关 | **keep magpie** | magpie（已三机部署，session 亲和/端点分派/smart 策略全在） | 不 adopt LiteLLM/Bifrost：magpie 已是体系一部分且能力同构（cache-aware 亲和已在实践），换网关=全路由重写+三机重部署，收益为零 |
| 网络组网 | **keep Tailscale** | tailnet 7 节点 + 单位隧道（备份链路） | 不自建 WireGuard mesh：Tailscale 的 DERP/密钥轮换/MagicDNS 免运维，自建是纯负担 |
| 代理 | **keep Clash SSOT** | repo→build→deploy 三场景 + drift-guard 自愈 | 不 adopt sing-box 重写：SSOT 链已闭环，换核心=防线全部重写 |
| IaC/配置 | **keep local-ops + manifest 路线** | dotfiles git + env-manifest（A2 规划中） | 不 adopt Ansible/nix-darwin：9 台机器规模 launchd+git+manifest 足够；nix 学习曲线对单人体系 ROI 为负。**90 天后若 manifest 不够用再评估** |
| P0 可用性监控 | **build 轻量探针→90 天评估 Uptime Kuma** | 复用防线模式（探针脚本+cron+osascript，30 分钟落地） | 不直接上 Prometheus+Grafana：个人体系养不起全家桶；Kuma（单容器/成熟/可迁移）是探针跑顺后的升级位——**先证明需求再上工具** |
| 指标存储 | **keep usage.jsonl + 周归档** | magpie 原生数据流 + gzip 快照 | 不引入 VictoriaMetrics：数据量（9 万行/25 天）jsonl+归档绰绰有余 |
| 结构校验 | **keep cluster-diff** | 已覆盖四清单/版本/model_dir/白名单 | 这是**唯一合理的自建**（逻辑 100% 私有），且已运行 |
| 备份 | **keep tar 快照链 → adopt restic（90 天）** | 现有 tar+sha256+mini pull；restic 提供去重/加密/校验和 | restic 是社区标准答案（去重节省 60%+ 空间、端到端校验），tar 链作为过渡保留 |
| 密钥管理 | **keep 钥匙串+registry 登记** | macOS Keychain + secrets registry（已有指纹登记制） | 不 adopt Vault：单用户场景过重，钥匙串已满足"不落盘不落屏" |
| 编排调度 | **keep launchd+cron+plist** | 全部在 git，drift 检查已盯 | 不 adopt Kubernetes：9 台异构机器（mac/win/linux）个人体系，k8s 运维成本 >> 收益 |
| 记忆层 | **keep funes+gbrain+Cortex** | Brain Stack 三层已各司其职 | 不 adopt 第三方 memory 框架（mem0 等）：数据主权+已有索引资产，接口对齐 MCP 即可互通 |
| 知识工作流 | **keep LifeOS** | 7.40.4 固定核心 + 单一 USER/MEMORY | LifeOS 本身就是"最长远的自建"，与 omostation 治理同构融合 |
| 评测 | **keep eval/ 体系** | 12+8 道题库、严格口径、新判据（轮次+耗时） | 已含两轮校准与自我纠错记录，第三方框架（inspect-ai）只在需要分布式评测时引入 |

**决策共识**：本体系 90% 环节是 keep——这不是保守，是**已有的轮子确实好**（六层防线+SSOT 链是三天治理的净成果）。adopt 只在两处（restic、可能 的 Kuma），build 只有一处正当性（cluster-diff，私有逻辑）。任何新需求进门先过这张表。

## 8. 业内参照索引


- [LiteLLM — Open-Source AI Gateway](https://litellm.ai) / [Cache-Aware Routing for Self-Hosted Models](https://docs.litellm.ai/blog/cache-aware-routing) —— 网关与亲和路由
- [Best LLM Routing Solutions in 2026 (Maxim)](https://www.getmaxim.ai/articles/best-llm-routing-solutions-in-2026) / [LiteLLM Alternatives (Inworld)](https://inworld.ai/resources/best-litellm-alternatives) —— 网关选型面
- [How to Set SLOs in 2026 (OpenObserve)](https://openobserve.ai/blog/set-meaningful-slos) / [Best Observability Tools for SRE 2026 (Sherlocks)](https://www.sherlocks.ai/blog/best-observability-tools-sre-teams-2026) —— SLO/burn-rate 心法
- [The Brain Stack (Vectorize)](https://vectorize.io/articles/brain-stack-second-company-single-brain) —— 三层记忆架构
- [AI Second Brain Guide 2026](https://www.iwoszapar.com/p/ai-second-brain-guide) / [Second Brain with LLM Agents (Liran Tal)](https://lirantal.com/blog/building-second-brain-with-llms-ai-agents) —— memory-as-infrastructure 与 durable context
- 内部衔接：`docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md`（eCOS 三年规划，ADR-0410）· 10-29 算力战略总纲（本文件的基础）· `docs/pitfalls.md`（历史实证避坑档案）

## 9. 本文档自身的持续迭代机制

> 纲领不能是死文档。"持续动态优化迭代"先从本文档自己做起——它挂在已有防线的节奏上，不另造机制。

- **数据自动更新**：§1 资产数字不在本文维护——cluster-diff 每日 06:13 出结构真相，usage 日报每日 06:07 出业务真相；本文只维护决策与结构。
- **月度复审（自然钩子）**：usage 周报（周一 06:37）滚动四周后，取月度视图对照 §4 SLO 表——达标项打勾、连续两月未达标项升级动作编号。复审即更新 frontmatter `last-reviewed`（真复审，防日期农场）。
- **触发式修订**：任何一次 P0/P1 事故复盘（如 Decision 499）若改变架构决策 → 同步修订对应维度小节并记入 git/文件历史。
- **路线图节奏**：30 天清单按周勾销（挂在周一节奏）；90/365 天项在月度复审时重估优先级。
- **版本晋级**：结构级变更（增删维度/换架构）时 version 升位（v1.x → v2.0），并同步 STRATEGY-3YEAR-PLAN 的衔接注记。

