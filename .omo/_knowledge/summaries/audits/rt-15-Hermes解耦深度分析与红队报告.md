# 深度分析与红队报告：Hermes 解耦蓝图

> 对《14-Hermes解耦蓝图与Roadmap》的批判性审计。
> 方法论：5维深度分析（推演链·自洽性·实现差距·完整性·相位校准）+ 10+红队攻击向量

---

## 一、推演链分析：从用户约束到架构设计

### 用户核心约束

| 约束 | 来源 | 对架构的约束 |
|------|------|-------------|
| 脱离 Hermes 无本质变化 | 明确要求 | 所有关键路径必须有独立替代 |
| 零 token 成本偏好 | 记忆 | no_agent 脚本优先于 Agent 推理 |
| 渐进替代，非一刀切 | 推理 | 双轨并行周期 |
| 可靠性敏感 | 记忆 | 服务波动立刻报警 |
| 架构先行，理论驱动 | 性格 | 方案必须先通过审计再执行 |

### 推演链

```
约束: 脱离Hermes无本质变化
  → 需要替代 4 个运行时基础设施
    → Agent对话循环 → L3 Agent Runtime
    → 平台网关     → L4 Gateway
    → Cron调度器   → L2 系统crontab
    → WeChat发送   → L1 weixin_send.py

约束: 渐进替代
  → Phase 1: L1+L2（最独立、最易替换）
  → Phase 2-3: L3（中等复杂度）
  → Phase 4: L4（最复杂）

约束: 零token成本
  → 8个no_agent脚本先迁移（Phase 1）
  → Agent Runtime只用于必须LLM推理的cron任务
```

**推演链结论**: ✅ 架构选择追随用户约束，无断裂

---

## 二、自洽性分析：矛盾检测

### 矛盾 #1: "底层独立" vs "weixin_send.py 依赖 iLink"

| 项 | 内容 |
|---|------|
| **规则A** | L1 层应完全独立，不依赖任何外部运行时（14号文档） |
| **规则B** | weixin_send.py 需要通过 curl 调 iLink API 发消息 |
| **矛盾** | iLink API 是 Hermes gateway 的核心能力——如果 Hermes 完全停用，iLink API 是否还在？ |
| **严重度** | 🔴 P0 |

**分析**: Hermes 的 WeChat 发送不是通过一个独立的 REST API 实现的——它是 Hermes gateway 内部 iLink 插件的一部分。这个插件在 gateway 进程内运行，维护与 ihome.link 的长连接。如果 Hermes gateway 停用，iLink 连接也断了。

**修复**: 需要梳理 Hermes gateway 的 WeChat 发送机制。有两个可能：
1. 如果是 **HTTP API 调用 ihome.link 服务端** → weixin_send.py 可以直接 curl 调，独立运行
2. 如果是 **gateway 进程内的长连接**（WebSocket to iLink）→ 需要自己维护长连接或部署独立发送服务

**需要实测验证（Task 0）。**

### 矛盾 #2: "Hermes 停用时无本质变化" vs "MCP 工具名会变"

| 项 | 内容 |
|---|------|
| **规则A** | Hermes 停用时所有能力不变 |
| **规则B** | 当前 11 个 LLM cron 的 prompt 中使用 `mcp_kos_*`、`mcp_agora_*` 等工具名 |
| **规则C** | Agent Runtime 通过 HTTP 直接调 MCP 服务器，不经过 Hermes 的 MCP client |
| **矛盾** | Agent Runtime 调用 MCP 工具时，工具名和参数格式可能与 Hermes 的不一致（取决于 MCP server 暴露的接口名） |
| **严重度** | 🟡 P1 |

**分析**: 现有的 cron prompt 是写给 Hermes Agent 的，Hermes Agent 把 `mcp_kos_search_knowledge` 这个工具名映射到背后 KOS MCP server 的调用。如果 Agent Runtime 直接 HTTP 调 KOS MCP server，工具名可能是 `search_knowledge`（少了 `mcp_kos_` 前缀）。需要验证。

**修复**: 
1. 在 Agent Runtime 中做一个工具名映射层（`mcp_kos_*` → `*`），保持 prompt 兼容
2. 或者重写 cron prompt（工作量更大，但更干净）

建议方案1，这是最小变更。

### 矛盾 #3: "双轨并行" vs "数据冲突"

| 项 | 内容 |
|---|------|
| **规则A** | 双轨并行：Hermes cron + 系统 cron 同时跑同一些任务 |
| **规则B** | 某些任务有副作用（如 WF-008 Kanban→SSB 桥接每5分钟写一次数据库） |
| **矛盾** | 如果两个系统同时执行同一任务，可能产生重复事件、重复索引、重复推送 |
| **严重度** | 🟡 P2 |

