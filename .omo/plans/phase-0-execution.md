# Phase O: OpenHuman 对标迭代

> **P10**: atlas | **P9**: sisyphus | **P8**: prometheus
> **机制**: MECH-02 治理计划 + MECH-05 Wave 分解
> **总工时**: ~26h | **并行度**: 4 Sprint 可并行 3 个

---

## TL;DR

```
对标 OpenHuman 的 6 个差距 → 4 个 Sprint → 12 个 Wave → 26 个 Task

Sprint O1: 数据入口 (连接器扩展)     7h  ← 最优先
Sprint O2: 智能增强 (Token+Memory)  6h  ← 独立
Sprint O3: 智能推送 (拉→推)         8h  ← 依赖 O1+O2
Sprint O4: 呈现层 (桌面 Agent)      5h  ← 独立 (与 O1 并行)
```

---

## 一、Phase 定义

| 属性 | 定义 |
|------|------|
| **目的** | 对标 OpenHuman 6 个差距，吸收其最精华设计理念 |
| **范围** | 连接器规模化、Token 压缩、Memory Tree、自动同步、智能推送、桌面呈现 |
| **不做的** | 不复制 OpenHuman 代码，不追求 118 个连接器，不做视频会议 Agent |
| **验收** | Iris 连接器 ≥5 个 | Token 压缩上线 | 智能推送原型可工作 | 桌面仪表板升级 |
| **依赖** | O3 依赖 O1+O2；O1/O2/O4 独立可并行 |
| **工作量** | ~26h |
| **评分目标** | 8.8 → 9.2/10 |

---

## 二、Sprint 拆解

### Sprint O1: 数据入口扩展（连接器）

**P9**: sisyphus | **工期**: ~7h | **依赖**: 无（可立即开始）| **目标**: Iris 连接器 2 → 5+

| Wave | Task | 内容 | 角色 | 工时 |
|:----:|:----:|------|:----:|:----:|
| **O1.1** | 1 | Token 压缩层 — Python 模块 | P8 | 2h |
| **O1.2** | 2 | Memory Tree 片段化 — KOS 模块 | P8 | 3h |
| **O1.3** | 3 | 自动同步循环 — ops cron 配置 | P8 | 1h |

### Sprint O2: 智能能力增强

**P9**: sisyphus | **工期**: ~6h | **依赖**: 无（可立即开始）

| Wave | Task | 内容 | 角色 | 工时 |
|:----:|:----:|------|:----:|:----:|
| **O2.1** | 1 | Iris 邮件连接器 (IMAP) | P8 | 2h |
| **O2.2** | 2 | Iris 日历连接器 (CalDAV) | P8 | 2h |
| **O2.3** | 3 | Iris 连接器 OAuth 管理 | P8 | 2h |

### Sprint O3: 智能推送—Unpredictable

**P9**: sisyphus | **工期**: ~8h | **依赖**: O1 + O2

| Wave | Task | 内容 | 角色 | 工时 |
|:----:|:----:|------|:----:|:----:|
| **O3.1** | 1 | KOS pattern_learner — 行为模式学习 | P8 | 4h |
| **O3.2** | 2 | 智能推送规则引擎 | P8 | 2h |
| **O3.3** | 3 | hermes-ops 推送通道 (告警+通知) | P8 | 2h |

### Sprint O4: 呈现层（桌面 Agent）

**P9**: sisyphus | **工期**: ~5h | **依赖**: 无（可立即开始, 与 O1/O2 并行）

| Wave | Task | 内容 | 角色 | 工时 |
|:----:|:----:|------|:----:|:----:|
| **O4.1** | 1 | 桌面 Agent 面板 — HTML+JS | P8 | 3h |
| **O4.2** | 2 | 语音 TTS 集成 (ElevenLabs) | P8 | 2h |

---

## 三、Wave 详细分解（Task Prompt 六要素）

---

### Wave O1.1 — 邮件连接器

**Task Prompt**:

