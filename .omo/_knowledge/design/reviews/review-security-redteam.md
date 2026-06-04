# 安全红队对抗性审阅报告: Task Center

> **审阅对象**: [task-center-requirements.md](../task-center-requirements.md) (v0.1, 草案)
> **审阅日期**: 2026-05-31
> **审阅类型**: 对抗性安全分析 (Red Team)
> **审阅范围**: RCE / 权限逃逸 / 敏感信息泄露 / SQLite 并发 / SSRF & webhook 伪造 / 供应链攻击 / 凭据管理 / 文件系统事件攻击 / 日志信息泄漏

---

## 摘要

Task Center 需求文档对安全性有初步意识（非功能性需求中声明了"子进程隔离 + 权限白名单"），但**多处关键安全机制缺失实现细节或存在根本性设计缺陷**。最严重的问题集中在：(1) 子进程执行未指定安全参数，存在 shell 注入风险；(2) webhook HMAC secret 的存储和管理方案缺失；(3) 多个 SQLite 写入路径存在并发竞争条件；(4) hermes symlink 桥接层构成经典的 TOCTOU / symlink 遍历攻击面。当前文档处于草案阶段，建议在进入实施前修复所有 CRITICAL 和 HIGH 级别发现。

---

## CRITICAL 发现

### C-1: 子进程执行缺少 shell 注入防护 (RCE)

| 属性 | 内容 |
|------|------|
| **攻击路径** | `executor.execute()` 复用自 cron-service，文档未指定是否使用 `shell=True`。若使用 `shell=True`，registry.yaml 中的 `script` 字段（如 `kos-index.sh`）即便无用户直接输入，**任务创建/更新 MCP 工具传入的 script 路径若包含 shell 元字符**（如 `; rm -rf /`、`$(malicious)`、`| cat /etc/passwd`），则为 RCE 向量。即使 script 值在 registry.yaml 中经 MCP 写入，攻击面在于：MCP 客户端被攻陷 / registry.yaml 写权限被滥用 → 注入恶意脚本路径。 |
| **影响组件** | 执行层 Executor, `executor.execute()`, subprocess.Popen |
| **严重级别** | **CRITICAL** |
| **建议修复** | • 始终使用 `subprocess.Popen([script_path, ...], shell=False)` 列表形式调用，禁用 `shell=True`<br>• `script` 路径在传入 executor 前做严格校验：必须是 `~/.hermes/scripts/` 下的直接子项（禁止 `../` 目录遍历）<br>• MCP 工具 `task_create`/`task_update` 写入 script 前做路径规范化 + 白名单检查 |

### C-2: 凭据存储方案缺失 — 所有私密信息疑似明文存储

| 属性 | 内容 |
|------|------|
| **攻击路径** | 文档多处提及敏感信息存放位置但均无加密方案：<br>1. **iLink token**：「存储在 `~/.cron-service/config.yaml` 非 registry.yaml」— 但 config.yaml 本身未说明是否加密<br>2. **webhook secret**：「存储在 `_secret/` 而非 registry.yaml 明文」— 但 `_secret/` 的存储机制、加密方案、访问控制完全未定义<br>3. **HMAC secret** 被引用为 `<SHA256-HMAC-SECRET>` 占位符 — 若实际实施时变成明文 YAML 字段则为数据泄露<br>若这些凭据以明文存储在磁盘上，任何能读取文件系统的进程（包括被漏洞利用的子进程）均可窃取。 |
| **影响组件** | 注册层 Registry, config.yaml, `_secret/` 目录（未定义） |
| **严重级别** | **CRITICAL** |
| **建议修复** | • 定义 `_secret/` 目录的规范：加密存储（如 age/sops 加密 YAML），运行时解密到内存<br>• iLink token 至少使用 base64 编码 + 文件权限 `600`，建议集成系统密钥链（macOS Keychain) 或环境变量注入<br>• webhook secret 生成时使用 `secrets.token_hex(32)`，存储到加密 vault<br>• 添加文档约束：registry.yaml 中**禁止**包含任何 `secret`/`token`/`password` 字段 |