**修复**: 
- 双轨并行期间，系统 cron 的脚本不做任何"写入"操作，只做"读取+通知"
- 或者：系统 cron 先跑，Hermes cron 延迟一小时后禁掉
- 或者：共享状态锁（但太复杂了）

推荐策略：**逐个迁移、逐个关停**。迁移一个 cron job → 确认运行正常 → 关掉 Hermes 中对应的 job → 验证 → 下一个。

---

## 三、实现差距分析

### 差距 #1: WeChat iLink 接口未知

| 假设 | 事实 | 差距 |
|------|------|------|
| weixin_send.py 可以用 curl 调 iLink API 发消息 | 不知道 iLink API 的具体 URL、认证方式、请求格式 | ❓ 严重未知 |

这是 **整个解耦计划的最大风险**。如果没有独立的 WeChat 发送能力，Phase 1 就无法开始。

**缓解方案**: 
1. 先审计 Hermes gateway 的 WeChat 发送代码（找出 iLink 调用方式）
2. 如果 iLink 需要长连接 → 研究能不能跑一个"仅发送"的简化 gateway
3. 如果 iLink 支持独立 HTTP API → 直接 curl

**建议**: 在 Phase 1 之前增加 **Task 0: iLink 接口调研**。

### 差距 #2: cron_wrapper.sh 环境问题

| 假设 | 事实 |
|------|------|
| system crontab 能直接跑脚本 | macOS 的 cron 环境变量很少：PATH 只有 `/usr/bin:/bin`，无 `~/.zshrc`、无 `~/.bashrc`、无 brew 的 PATH |
| PYTHONPATH 和 API keys 能正确传递 | 脚本依赖的环境变量（API keys、KOS_HOME、HERMES_HOME 等）需要显式 source |

**缓解方案**: cron_wrapper.sh 必须：
```bash
#!/bin/bash
source /Users/xiamingxing/.zshrc  # 或 .bash_profile
export HERMES_HOME=${HERMES_HOME:-/Users/xiamingxing/.hermes}
export KOS_HOME=${KOS_HOME:-/Users/xiamingxing/.kos}
# ... 其他必需变量
cd /Users/xiamingxing/Workspace
exec "$@"
```

### 差距 #3: Agent Runtime 的 MCP 调用需要 HTTP 端点

| 假设 | 事实 |
|------|------|
| KOS/Agora/Minerva 的 MCP 服务器都有 HTTP 端点 | ✅ 确实有——Agora :7430, KOS :7420, Minerva :8765 |
| 这些服务常驻运行 | ❓ 不一定——Minerva 是按需启动的，Agora 和 KOS 的 MCP 可能由 Hermes 拉起 |

**缓解方案**: 
- 检查每个 MCP server 是否是常驻服务（launchd/systemd）
- 如果不是，Agent Runtime 需要先拉起服务再调用
- 或者在 Agent Runtime 中内置进程管理（启动→调用→停止）

### 差距 #4: 8 个 no_agent 脚本中还有 Hermes 残留依赖

| 脚本 | 已知依赖 | 潜在问题 |
|------|---------|---------|
| ecos-watchdog.sh | 无 | 直接用 Bash 调 eCOS 脚本 |
| hermes-event-watcher.py | `AGORA_EVENTS_FILE` env，STATE_FILE 用 `HERMES_HOME` | ✅ 已解耦（env var） |
| wpsnote-kos-sync.py | WPS KEY 硬编码 | KEY 在脚本里硬编码，迁移时一起带走即可 |
| workspace-git-sync.py | 未知 | 需要检查 |
| daily-todo.sh | 未知 | 需要检查 |

**缓解方案**: Phase 1 前做逐个检查，记录每个脚本的真实依赖。

---

## 四、完整性分析

### 缺少的机制