| 要素 | 内容 |
|------|------|
| **目标** | Iris 新增邮件连接器，支持 IMAP 协议读取邮件 |
| **范围** | Iris/connectors/email/ | 实现 connect/read/recent 方法 | 遵循 Obsidian connector 模式 | **不改** 现有 Iris 核心 |
| **验收** | `email/__init__.py` 存在 | `email/connector.py` 实现 IMAP connect()/read() | `python3 -c "from iris.connectors.email import EmailConnector; c=EmailConnector(); print('OK')"` 通过 |
| **依赖** | 无 |
| **输出** | Iris/connectors/email/ |
| **角色** | P8 (Python, IMAP) |

---

### Wave O1.2 — 日历连接器

**Task Prompt**:

| 要素 | 内容 |
|------|------|
| **目标** | Iris 新增日历连接器，支持 CalDAV/iCal 协议读取日历事件 |
| **范围** | Iris/connectors/calendar/ | 实现 connect/sync/events 方法 | **不改** 现有 Iris |
| **验收** | `calendar/__init__.py` + `connector.py` 存在 | 至少支持 iCal 文件导入 + 在线 CalDAV |
| **依赖** | 无 |
| **输出** | Iris/connectors/calendar/ |
| **角色** | P8 (Python, CalDAV) |

---

### Wave O1.3 — Token 压缩层

**Task Prompt**:

| 要素 | 内容 |
|------|------|
| **目标** | 创建 token_compressor.py，在 LLM 调用前压缩文本，降低 80% token 消耗 |
| **范围** | ~/.hermes/scripts/token_compressor.py | HTML→Markdown | 长 URL→short | 非 ASCII 清理 > 去重 > 截断 | **独立脚本**，不修改任何 LLM 调用代码 |
| **验收** | `token_compressor.py` 存在 | `python3 token_compressor.py --stdin < input.html > output.md` 输出 < 输入 50% |
| **依赖** | 无 |
| **输出** | ~/.hermes/scripts/token_compressor.py |
| **角色** | P8 (Python, 文本处理) |

**验证场景**:
```
Scenario: Token 压缩测试
  Tool: Bash
  Precondition: 存在 token_compressor.py
  Steps:
    1. 创建 /tmp/test.html 包含 10KB HTML
    2. python3 ~/.hermes/scripts/token_compressor.py < /tmp/test.html | wc -c
  Expected: 输出 < 5KB (压缩 ≥ 50%)
  Evidence: .omo/evidence/o1.3-token-compress.txt
```

---

### Wave O2.1 — Memory Tree 片段化

**Task Prompt**:

| 要素 | 内容 |
|------|------|
| **目标** | 在 KOS 中创建 memory_card 模块，将知识压缩为 ≤3000 token 的 Markdown 片段 |
| **范围** | KOS kos/kos/memory_card.py | 读取 KOS domain 内容 | 分段 → 压缩 ≤3000t | 写入 SQLite + .md 文件 | **不改** KOS 核心模块 |
| **验收** | `memory_card.py` 存在 | 导入不报错 | `from kos.memory_card import MemoryCard; print('OK')` |
| **依赖** | 无 |
| **输出** | kos/kos/memory_card.py |
| **角色** | P8 (Python, KOS) |

---

### Wave O2.2 — 自动同步循环

**Task Prompt**:

| 要素 | 内容 |
|------|------|
| **目标** | 在 hermes-ops 中配置定时同步任务，每 20 分钟从 Iris 连接器拉取新数据 |
| **范围** | ~/.hermes/ops/config.yaml 新增 schedule | 新增 ops_sync_connector MCP tool | **不改** Iris 代码 |
| **验收** | `crontab -l` 有 `*/20 * * * * hermes-ops --sync-connectors` | `ops_sync_connector()` 返回 sync 结果 |
| **依赖** | O1.1 + O1.2 (连接器必须存在) |
| **输出** | config.yaml 更新 + server.py 更新 |
| **角色** | P8 (Python, hermes-ops) |

---

### Wave O3.1 — 行为模式学习器

**Task Prompt**:

| 要素 | 内容 |
|------|------|
| **目标** | KOS 中创建 pattern_learner.py，从 Iris 采集的行为数据中学习周期性模式 |
| **范围** | KOS kos/kos/pattern_learner.py | 读取 Iris connector 数据 | 检测周期性行为（每日/每周模式） | 输出 pattern 到 ops_event | **不改** Iris 或 hermes-ops 核心 |
| **验收** | `pattern_learner.py` 存在 | `from kos.pattern_learner import PatternLearner; p=PatternLearner(); p.learn()` 不报错 |
| **依赖** | O2.2 (自动同步必须先启动) |
| **输出** | kos/kos/pattern_learner.py |
| **角色** | P8 (Python, KOS) |

---

### Wave O3.2 — 智能推送规则引擎

**Task Prompt**:

| 要素 | 内容 |
|------|------|
| **目标** | KOS 中创建 push_engine.py，从 pattern_learner 的输出自动生成推送规则，而非手动预设规则 |
| **范围** | KOS kos/kos/push_engine.py | 读取 patterns | 生成 ops_alert 规则 | push 到 hermes-ops | **不改** pattern_learner |
| **验收** | `push_engine.py` 存在 | 能根据一个 pattern 生成对应的告警规则 |
| **依赖** | O3.1 |
| **输出** | kos/kos/push_engine.py |
| **角色** | P8 (Python) |

---

### Wave O4.1 — 桌面 Agent 面板

**Task Prompt**:

| 要素 | 内容 |
|------|------|
| **目标** | 创建桌面 Agent 面板 — 一个始终运行的本机 Web 仪表板，显示 Agent 状态、最近事件、推送通知 |
| **范围** | ~/.hermes/agent-panel.html | 读取 hermes-ops 数据 | 显示: Agent 状态/最近事件/告警/活跃连接器/系统指标 | 5 秒自动刷新 | **不改** hermes-ops |
| **验收** | `agent-panel.html` 存在 | 浏览器打开后 5 秒内显示仪表板 | 数据从 hermes-ops 拉取 |
| **依赖** | 无 |
| **输出** | ~/.hermes/agent-panel.html |
| **角色** | P8 (HTML/JS/CSS) |

---

### Wave O4.2 — 语音 TTS 集成

**Task Prompt**:

| 要素 | 内容 |
|------|------|
| **目标** | 集成 ElevenLabs TTS + 系统文本到语音，让 AI 可以通过语音表达 |
| **范围** | ~/.hermes/scripts/ops_tts.py | 调用 ElevenLabs API | 文本→语音→文件播放 | **不改** 任何核心模块 | 可选: 集成到 hermes-ops 作为 alert 通知方式 |
| **验收** | `ops_tts.py` 存在 | `python3 ops_tts.py "hello"` 生成音频文件 |
| **依赖** | 无 |
| **输出** | ~/.hermes/scripts/ops_tts.py |
| **角色** | P8 (Python, API 集成) |

---

## 四、Commit 策略

| Sprint | Commit 消息 |
|:------:|-------------|
| O1 | `feat(iris): add email + calendar connectors` |
| O1 | `feat(ops): add token compressor module` |
| O2 | `feat(kos): add memory card ≤3000t fragment` |
| O2 | `feat(ops): connector auto-sync every 20min` |
| O3 | `feat(kos): add pattern learner + push engine` |
| O3 | `feat(ops): intelligent push notification channel` |
| O4 | `feat(ops): desktop agent panel + voice TTS` |

---

## 五、最终验收

- [ ] Iris 连接器 ≥5 (当前 2 → obsidian/telegram/email/calendar/计划中的)
- [ ] token_compressor 压缩 ≥50%
- [ ] memory_card ≤3000t 片段化
- [ ] 20 分钟自动同步循环运行
- [ ] pattern_learner 可识别 1+ 行为模式
- [ ] push_engine 可根据 pattern 自动生成规则
- [ ] 桌面 Agent 面板可显示系统状态
- [ ] ops_tts 可语音输出
- [ ] 全量: `make test` 全部通过