### C-3: webhook HMAC 实现缺少安全比较方法

| 属性 | 内容 |
|------|------|
| **攻击路径** | HMAC 签名验证若使用 `==`（字符串比较）而非 `hmac.compare_digest()`，则存在**时序侧信道攻击**。攻击者可通过逐字节测量响应时间差伪造有效签名。结合 SSRF 攻击（诱使内部服务发送伪造请求），可在无 secret 的情况下绕过认证。 |
| **影响组件** | webhook 端点, HMAC 验证中间件 |
| **严重级别** | **CRITICAL** |
| **建议修复** | • 强制使用 `hmac.compare_digest(signature, computed)` 进行签名比对<br>• 在代码规范中明确：**禁止**使用 `==`/`!=` 比较 HMAC 签名<br>• 建议在验收检查清单中添加此项（当前 7.4 安全验收缺失此项） |

---

## HIGH 发现

### H-1: 多进程 SQLite 并发写入竞争条件

| 属性 | 内容 |
|------|------|
| **攻击路径** | `cron.db`（SQLite）被多个进程并发操作的可能性：<br>• HTTP webhook 端点写入触发记录<br>• MCP 工具读写任务状态<br>• 调度层 (scheduler) 持续读取/写入 tick 状态<br>• `omo task-center sync` CLI 同步操作<br>SQLite 默认串行化写入（单个 writer），但多进程同时写入时若未启用 WAL 模式，写入者会阻塞读取者，极端情况下可导致 `SQLITE_BUSY`（5）错误，造成任务丢失触发或状态不一致。文档在 R2（registry.yaml 与 SQLite 不一致）中提到了风险，但**未解决多 writer 竞争**。 |
| **影响组件** | SQLite cache layer, cron.db, Scheduler + MCP + HTTP 三路并发 |
| **严重级别** | **HIGH** |
| **建议修复** | • 启用 WAL 模式 (`PRAGMA journal_mode=WAL;`) — 允许并发读写，但不能解决多 writer 互斥<br>• 引入**单点写入代理**：所有写操作通过 scheduler 进程的 write queue 串行化；MCP/HTTP 仅做 reads，如需写入通过 IPC(Unix socket / 消息队列) 发送给 scheduler<br>• 设置 SQLite busy timeout (`PRAGMA busy_timeout=5000;`) 减少冲突<br>• 考虑使用 SQLite 的 `BEGIN IMMEDIATE` 事务开始方式 |

### H-2: script 路径的目录遍历与 TOCTOU 攻击

| 属性 | 内容 |
|------|------|
| **攻击路径** | registry.yaml 中的 `script` 字段路径解析存在两条攻击向量：<br>1. **目录遍历**: script 路径被记录为 `kos-index.sh` 但实际执行可能被拼接为 `~/.hermes/scripts/kos-index.sh`。若攻击者可在 MCP 调用链中注入 `../../.secret/steal.sh`，则可能执行任意路径的脚本<br>2. **TOCTOU (Time-of-Check Time-of-Use)**：`task_check` 断裂检测先行校验 script 文件存在性，但 executor 执行时可能已指向不同的目标文件（通过 symlink 切换）。文档 4.2.3 要求在创建时校验，但未说明执行时是否重新校验。 |
| **影响组件** | 注册层 Registry, 执行层 Executor, `~/.hermes/scripts/` |
| **严重级别** | **HIGH** |
| **建议修复** | • script 路径做规范化 (`os.path.realpath`) + 前缀检查（必须落在 `~/.hermes/scripts/` 内）<br>• 每次执行前**重新校验** script 可达性（"执行时校验"而非仅"创建时校验"）<br>• 执行时 resolve symlink 后检查目标不在 `~/.hermes/scripts/` 之外 |

### H-3: webhook 端点 SSRF 与 DoS 攻击面