| 机制 | 当前状态 | 需要补充 |
|------|---------|---------|
| **SILENT 协议** | Hermes cron 内置：输出 `[SILENT]` = 不推送 | cron_wrapper.sh 需要自己实现 |
| **重试机制** | Hermes cron 自动重试（失败后下一次 tick） | 系统 crontab 不自动重试 |
| **执行历史** | Hermes cron 的 `last_run_at`、`last_status`、错误日志 | 系统 crontab 默认只有 `/var/mail/`；需要自建 execute log |
| **失败通知** | Hermes cron 把 `last_error` 记录在 jobs.json 中 | 需要 weixin_send.py 在脚本失败时主动通知 |
| **频率限制** | Hermes gateway 内置微信 rate limit 管理 | weixin_send.py 需要内置排队/限流 |
| **看门狗** | Hermes cron 定期检查自身是否健康 | 系统 crontab 不检查自身 |
| **锁机制** | Hermes cron 有 `.tick.lock` 防并发 | 需要自建（或依赖 system crontab 的 flock） |
| **日志追踪** | Hermes 有 agent.log / errors.log / gateway.log | cron_wrapper.sh 需要写自己的日志 |

### 缺失的功能——优先级 P2

这些不是"必须"，但如果没有，用户体验下降：

1. **执行历史看板** — 以前 `hermes cron list` 能看到所有 job 状态，系统 crontab 没有
2. **手动触发** — `hermes cron run <job_id>` → 需要手动跑脚本
3. **推送去重** — 双轨并行期间同一消息被推两次
4. **临时暂停** — `hermes cron pause/resume` → 需要注释/取消注释 crontab 行

---

## 五、相位校准：Phase 1 的真实模样

### 文档说 VS 实际做

| Phase 1 声称 | 实际需要 |
|-------------|---------|
| 1 周，10 tasks | ⚠️ 至少需要先加 Task 0（iLink 调研），可能 1-2 周 |
| T1.1 weixin_send.py 半天 | ⚠️ 如果 iLink 需要长连接，可能是 2-3 天 |
| 其余任务各 1h | ✅ 合理——都是简单脚本包装 |
| E2E 验证半天 | ⚠️ 需要先确认"E2E 通过"的标准是什么 |

### 实际 Phase 1 时间线（修正版）

```
Task 0: iLink 接口调研 & weixin_send.py 原型     2-3天  ← 关键路径！
T1.1:  weixin_send.py 完整版 (含限流/重试/日志)    1天
T1.2:  cron_wrapper.sh + 失败通知                   1天
T1.3-10: 逐个迁移 8 个 no_agent 脚本               1天
T1.11: E2E 验证                                    0.5天
──────────────────────────────────────────
Total: 约 5.5 - 7.5 天
```

**关键**: Task 0 决定 Phase 1 能不能做。如果 iLink 需要长连接且不可拆，需要重新评估整个方案。

---

## 六、红队分析：10 个攻击向量

### Attack #1: iLink 单点失效 🔴 P0

| 属性 | 内容 |
|------|------|
| **向量** | weixin_send.py 依赖 iLink API。如果 iLink 接口变更、过期、或需要 gateway 进程内长连接，整个消息通道中断 |
| **影响** | 所有 cron 推送全部消失。系统成为"哑巴" |
| **现有防御** | 无——当前没有任何备选通知通道 |
| **建议修复** | **Phase 0 就必须验证 iLink 的可独立性。** 同时准备备选：邮件/本地通知/Slack webhook |

### Attack #2: 凭证泄露 🔴 P0

| 属性 | 内容 |
|------|------|
| **向量** | weixin_send.py 需要 WeChat iLink 的 API Key。这个 Key 将明文存在脚本或环境变量中 |
| **影响** | Key 泄露 → 攻击者可以冒充你发消息 |
| **现有防御** | 当前 Hermes gateway 用 `.env` 文件管理 Key |
| **建议修复** | 1. 用 1Password CLI 管理 Key（用户使用 1password） 2. 或 macOS Keychain 3. 或加密 env 文件 |

### Attack #3: SILENT 协议误判 🟡 P1

| 属性 | 内容 |
|------|------|
| **向量** | cron_wrapper.sh 检查 stdout 是否为 `[SILENT]`。如果脚本崩溃了（没有 stdout），误判为 SILENT——真正的故障被掩盖 |
| **影响** | 脚本挂了但没人知道。可能几天后才发现 |
| **现有防御** | Hermes cron 有 `last_status` 跟踪 |
| **建议修复** | cron_wrapper.sh 检查 exit code：只有 exit code=0 且输出为 SILENT 才静默；exit code≠0 → 告警 |

### Attack #4: 环境变量扩散 🟡 P1

| 属性 | 内容 |
|------|------|
| **向量** | 8 个 no_agent 脚本各需要不同的环境变量。cron_wrapper.sh 需要知道所有变量。漏掉一个就挂一个脚本 |
| **影响** | 迁移后某个脚本异常，原因难以排查 |
| **建议修复** | 统一在 `~/.hermes/scripts/common_paths.py` 中定义所有路径，`cron_wrapper.sh` source `~/.zshrc` + `~/.hermes/.env` |

