# 贾维斯基座规划（Jarvis Foundation · JF-2026-10）

> 日期: 2026-10-10 · 状态: 待执行 · 来源: Harness 配置会话深度调研
> 裁决记录: Q1=**B**（G0 升级收口，不加新系统）· Q2=全场景→**基座先行**（护栏: 每组件绑真实负载）· Q3=组织外溢=远期愿景，不排期
> TELOS 对齐: M1 数字大脑 · G0 收口（死线已过，本计划即收口）· G1 全信息源接入（2026-12-31 死线）· 红线 S1「输出优先，绝不躲在系统后面」

## 1. 定位：激活与收敛，不是新建

贾维斯的 70% 已建成（实测盘点见 §2）。本计划只做三件事：
1. **点亮**——把已建成但空转的组件喂活（常驻 agent、本地能力、算力门面）
2. **接通**——把外部信息源接入事件流（G1）
3. **收敛**——三套算力路由体系统一成一张能力目录

三大病灶（全部实测确认）：
| 病灶 | 实测证据 | 根因 |
|---|---|---|
| 事件流断供 | 输入流 idle 43min；swarm 面板 0/6 agent 活跃 | 没有东西在给贾维斯喂数据 |
| 本地能力缺口 | aictl 表 tts ✗ asr ✗ decide ✗；门面 12h 0 调用/11 错 | omlxc 设计里本就有 tts-qwen3/tts-kokoro/asr-whisper，模型未加载；decide 模型 laya 未部署（mini 已有 jev-style-qwen3.5-2b-decision-mlx 可替代） |
| 路由三轨并存 | aictl 9 场景 × magpie 组路由 × 百炼 8 MCP | 各自为政，无统一能力目录与 fallback 链 |

## 2. 资产盘点（实测 2026-10-10）

### 硬件与节点（aictl 节点表）
| 节点 | 角色 | 配置 | 状态 |
|---|---|---|---|
| macmini | 常驻服务面（gateway/lmstudio/ollama/omlxc + zhixing 驾驶舱 :43191 + magpie webdav :8090） | M4 Pro / 24G / 460G(145G free)，内存 16.9/24G | ● 在线 |
| mbp | 主控 + 外置模型盘（重推理 swift-1.5 / 编码 qwen3.6-35b / 视觉 glm-4.6v） | MacBook Pro | ● 在线（Tailscale 抖动留观） |
| y7000p | LM Link 池（Windows，lmstudio+ollama） | RTX 待确认 | ● 注册在册，利用率低 |
| muse | — | — | ✗ 离线 |

### 推理栈（mini 实测）
- **lmstudio**: 15+ 模型（qwen3.6-35b-a3b 19.5G 已载 · glm-4.6v-flash · qwen3.8-27b · jev-2b-decision · minicpm-v 等）
- **ollama**: gpt-oss:20b · gemma4:31b-mlx · qwen3-embedding:8b · bge-m3
- **omlxc**: daemon 在跑（launchd），常驻集 [embedding, mythos-fast]；**tts/asr 模型未载**（P0 修复点）
- **aetherforge 门面** :4000：三节点统一入口，别名→物理落位解耦

### 路由与订阅
- aictl 9 套场景（official/save/local/deep/pools…）· magpie 44 providers/27 客户端/组路由（cn-fast/pool-code/local-first）· 双机 webdav 同步
- 订阅池: 百炼 Token Plan（text/vision/image/video）+ DeepSeek/GLM/Kimi/MiniMax/硅基/NIM/OpenRouter + 账号型（qoder/zcode/trae/workbuddy/codex/claude…）
- **百炼 Harness（今日落地）**: 8 MCP 双机 8/8 Connected + RAG/Memory/Managed Agent（workspace 域名 llm-tv0c41mr2zdegmfd.cn-beijing.maas.aliyuncs.com，注意 bl/kscli 必须显式 --base-url）+ 标准 key 双机注入（mini Keychain / mbp secrets.env 600）

### eCOS（18 子项目 12🟢6🟡0🔴，BET 98.5%）
- resident 五件套 **活着**（daemon tick 66s · sediment 22 runs 0 fail）——但等输入
- swarm 观测面 6 agent **stale**（governor/advisor/knowledge-curator/observer/task-worker/bridge）
- family-hub 子项目已立项 🟡 · BCOS 信号路由骨架在 · KOS 万篇知识库在

## 3. 目标架构（能力金字塔，全部映射既有组件）

```
L7 场景外溢:   个人提效 | 公开输出(S0) | family-hub(G2) | 组织(远期愿景)
L6 执行层:     resident 五角色(活) + swarm 6 agent(喂活) + 人机批准门
L5 知识记忆:   KOS(万篇) + 百炼RAG/Memory(今日通) + LifeOS MEMORY
L4 路由层:     aictl 场景 × magpie 组 → 统一能力目录(§E3)
L3 能力层:     统一别名: text/vision/image/video/tts/asr/embed/decide/search
               每能力 = 本地优先 → 云端 fallback 链
L2 推理服务:   lmstudio/ollama/omlxc(本地) + 百炼MCP/订阅池(云端) + 三节点门面
L1 硬件网络:   mini(服务面) + mbp(算力) + y7000p(池) + Tailscale tailnet
L0 身份治理:   LifeOS 身份/TELOS + eCOS GaC/P74 + SYNC-MATRIX 双机纪律
```

## 4. 三大工程