| 属性 | 内容 |
|------|------|
| **攻击路径** | webhook 端点通过 HTTP POST 触发，存在以下攻击面：<br>1. **SSRF**: 若 webhook 端点未验证 `Host` header 或来源 IP，攻击者可通过内网 SSRF 跳板（如 SSRF-vulnerable 内部服务）向 `/hooks/deploy` 发送伪造请求触发任务<br>2. **DoS**: 文档设置了 10 次/分钟速率限制，但未说明限制粒度（per path？global？）和实现方式（内存计数？Redis？）。若不区分 path，单个路径的攻击可耗尽所有路径的配额。若速率限制重启后丢失，攻击者可无限重试<br>3. **大请求体攻击**: 文档设置了 1MB 限制，但未说明在**何处**执行此限制。若在读取完整请求体后才校验大小，1MB x 10次/分钟 的持续流量可能消耗内存带宽。 |
| **影响组件** | webhook HTTP 服务, 观测层 Observability |
| **严重级别** | **HIGH** |
| **建议修复** | • SSRF防御：验证 `Host` header 为已注册的 webhook path；可选 IP 白名单应在请求**解析前**拒绝<br>• 速率限制实现：使用固定窗口 + per-path 计数，持久化到 SQLite（防止重启丢失），或使用令牌桶算法<br>• 请求体限制：在 HTTP 头部解析后立即使用 `Content-Length` 拒绝 → 若超限直接 `413 Payload Too Large`，不读取 body<br>• 对未认证（无有效 HMAC）的请求也应计数到速率限制中 |

### H-4: 文件系统事件监听 — symlink 遍历与资源耗尽

| 属性 | 内容 |
|------|------|
| **攻击路径** | event 类型 `watch` 目录存在两个攻击面：<br>1. **Symlink 遍历**: 若监听的目录内存在恶意 symlink 指向外部（如 `/etc/passwd`），inotify/kqueue 可能递归跟踪 symlink，导致触发本不应触发的文件变更事件<br>2. **inotify 资源耗尽**: Linux inotify 有 `/proc/sys/fs/inotify/max_user_watches` 限制（默认 8192）。若用户注册大量 event 任务监听多个目录，可耗尽 inotify watches，导致系统级文件监听失效。macOS kqueue 也有类似限制 (`kern.maxkernelsum`)。 |
| **影响组件** | 事件系统, event 类型任务, 操作系统内核资源 |
| **严重级别** | **HIGH** |
| **建议修复** | • 监听器层跳过 symlink 目标（`kqueue` 使用 `NOTE_NOINTR` 但不防 symlink，需应用层过滤）<br>• 添加全局 watch 数量上限（如 10 个目录、1000 个文件）<br>• 启动时检查可用 inotify/kqueue 资源，若接近上限拒绝注册新 event 任务<br>• 添加 `max_depth` 参数控制递归深度 |

### H-5: 子进程无隔离 — 可修改 registry.yaml 本身

| 属性 | 内容 |
|------|------|
| **攻击路径** | 文档非功能性需求要求"子进程隔离 + 权限白名单"，但**无具体实现方案**。子进程（由 `executor.execute()` 启动的脚本）与 Task Center 主进程共享相同用户权限。攻击者若通过 RCE（C-1）执行恶意脚本，可：<br>1. 直接写入 `_truth/task-center/registry.yaml` 篡改其他任务<br>2. 读取 `~/.cron-service/config.yaml` 窃取 iLink token<br>3. 创建新的 cron job 实现持久化<br>4. 修改 `_secret/` 中的凭据<br>子进程与主进程之间**没有强制访问控制 (MAC) 或 seccomp/AppArmor 约束**。 |
| **影响组件** | 执行层 Executor, 注册层 Registry, config.yaml, `_secret/` |
| **严重级别** | **HIGH** |
| **建议修复** | • **即时修复**：确保 Task Center config 和 registry.yaml 文件权限为 `600` 或 `640`，主进程以单独用户运行，子进程以不同（更低权限）用户执行<br>• **深入加固**：基于操作系统能力：macOS 使用 sandbox-exec(1) 或 Seatbelt 沙箱限制子进程的文件系统/网络访问；Linux 使用 systemd 的 `ProtectSystem=strict` + `NoNewPrivileges=true` + `CapabilityBoundingSet`<br>• 或使用 Docker 容器包装高风险脚本执行<br>• 在 registry.yaml 中为每个任务声明所需的最小权限（白名单模式） |