### Attack #5: Cron 并发执行 🟡 P2

| 属性 | 内容 |
|------|------|
| **向量** | 系统 crontab 不防并发。如果一个脚本执行超过间隔时间，两个实例同时运行 |
| **影响** | 数据竞争、重复推送。特别是 Watchdog（每5m）和 EventWatcher（每5m） |
| **建议修复** | cron_wrapper.sh 用 `flock`（macOS 有 `/usr/bin/flock`）或 PID 文件防并发 |

### Attack #6: 无监控报警 🟡 P1

| 属性 | 内容 |
|------|------|
| **向量** | Hermes 移走后，没有 dashboard 可以看到所有 cron 的运行状态。一个脚本默默坏了，没有人知道 |
| **影响** | 可靠性的致命下降——正与用户的"可靠性敏感"背道而驰 |
| **建议修复** | 1. 每个脚本写执行日志到 `$HERMES_HOME/cron/output/<job_name>/`（已有） 2. 增加每日汇总 cron 来检查所有 job 前 24h 是否都跑过 3. 连续失败 N 次 → 微信告警 |

### Attack #7: 线程安全问题 🟢 P3

| 属性 | 内容 |
|------|------|
| **向量** | weixin_send.py 如果同时被多个 cron 调用，可能并发发消息——导致微信 rate limit 触发 |
| **建议修复** | 用一个简单的锁文件 + 排队机制（或直接用 `flock`） |

### Attack #8: 路径回退 🟢 P3

| 属性 | 内容 |
|------|------|
| **向量** | 脚本迁移到 Workspace 后，如果 `common_paths` 的 `HERMES_HOME` 忘记设置，所有脚本回退到默认 `~/.hermes` |
| **影响** | 迁移后系统还在读旧路径——产生"我到底解耦了没有"的困惑 |
| **建议修复** | 每个脚本启动时打印一行日志：`[BOOT] HERMES_HOME=/custom/path` |

### Attack #9: Phase 4 作为前提 🔴 P0

| 属性 | 内容 |
|------|------|
| **向量** | 蓝图把 L4（平台网关）放在 Phase 4，但 L4 的"收消息"能力是整个系统"无本质变化"的关键——如果不收消息，你就无法通过微信跟系统交互 |
| **影响** | Phase 1-3 完成后，你可以发出消息但收不到回复——系统变单向通道了 |
| **建议修复** | 这其实是 OK 的——系统的核心价值是 cron 推送 + 知识服务，即时对话是 Hermes 的增值功能。但需要明确告知用户：**Phase 4 之前系统是"只推送不接收"的** |

### Attack #10: 测试策略缺失 🟡 P2

| 属性 | 内容 |
|------|------|
| **向量** | 没有独立于 Hermes 的 E2E 测试。如何确保迁移后一切正常？ |
| **建议修复** | 每个 Phase 完成后，手动关掉 Hermes 对应功能 24h 验证。具体：|
| | Phase 1 完成后 → shutdown Hermes cron → 24h 内所有 Webhook 正常推送 |
| | Phase 3 完成后 → 同时 shutdown Hermes cron + Gateway → 48h 全链路 |

### Attack #11: 锁定效应 🔴 P0

| 属性 | 内容 |
|------|------|
| **向量** | 我们的所有 cron prompt 是用中文写给 Hermes Agent 的（"检查文件完整性"、"跑 capture_watcher.py"）——这些 prompt 与 Hermes 的理解能力绑定。如果 Agent Runtime 使用的 LLM 版本/模型不同，理解能力不同，同一个 prompt 在不同模型下行为不一致 |
| **影响** | WF-003 健康检查在 DeepSeek V4 下可能输出与在 GLM-5 下不同的格式/内容 |
| **建议修复** | 1. Agent Runtime 固定模型（不跟随默认模型切换）2. 为每个 LLM cron 写更精确的 prompt（指定输出格式）3. 在 E2E 测试中检查输出格式的稳定性 |

### 红队评分矩阵