### E1 点亮：常驻层 + 本地能力全面激活（P0，本周）
- **E1.1 omlx 能力补全**（tts/asr/decide 本地化——用户已拍板走本地算力）:
  - `aictl load omlx tts-qwen3` / `tts-kokoro`（中/英声库）→ 载入后跑 services.yaml 已定义的 tts→asr 回环 e2e
  - asr-whisper 载入；decide: 先试 laya-multilingual 部署，备选直接映射 mini lmstudio 现成的 jev-style-qwen3.5-2b-decision-mlx + decide-calibrated 校准
  - 验收: `aictl status` 能力表 10/10，`aictl check --live` 全绿
- **E1.2 事件流喂活**:
  - personal-signals cron 确认激活（CRON_SIGNALS）；heartbeat tick 频率对齐面板阈值
  - 日常工作流强制 start 事件（agent_workflow_start）——本人每次开 Claude/agent 会话即自然喂入
- **E1.3 swarm 6 agent 恢复活跃**（绑定真实负载，防空转）:
  | agent | 绑定的真实职责 |
  |---|---|
  | observer | 每日系统巡检报告（resident monitor 已有） |
  | knowledge-curator | KOS 增量沉淀（sediment 已有 22 runs，扩输入源） |
  | governor | GaC 合规巡检 + P74 warn 监视 |
  | advisor | BCOS 信号→提案（decision 已有） |
  | task-worker | G1 信息源接入任务执行 |
  | bridge | family-hub 消息桥（P2 接管） |

### E2 接通：信息源接入事件流（P1，2026-10~11，G1 死线 12-31）
- 首批 3 源: ①邮件摘要（Gmail MCP 已在）→ personal-signals ②日历（Google Calendar MCP 已在）③工作公文/会议纪要（手动投递目录，resident inbox 已有）
- 每源走 BCOS 信号路由（bin/bc-os/signal_router.py）→ 事件流 → 角色处理
- 验收: 事件流 idle < 30min；BCOS 北极星价值度量非零

### E3 收敛：统一能力目录 + fallback 链（P1 并行）
- 在 aetherforge aliases.yaml 基础上建**单一能力目录**（唯一 SSOT）: 能力 → [本地首选, 云端fallback, 成本档]
  - 例: tts=[kokoro@omlx(0元), qwen3-tts@百炼MCP(按量)] · image=[flux2@phosphene(订阅), TextGenerateImage@百炼(按量)]
- magpie 组路由引用该目录（magpie 管分发，目录管能力语义）；百炼 8 MCP 作为云端 fallback 层挂入门面
- 验收: `aictl check --live` 对每个能力验证主备双通

## 5. 分期与产出物（防 C0：每期必须有非建设性产出）

| 期 | 时间 | 工程内容 | **真实产出物（验收物）** |
|---|---|---|---|
| P0 点亮 | 本周 | E1 全部 | ① 能力表 10/10 截图 ② 首条"日报"由 observer 自动生成并送达 ③ tts/asr 本地回环演示音频 |
| P1 喂活 | 10-11月 | E2 三源 + E3 目录 | ① 每日自动摘要落地 ② BCOS 价值曲线非零 ③ 公开输出首篇由管线辅助产出（S0 对冲） |
| P2 外溢 | 12月-2027Q1 | family-hub 首场景 + 输出管线 | ① 家庭健康档案首条入库（G4）② 公开输出系列 ≥4 篇 |
| P3 愿景 | 不排期 | 组织外溢（合规红线先行：医疗数据不出内网） | — |

## 6. 硬度量（驾驶舱接入，每周对照）

| 指标 | 基线(10-10) | P0 目标 | P1 目标 |
|---|---|---|---|
| 门面调用量/日 | 0 | ≥20 | ≥100 |
| swarm 活跃 agent | 0/6 | 6/6 | 6/6 |
| 事件流 idle | 43min | <60min | <30min |
| aictl 能力可用 | 6/10 | 10/10 | 10/10 |
| 非建设性产出物 | — | 日报×7 | 摘要×30 · 公开输出≥1 |
| 云端费用 | ~0 | 本地优先，百炼按需 | 月度护栏（bl usage stats 周检） |

## 7. 风险与红线
- **C0 复发监测**: 本计划任何一期若"建设投入 > 产出物"，冻结新建设，强制转产出（S1 红线钩子）
- **费用**: 百炼按调用计费；能力目录默认本地优先，云端仅 fallback；`bl usage stats` 周检
- **双机纪律**: 全部改动走 SYNC-MATRIX 既有通道（dotfiles git / local-ops git / magpie 域零接触）；secrets 永不进仓
- **y7000p**: LM Link 池利用率低，P1 评估是否纳入日常调度（Windows 侧稳定性待验）

## 8. P0 立即执行清单
- [ ] `aictl load omlx tts-qwen3 && aictl load omlx tts-kokoro && aictl load omlx asr-whisper`
- [ ] decide 双路验证: laya 部署 or jev-2b 映射（`aictl check --live` decide 场景）
- [ ] `aictl verify quick` → `last-verify.json` 全绿
- [ ] CRON_SIGNALS 确认激活；`make resident-status` events idle 收敛
- [ ] observer 日报首跑并送达（邮件/驾驶舱）
- [ ] tts→asr 回环演示（services.yaml tts_asr 场景）音频落盘
- [ ] 度量基线入驾驶舱（zhixing dashboard 指标卡）