---

## MEDIUM 发现

### M-1: 日志 output_snippet / error_snippet 可能泄漏敏感信息

| 属性 | 内容 |
|------|------|
| **攻击路径** | 运行记录 JSON 中 `output_snippet` 和 `error_snippet` 字段可能包含：<br>• 脚本输出中打印的 API key / token / secret<br>• 数据库连接字符串（含密码）<br>• webhook POST body 回显（若脚本 echo 了包含 secret 的 payload）<br>这些记录持久化在 `_delivery/task-center/runs/` 中，若此目录权限不足或同步到 Git，则构成敏感信息泄露。 |
| **影响组件** | 观测层 Observability, 运行记录存储 |
| **严重级别** | **MEDIUM** |
| **建议修复** | • 在写入前对 output/stderr 进行正则过滤（匹配 `token=`, `secret=`, `password=`, `api_key` 等模式的键值对，替换为 `***REDACTED***`）<br>• 可配置每个任务级别的日志脱敏规则（`redact_patterns` 字段）<br>• 运行记录目录 `_delivery/task-center/runs/` 设置 `600` 权限，且 **gitignore**（不在需求文档中，但应注明） |

### M-2: iLink delivery 投递无完整性验证

| 属性 | 内容 |
|------|------|
| **攻击路径** | 任务执行结果通过 iLink 微信投递时，`output_snippet` / `error_snippet` 通过 iLink token 认证发送。文档未说明投递是否使用 HTTPS（TLS 加密）。若使用明文 HTTP：<br>• 中间人攻击者可篡改投递内容<br>• 中间人攻击者可截获 iLink token（若其在请求中） |
| **影响组件** | 观测层 Observability, iLink 投递通道 |
| **严重级别** | **MEDIUM** |
| **建议修复** | • 强制所有 iLink API 调用使用 HTTPS<br>• 文档注明 iLink 投递使用 TLS 加密传输<br>• 在投递 payload 中附加 HMAC 签名以确保端到端完整性 |

### M-3: MCP 工具返回错误信息过多

| 属性 | 内容 |
|------|------|
| **攻击路径** | MCP 工具的 `task_get`、`task_status` 等返回 `data/error` 字段，若错误信息包含：<br>• 文件系统路径（如 `/Users/xxx/.hermes/scripts/xxx.sh not found`）<br>• SQL 错误（暴露表结构）<br>• stack trace（暴露代码和内部实现）<br>则可能被攻击者用于信息收集和进一步的针对性攻击。 |
| **影响组件** | MCP 工具集, 观测层 |
| **严重级别** | **MEDIUM** |
| **建议修复** | • MCP 错误响应应区分用户可见错误和内部错误<br>• 用户可见：`"error": "script not found"`<br>• 内部日志：完整路径 + stack trace（写入 stderr 或 logging 系统，不返回给客户端）<br>• 错误对象中路径归一化（替换用户 home 为 `~`） |

### M-4: registry.yaml 并发修改冲突 R8 缓解不足