| # | 攻击 | 影响 | 检测难度 | 优先级 |
|---|------|------|---------|--------|
| A1 | iLink 单点失效 | 🔴 系统变哑巴 | 🟢 立即可发现 | **P0** |
| A11 | 锁定效应（模型差异） | 🔴 输出不一致 | 🟡 需要对比 | **P0** |
| A2 | 凭证泄露 | 🔴 安全事件 | 🔴 事后才发现 | **P1** |
| A3 | SILENT 误判 | 🟡 故障被掩盖 | 🔴 默默恶化 | **P1** |
| A4 | 环境变量扩散 | 🟡 脚本异常 | 🟡 排查困难 | P1 |
| A6 | 无监控报警 | 🟡 可靠性下降 | 🔴 直到出事才知道 | P1 |
| A9 | 单向通道 | 🟡 用户体验降级 | 🟢 已知限制 | P2 |
| A5 | 并发执行 | 🟢 数据竞争 | 🟢 可监控 | P2 |
| A10 | 测试策略缺失 | 🟡 回归风险 | 🟢 可建立 | P2 |
| A7 | 线程安全 | 🟢 率限触发 | 🟢 可监控 | P3 |
| A8 | 路径回退 | 🟢 混淆 | 🟢 可见 | P3 |

---

## 七、修复建议（按优先级）

### P0: 必须先解决的问题

```
1. Task 0: iLink 接口调研
   └─ 审计 Hermes gateway 的 WeChat 发送代码
   └─ 确认：iLink 是独立 HTTP API 还是 gateway 内部长连接
   └─ 输出：iLink 调用方式文档 + weixin_send.py 原型
   └─ **如果 iLink 必须走长连接，取消 Phase 1，重新评估方案**

2. Agent Runtime 模型固定
   └─ agent_runtime.py 必须显式指定模型名
   └─ 不跟随默认 model 切换
   └─ 增加输出格式校验（cron prompt 中加入"输出格式要求"）

3. E2E 验证标准文档化
   └─ 定义"Hermes 停用无本质变化"的度量标准
   └─ 写一个 e2e_decoupled_test.py
```

### P1: 这一两周解决

```
4. SILENT 协议安全加固
   └─ cron_wrapper.sh 检查 exit code
   └─ exit≠0 → 推送错误告警
   └─ stdout 为空但 exit=0 → 视为 SILENT（兼容性）

5. 凭证管理
   └─ iLink Key 放入 1password 或 macOS Keychain
   └─ cron_wrapper.sh 从安全存储读取

6. 监控/日志系统
   └─ 每个 cron 执行写日志：时间、exit code、输出摘要
   └─ 每日汇总 cron：检查所有 job 前 24h 是否都跑过
   └─ 连续 N 次失败 → 微信告警
```

### P2: 这个月解决

```
7. 双轨并行管理
   └─ 逐个迁移 + 逐个关停 Hermes cron
   └─ 不要同时跑两个版本

8. 通知备选通道
   └─ 邮件作为 WeChat 不可用时的备选
   └─ 或本地日志通知 (macOS notification)

9. 执行历史
   └─ 轻量 SQLite 表记录执行历史
   └─ cron_audit: job_id, run_at, exit_code, output_hash, delivered
```

---

## 八、结论

### 方案总体可行，但有 3 个必须解决的前置问题

| # | 问题 | 如果不过 |
|---|------|---------|
| 1 | **iLink 必须可独立 HTTP 调用** | ❌ 整个方案无法执行 |
| 2 | **Agent Runtime 的模型必须固定** | ⚠️ 输出不稳定，cron 任务行为不确定 |
| 3 | **必须有 E2E 验证标准** | ⚠️ 不知道什么时候才算做完 |

### 修正后的 Roadmap

```
Phase 0 (调研+原型):  Task 0 iLink调研 + weixin_send.py 原型    3天
Phase 1 (快速赢):     8个no_agent脚本迁移                       5天
Phase 2 (Agent基础):  Agent Runtime + 4个轻LLM任务迁移          5天
Phase 3 (完善):       剩余7个LLM任务迁移                       7天
Phase 4 (收尾):       Gateway + 数据迁移                       5天
                      ───────────────────
                      总计 ~25天（5周）
```

### 健康评分基线

```
D1 - 愿景达成度: 75  (方案清晰但 iLink 未验证)
D2 - 场景覆盖度: 80  (20个cron全部有替换路径)
D3 - 完整性:     70  (iLink未知、监控缺、E2E标准缺)
D4 - 功能成熟度: 50  (还没开始做)
D5 - 架构成熟度: 85  (5层设计合理，自洽性好)
D6 - 熵:        70  (红队发现8个P1以上问题)
D7 - 安全/质量:  70  (凭证、SILENT误判未解决)
D8 - 债务:       90  (方案干净，无历史包袱)
D9 - 成本:       95  (几乎零token成本)
```

**总结**: 方案本身设计合理（D5=85），但执行风险在 iLink 调研结果（D7=70，D1=75）。建议先做 Task 0 再决定是否全面启动。
