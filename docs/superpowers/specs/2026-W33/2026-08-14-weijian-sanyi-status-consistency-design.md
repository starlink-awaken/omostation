---
status: accepted
lifecycle: contract
owner: governance-team
version: 1.0.0
last_updated: 2026-08-14
type: ssot
last_updated: 2026-09-03
---

# 卫健委 CR08 三医态势一致性审计设计

## 目标与边界

为 `work-weijian` 域交付一个可由 Workspace Runtime 执行、由 Cockpit 发现的**只读**
CR08 审计：比较已核验的三医进展事实与三医态势仪表盘的声明性复核日期，告诉使用者
仪表盘是否需要人工更新。

它解决的是“事实已变化而仪表盘仍停在旧复核日期”的可观察性缺口；它不替用户撰写、
修改或发布任何 Documents 内容。

权威来源保持分层：

- `@工作文档/卫健委/_control/control-rules.md` 的 CR08 定义是场景语义 SSOT。
- `@工作文档/卫健委/_control/三医态势仪表盘.md` frontmatter 的 `last-reviewed` 是
  仪表盘的声明性时间锚点。
- `@工作文档/卫健委/_entities/facts/01-progress.yaml` 内匹配本场景实体的、已验证
  `verified_at` 是事实时间锚点。
- 根仓 `documents-domain-projects.yaml` 是 Runtime job、输入范围、owner、读写边界与
  Cockpit tool profile 的绑定 SSOT。
- Runtime 是隔离执行、超时、状态侧 receipt 的唯一 owner；Cockpit 是只读投影与客户端
  发现入口；Documents 仅是输入。

## 审计合同

绑定新增一个手工 job `documents-weijian-sanyi-status-audit`，其 `domain_id` 为
`work-weijian`，`owner` 为 `runtime-control`，`action` 为
`audit_sanyi_status_consistency`。它只读取：

1. `_control/三医态势仪表盘.md`；
2. `_entities/facts/01-progress.yaml`；
3. 为解析这两个受控输入所必需的域解析/绑定元数据。

绑定显式声明 CR08 的事实范围：`proj-syld`、`proj-jingbao`、`proj-emr-quality`。这避免
运行时用关键字、目录遍历或 Markdown 全文猜测“三医”语义；范围变更必须先变更绑定
SSOT 和相应测试。

Runtime 只接受普通文件，不跟随输入符号链接；文件、YAML、frontmatter、日期或绑定契约
不可读/非法/歧义时均不把结果伪装为陈旧或最新。

### 状态判定

| 条件 | job 状态 | 进程结果 | 含义 |
| --- | --- | --- | --- |
| 每个范围内事实均有严格 ISO 日期 `verified_at`，且其最大值不晚于仪表盘 `last-reviewed` | `ok` | 0 | 已知事实没有要求新的人工复核 |
| 同样的有效输入中，最大 `verified_at` 晚于 `last-reviewed` | `attention` | 1 | 仪表盘需要人工复核/更新 |
| 输入缺失、符号链接、解析失败、范围事实缺 `verified_at`、或日期不合法 | `unavailable` | 2 | 无法安全得出比较结论 |
| Runtime 隔离、超时、receipt 或状态 I/O 失败 | `error` | 非零 | Runtime 不声称审计已经完成 |

`attention` 是有证据的业务发现，不是运行时故障；`unavailable` 与 `error` 不得降格成
`ok`。没有匹配范围的事实同样是 `unavailable`，防止空集合产生假绿。

### 最小证据

receipt schema 固定为 `runtime.documents-sanyi-status-consistency.evidence.v1`，仅含：

- 状态、执行时间与稳定错误码；
- `dashboard_last_reviewed`、`latest_verified_at`；
- `relevant_fact_count`；
- 与隔离/状态写入有关的 Runtime 元数据。

receipt、Cockpit CLI、MCP 与 `domain_context` 不得返回事实正文、`fid`、绝对路径、
相对 Documents 文件名、实体以外的原始 YAML 字段，或任何客户端配置/凭据。Runtime 的
唯一写入位置是其受控 state root 下的 evidence；绑定 `writes` 为空，Documents 树在执行
前后必须字节级不变。

## Cockpit 与客户端发现

Cockpit 新增 pathless 投影 `domain_sanyi_status_consistency_status`，并提供：

- CLI：`cockpit sanyi-status work-weijian --json`；
- agent Runtime MCP 的同名只读 tool；
- `domain_context(work-weijian)` 中的 discoverable 工具条目。

其 envelope schema 为 `cockpit.domain-sanyi-status-consistency.v1`。投影只读取 Runtime
receipt；没有 receipt、绑定不合法或 Runtime 报错时返回 `unavailable`/`error`，并保持
无路径输出。

根 binding 同步把该 tool 纳入所有已声明的 Workspace MCP / Secure MCP Tunnel read profile。
这只是可发现性声明：不配置或不重载的 Claude Desktop、ChatGPT、Zed/ZCode 等客户端不被
宣称已安装、已连接或已经刷新。

## 不在本 MVP 内的事项

- 不自动改写 `三医态势仪表盘.md`、`facts/*.yaml`、`_index.yaml` 或任何 Documents 内容。
- 不扫描卫健委域的全部 Markdown、附件或历史资料；不使用文件 mtime 作为业务真相。
- 不创建域内 KEMS/Runtime，也不引入 watcher、cron、通知、草稿生成、LLM 判断或客户端 UI。
- 不改变现有 `controller.py` 的运行路径。它把断链/不可读情况标为 CR08 的历史规则与
  `control-rules.md` 的场景语义不一致；本次以新、独立且有边界的 owner job 消除误用，
  旧 controller 的重分类留给一个单独、经授权的兼容性治理变更。

## 实施顺序与验收

1. Runtime：按根 binding 严格解析 job，完成普通文件输入、日期比较、状态侧 evidence 与
   dry-run/重复执行契约；以 RED/GREEN 覆盖 `ok`、`attention`、空集合、非法日期、缺失、
   符号链接、超时与 Documents 零写。
2. Cockpit：增加 adapter、CLI、MCP 和 `domain_context` 投影；覆盖 receipt 映射、缺失
   receipt、`attention` 非零、无路径泄露以及 tool discoverability。
3. 根 binding：注册 job/tool/profile，更新 Runtime/Cockpit gitlink；验证 binding checker、
   Secure MCP Tunnel profile 和相关根测试。
4. 安装态 closeout：从干净主线执行真实 `runtime documents run ... --json`、Cockpit CLI、
   MCP initialize/tools-list/tool-call 与 Documents 前后 digest；预期当前如果事实晚于仪表盘，
   结果诚实为 `attention`，而不是为了绿灯改输入。

每层先在自己的独立分支完成聚焦测试、代码审查、CI 与合并；根仓只指向已进入子仓
`origin/main` 的提交。最后以安装态 evidence 和简短复盘确认是否值得扩展到其他
场景规则。

## 回滚与后续决策点

在 Runtime/Cockpit/根 binding PR 未合并前，删除各自分支即可回滚；合并后若需要暂停，
从 binding profile 移除 job/tool 可停止发现与执行，不删除历史 state evidence。任何把
`attention` 直接转为 Documents 写入、增加自动调度，或扩展事实实体范围的提议，都必须先
更新本契约与 binding SSOT，并重新取得用户授权。