| 属性 | 内容 |
|------|------|
| **攻击路径** | 文档 R8 将多人同时修改 registry.yaml 的风险标记为"低"，缓解措施仅为"Git 冲突处理，定期 sync 覆盖"。但无锁的 YAML 编辑 + `sync --overwrite` 策略可能导致：<br>• 丢失中间写入（last-writer-wins 语义）<br>• MCP `task_create` 返回成功但实际写入被后续 sync 覆盖<br>• 健康状态与实际任务不同步 |
| **影响组件** | 注册层 Registry, Git 同步机制 |
| **严重级别** | **MEDIUM** |
| **建议修复** | • 短期：registry.yaml 编辑通过 MCP 工具作为单点入口，禁止直接编辑 YAML<br>• 长期：考虑使用 YAML 拆分（每个任务独立文件）+ 目录级原子写入，而非单一大文件<br>• 引入乐观锁：MCP 工具写入前读取 registry.yaml 的 `updated_at`，冲突时拒绝写入要求重试 |

---

## LOW / INFO 发现

### L-1: 任务雪崩保护硬限制可能妨碍合法使用

| 属性 | 内容 |
|------|------|
| **发现** | 文档 4.5.3 规定"单任务 1 分钟内最多触发 4 次（硬限制）"。在文件变更密集场景（如批量编辑 10 个文件，去抖 30s），任务可能 1 分钟内触发不足 4 次 — 此限制对高频 event 任务偏保守。但**非安全漏洞**。 |
| **建议** | 考虑将此限制设为可配置 (`max_trigger_rate: 4/min`)，或仅在雪崩检测到异常触发模式时激活（相比于始终硬限制）。 |

### L-2: 断裂检测频率与攻击面

| 属性 | 内容 |
|------|------|
| **发现** | 断裂检测定期扫描 `~/.hermes/scripts/` 中所有 script 路径的可达性。若检测频率过高（如每 tick 15s），可能被用于文件系统探测（验证某个路径是否存在），但对于本地系统攻击场景影响有限。 |
| **建议** | 将断裂检测频率与 tick 解耦（如每 5 分钟执行一次全量扫描）。 |

### L-3: n8n credential 管理参考未被采纳

| 属性 | 内容 |
|------|------|
| **发现** | 文档 5.4 提及 n8n 的 credential 管理是"可学习的"，但当前版本未纳入 credential 管理功能。鉴于 Task Center 至少涉及 iLink token、webhook secret 两类凭据，缺少统一 credential 管理是个隐患。 |
| **建议** | 升级优先级：将 credential 管理从"可参考"升级到当前版本的 out-of-scope → Wave 2 必做项。参考 HashiCorp Vault 或 systemd-creds 的加密 + 访问审计方案。 |

### L-4: 回退方案缺少安全验证

| 属性 | 内容 |
|------|------|
| **发现** | 6.2 回退方案中"回滚 registry.yaml 到上一版，恢复 cron.db 备份"未说明回滚时的安全验证：回滚的 registry.yaml 是否重新校验签名？cron.db 备份是否加密？备份文件权限是否足够？ |
| **建议** | 在回退 SOP 中添加：回滚后必须执行全量安全验证 + 断裂检测。cron.db 备份应使用 `ATTACH DATABASE` + WAL 模式完成在线备份。 |

### L-5: 安全验收清单不完整

| 属性 | 内容 |
|------|------|
| **发现** | 7.4 安全验收清单仅 5 项，缺失以下关键验证点：<br>• HMAC 安全比较使用 `compare_digest`<br>• shell 注入防护验证<br>• 目录遍历防护验证<br>• SQLite 并发写压测<br>• 日志脱敏生效验证<br>• 速率限制持久化和精确性 |
| **建议** | 扩展安全验收清单至 15+ 项，覆盖本报告中所有 CRITICAL 和 HIGH 发现。 |

---

## 安全加固建议清单（按优先级排序）

| 优先级 | 建议 | 关联发现 | 预估工作量 |
|--------|------|----------|-----------|
| **P0** | 禁用 `shell=False`，强制使用列表参数调用 subprocess | C-1 | ~0.5 天 |
| **P0** | 定义 `_secret/` 目录规范：加密存储 + 运行时解密 + 文件权限 600 | C-2 | ~2 天 |
| **P0** | HMAC 比较实现强制使用 `hmac.compare_digest` | C-3 | ~0.5 天 |
| **P0** | 每次执行前重新校验 script 路径合法性（规范化 + 前缀检查） | H-2 | ~0.5 天 |
| **P1** | SQLite 并发写入加固：WAL + busy_timeout + 单点写入代理 | H-1 | ~2 天 |
| **P1** | webhook 速率限制实现：per-path 计数 + 持久化 + 请求体预检 | H-3 | ~1 天 |
| **P1** | 子进程隔离：sandbox-exec / systemd ProtectSystem + NoNewPrivileges | H-5 | ~2 天 |
| **P1** | 文件事件监听：symlink 跳过 + watch 数量上限 + 递归深度限制 | H-4 | ~1 天 |
| **P2** | 运行记录日志脱敏：output/error 敏感模式匹配替换 | M-1 | ~1 天 |
| **P2** | MCP 错误信息脱敏：区分用户错误和内部错误 | M-3 | ~0.5 天 |
| **P2** | registry.yaml 编辑单点入口 + 乐观锁 | M-4 | ~1.5 天 |
| **P2** | iLink 投递 HTTPS 强制 + TLS 配置文档化 | M-2 | ~0.5 天 |
| **P3** | 扩展安全验收清单至 15+ 项 | L-5 | ~0.5 天 |
| **P3** | 回退 SOP 添加安全验证步骤 | L-4 | ~0.5 天 |
| **P3** | 凭据管理升级为 Wave 2 必做项 | L-3 | 规划工作 |

---

## 攻击图谱（影响关系示意）

```
攻击者入口点
  │
  ├── MCP 工具 (task_create/update)
  │     └── C-1: script 路径注入 → RCE
  │           ├── H-5: 修改 registry.yaml（持久化）
  │           ├── H-2: symlink 遍历执行任意文件
  │           └── C-2: 读取 config.yaml（iLink 泄露）
  │
  ├── webhook HTTP 端点
  │     ├── C-3: HMAC 时序攻击 → 伪造请求
  │     ├── H-3: SSRF / DoS / 大请求体
  │     └── C-2: secret 泄露（若明文存储）
  │
  ├── 事件监听 (event/fs)
  │     ├── H-4: symlink 遍历触发未授权执行
  │     └── H-4: inotify 耗尽 → 系统级 DoS
  │
  ├── 运行记录日志
  │     └── M-1: output_snippet 泄密
  │
  └── SQLite 多进程写入
        └── H-1: 竞争条件 → 数据损坏 / 任务丢失
```

---

## 结论

**系统安全成熟度评估：初级阶段（1/5）**

Task Center 需求文档展示了安全意识，但**安全设计尚未落地为具体实施规范**。文档在非功能性需求中声明了"子进程隔离 + 权限白名单"，但整个文档中没有一处给出这两个需求的具体实施方案。

**最关键的问题**：
- 子进程执行没有明确的 shell 注入防护方案
- 凭据管理完全未定义（`_secret/` 是一个空壳目录）
- HMAC 比较没有指定安全实现
- 多进程 SQLite 并发无写入串行化策略
- 脚本路径的运行时校验缺失

**积极方面**：
- 文档明确列出了 R4/R6 等安全相关风险
- webhook 安全性要求（HMAC、IP 白名单、大小限制、速率限制）已写入
- 安全验收清单存在（尽管不完整），表明安全验证被纳入交付标准

**建议**：在进入阶段 2 (MVP) 实施前，必须完成 P0 和 P1 级别的安全加固。建议增加一个**安全加固子阶段**（Safety Sprint），预计 4-6 天工作量，集中在子进程隔离、凭据管理、SQLite 并发、webhook 加固四个关键领域。MVP 的安全验收应通过**渗透测试**而非仅凭清单 check，至少覆盖 C-1、C-2、C-3、H-1、H-5 的攻击路径。

---

*本报告为对抗性安全分析，旨在暴露设计阶段的安全缺陷供前置修复。所有发现均基于需求文档草案 v0.1，实际实现代码应当在实施后进行代码审计。*
