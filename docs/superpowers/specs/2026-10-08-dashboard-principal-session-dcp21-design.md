---
schema: md/v1
status: design-for-review
lifecycle: proposal
owner: dashboard-convergence
updated-at: 2026-10-08
revision: 0.4
---

# 统一 Dashboard 身份、会话与数据授权设计（DCP-21）

## 目的与决策边界

统一 Dashboard 要让管理员（人类）、Agent、业务人员在同一产品壳中看到各自有权访问的内容，并由服务端对每次读取、操作和数据对象执行授权。界面角色切换、隐藏菜单和本机回环绑定都不构成身份或授权证明。

白皮书 v2.1 规定夏明星是唯一最高 Principal。管理员是 Principal 在 Dashboard 中承担的管理职能；Agent 与业务人员是经委托或角色分配获得有限能力的主体，不是新的最高 Principal。DCP-21 的终态覆盖三类主体，但首个实施阶段只能开放已具备可信身份链的主体。不能为缺少身份或 scope 证明的主体创建演示凭证，也不能把未标注的现有数据默认开放给管理员。

本文件定义授权边界和阶段门，不授予实现、生产部署或身份签发权。候选完成后由 Principal 审阅；其后仍须满足 Workspace 的 G0、M0、run 和 code identity 门。

## 当前事实与缺口

- Cockpit 的 `verify_api_key()` 在 `COCKPIT_AUTH_REQUIRED=false` 时允许匿名请求；当前 `:8090` 的决策图 summary 与 node API 曾以无凭证返回 HTTP 200。严格认证函数 `authenticate_api_principal()` 返回的是凭证摘要身份 `operator://cockpit-api/<digest>`，本身不证明该凭证属于哪种主体或它代表哪个 Principal。
- OMO `PrincipalAuthority` 是现有组件中最接近 Principal 身份根的实现：验证 `principal_id`、credential digest、membership version 并产生带期限的 receipt。但当前 `DefaultPrincipalAuthority` 的默认成员表是本地固定映射，并包含 fixture 主体；它不是供 Dashboard 使用的完整动态主体目录，也没有公开的 subject-to-principal 登录解析流程。
- OMO `SovereigntyService` 能保存有版本、状态和撤销生命周期的 `RoleAssignment`。它不认证发起请求者；`assign()` / `revoke()` 接受的 Principal、subject、role 和 scope 参数本身不能证明写入已获授权。assignment 的 `role_scope` 也不能单独证明某个 Dashboard 对象属于该范围。
- OMO `Mandate` 与 `WorkPacket` 提供任务或执行级委托、能力、期限和路径约束；它们不能替代浏览器登录身份或任意 Dashboard 资源的访问控制。
- Zhixing live server 的 `_allowed()` 只检查 loopback Host、可选 Origin 和 `Sec-Fetch-Site`，不验证用户/Agent/Principal 身份。`do_GET()` 的动态 `/api/v1/<operation>` 会把 operation 交给 `ObservationIndex.query()`；其 operation allowlist 含 `proposals/submit`、`proposals/adjudicate`、`health/auto-heal`、`health/execute-heal`、`bos/invoke` 和 `loops/step`，实现分别会写提案、执行修复、调用 BOS 或推进 loop。当前投影模式只在 `do_POST()` 拒绝写入，不能阻止这些副作用型 GET。它们目前可无凭证从 loopback 调用；此发现只依据静态处理路径，不执行这些操作。`loopback` 和响应中的 `read_only` 字段均不是身份、授权或无副作用证明。
- IdentityEnvelope 与 Kairon RoleBinding 是数据 schema；现有检查没有证明它们已经接入 Cockpit 会话、OMO 主体认证或对象级授权。Agora 有 AgentRegistry、IdentityCA 和 OAuth 等身份组件，但尚未证明它们与 OMO Principal、有效委托、业务角色、Dashboard 会话和资源 scope 形成完整签发链。
- `DecisionNode` 只有 `node_id/kind/actor/action/ts/context`；写入 API 接受调用方提供的 actor/context。DecisionGraph 没有可信 Principal/project 绑定，也没有已验证的 scope 生产者。现有 summary/nodes 读处理器会把图数据原样返回。
- Cockpit DCP-20 候选覆盖其静态路由与注册源，但当前摘要没有覆盖 Zhixing `:43191` 的人类页面和 API。因此 `:43191` 直连、静态页面内嵌快照和数据接口仍须加入统一授权面盘点；loopback 只能限制网络可达性，不能证明主体身份。
- 设计审阅已确认以上缺口。上一稿中“管理员可读全图”“无 scope 历史记录对管理员可见”和直接用 credential 配置赋予三种 persona 的做法均撤回。

## 权威与主体模型

身份链必须以 OMO Principal authority 为唯一 Principal 验证根，以 OMO sovereignty ledger 保存版本化角色分配状态；Dashboard 只消费经验证的授权结果，不维护第二份 Principal/Role SSOT。ledger 事件只有在写入者授权可验证后才可成为授权事实。登录适配器不可把客户端提交的 `principal_id`、`agent_id`、persona、project 或 scope 当作认证结果。

| Dashboard 主体 | 白皮书中的身份关系 | Dashboard 需要的可信链 | 当前状态 |
|---|---|---|---|
| 管理员（人类） | 唯一 Principal `principal:xiamingxing` 的管理能力 | 真实人类认证 → OMO Principal receipt → Principal 的显式管理能力 | Principal authority 组件存在，Dashboard 登录适配未接入 |
| Agent | 代表 Principal 执行的委托主体 | 可验证 Agent workload identity → 委托 Principal → 有效 Mandate/RoleAssignment → 明确资源 scope | Agent 注册组件存在；Principal 委托及资源 scope 链未证明 |
| 业务人员 | 被 Principal/Space 授权的非 Principal 人类主体 | 受信人员身份源 → Space membership/RoleAssignment → Principal 授予的有效 Mandate → 明确资源 scope | 尚无 Dashboard 端到端 provisioning 或受信业务人员 IdP |

在唯一 Principal 以外的页面产品角色、Space member 或 Agent service identity，不得命名为最高 Principal。管理员的系统管理能力不能自动跨越个人数据、记忆、Space 隔离与 Principal 授权边界。

**实现前置 A：** OMO authority 要提供经审计的主体解析/验证接口，将秘密 credential 在服务端解析为稳定主体和 Principal authority receipt，并支持 membership/credential 版本撤销。禁止在 Cockpit 中复制成员映射或硬编码凭证摘要。生产路径必须关闭 fixture identities。

**实现前置 B：** RoleAssignment 和 Mandate 的 grant、replace、revoke 必须由 OMO authority 边界验证写入授权。每个变更请求绑定当前 Principal-authorized receipt、经认证的写入者、目标 subject、精确 action、role/capability、resource scope、policy revision 与预期前序版本；authority 验证该 Principal 是否可授权此变更，成功后以 CAS 方式追加带来源和时间的审计事件。缺少、过期、被撤销或字段不匹配的授权证明必须拒绝；不能仅凭 `SovereigntyService` 的调用权限、自由文本 scope 或调用方传入的 Principal 字段接受变更。拒绝、替换和撤销也必须留有可追溯审计。此写入契约和负测完成前，ledger 只表示待验证的版本化记录，不足以授予 Dashboard 能力。

**实现前置 C：** Agent 与业务人员分别提供真实 provisioning：Agent 的身份绑定 Principal 与有效 Mandate；业务人员的身份绑定 Space membership 和 Principal 授权。任一路径未准备好时，该类主体保持不可登录、默认拒绝，不用固定假用户替代。

**紧急方法安全前置：** 在开放任何 Dashboard 功能给 persona 或进入 DCP-21A 读取路径前，DCP-20 必须证明所有 GET operation 都是无副作用读取。`proposals/submit`、`proposals/adjudicate`、`health/auto-heal`、`health/execute-heal`、`bos/invoke`、`loops/step` 等执行型 operation 必须从 GET 路由剥离；要保留时只能改为受认证、CSRF 保护、显式授权且有审计的写请求。未完成前，这些 operation 通过 GET 一律拒绝；不得以 `projection_store`、loopback、CORS、Origin 检查或 `read_only` 标记代替该门。

## 会话设计

统一 Dashboard 通过同源 BFF 建立短期服务器会话。长期 API credential 只在 TLS/loopback 登录请求中提交到服务端，不进入 URL、localStorage、JavaScript 状态或日志。服务端先调用 OMO authority 完成主体和 Principal 验证，再对 Agent/业务人员读取当前委托与 RoleAssignment 版本；任何缺失或过期都拒绝签发会话。

浏览器只持有随机、不含身份信息的 `__Host-cockpit_session` cookie：`HttpOnly; Secure; SameSite=Strict; Path=/`，不设置 Domain。正式产品由一个受管同源入口提供 UI 和 API；5173 Vite 仅为开发入口，经同源代理访问 BFF。禁止跨源携带 session cookie 或放宽 CORS 来绕开同源边界。

会话采用 15 分钟 idle TTL、8 小时 absolute TTL；认证成功与权限提升时轮换 session ID。会话服务端记录 authority receipt digest、Principal、主体、RoleAssignment/Mandate 版本和创建/到期时间，不存明文 credential。每个受保护请求都校验 session、receipt 到期和当前 authority version；版本变化、委托撤销、登出立即使关联会话失效。authority、版本查询或 session store 不可用时失败关闭。当前单进程阶段可使用进程内 store，进程重启使全部 session 失效；切到多 worker/多实例前必须换成共享、原子撤销、有 TTL 的 store。

所有登录、登出及写请求只接受登记的精确 `Origin`；拒绝缺失或不匹配的 Origin，并使用 CSRF token 保护状态变更。禁止用 `Sec-Fetch-Site`、`SameSite` 或隐藏按钮单独作为 CSRF 防护。登录错误统一返回，不泄露账号存在性；登录端点按主体和来源限速。服务只可在 loopback 提供 HTTP 开发模式；非 loopback 必须 HTTPS、安全 cookie 与明确 origin 清单。

现有 `@lru_cache` API key cache 不作为撤销保证。新登录/请求必须读取可撤销的 authority version；不允许通过清缓存或重启作为唯一的凭证轮换机制。

## PEP 与授权决策

统一 PEP 每次请求使用服务端身份与可信授权对象计算：

```text
decision = authorize(
  subject_identity,
  principal_authority,
  active_role_assignments,
  active_mandate,
  action,
  resource_binding,
  policy_revision,
)
```

所有默认拒绝。授权输入只接受 OMO authority receipt、当前 RoleAssignment/Mandate 和由受信 producer 签发的资源绑定。HTTP path/query/body 中的 `actor`、`principal_id`、`project_id`、persona 或 scope 都不能扩大权限。DCP-20 route inventory 必须记录 HTTP method、纯读取/计算/写入副作用、身份要求和资源范围；GET 必须经源码与行为测试证明无状态变化。每个 API route、SPA deep link、command palette action、按钮操作、`:43191` 端点与资源访问都必须在 DCP-20/更新后的 surface inventory 中明确登记。未登记路由必须拒绝或只返回不含业务数据的固定公开帮助页。

鉴于目前 Zhixing `:43191` 仍能直返含完整 snapshot 的 HTML 和数据 JSON，统一产品入口必须代理授权过的数据，或在 Zhixing 读服务本身增加同一身份/策略校验。仅仅隐藏主导航或把链接换成 Cockpit 不能阻止直连接口绕过。

## 数据 scope 与 Decision Graph 决策

第一阶段不启用 Decision Graph 数据读取。现有节点和边都没有受信 owner/project/privacy binding；因此不能按 `actor` 推断资源所有者，不能按“管理员”身份豁免 scope，也不能把无 scope 的历史对象开放给任何 dashboard persona。

未来的图 producer 必须在写入时从已验证的 Principal/Space/Role/Mandate/WorkPacket 上下文产生不可由调用方覆盖的 binding，并绑定 producer identity、resource ID、privacy class 和 schema version。导入路径必须校验该证明。读策略先过滤节点，再只返回两端均可见的边，并基于可见子图计算所有计数。无证明历史图对所有角色不可见，直到逐条重签或通过经批准、可追溯的来源迁移重新建立绑定。

首个业务数据纵向切片不得预先指定 Decision Graph。DCP-20 surface inventory 与数据 provenance audit 完成后，选择一个已有可信 producer、可证明 owner 和撤销传播的只读资源；若没有满足条件的资源，DCP-21 先交付安全会话和拒绝路径，数据读取保持关闭。

## 用户体验与错误语义

统一 Shell 的导航、全局搜索、深链、命令面板和操作入口读取 `/api/session` 的显示上下文，但它们只用于体验。每条 API 仍独立校验 session 和 PEP。

- 无效、过期、撤销 session：HTTP 401，不返回任何个人或业务数据；UI 提供同源登录。
- 身份有效但明确禁止的非对象操作返回 HTTP 403；若响应可能暴露资源存在性，对象级拒绝统一返回 `404 resource_unavailable`。集合查询只列出可见资源；审计保留精确拒绝原因。
- 未知路由、未知 capability、未绑定资源、authority/PEP/audit 依赖失败：默认拒绝，不降级匿名。未登记路由统一返回不含业务数据的 404。
- 不可见对象与不存在对象的 status、response schema、headers（排除逐请求追踪 ID）和字节长度必须完全一致。时序检查是残余风险审查，不声称消除本机侧信道：在同一构建/主机、无并发、固定请求与响应、相同缓存条件下，随机交错对“已存在但不可见”和“不存在”各采样 200 次；冷缓存与热缓存分开重复，记录 p50/p95、分布与主机噪声。若审查者能从样本稳定区分两类响应，则 DCP-21D 不得 PASS，须修复或由独立安全 reviewer 记录剩余风险、缓解措施及明确接受依据；不能把未设阈值的统计结果写成通过。
- 不记录 credential、Authorization、Cookie、session token 或可重放 receipt。审计记录稳定 subject/Principal、action、resource ref、scope ref、policy revision、decision、reason code 与时间。

UI 状态覆盖加载、未登录、无权、authority 不可用、scope 不完整、空列表、正常列表和部分数据。对未授权对象，页面不能显示对象名、总数或能推断其存在的提示。

## 阶段与验收门

| 阶段 | 范围 | 必须交付的证据 | 放行条件 |
|---|---|---|---|
| DCP-21A 主权根适配 | DCP-20 先完成 GET 无副作用安全修复；OMO authority 提供 subject resolution、可撤销版本；Cockpit 同源登录/session；先只接真实 Principal | method × operation inventory；执行型 GET 被拒绝/迁为授权写方法的证明；authority 契约、credential 到唯一 Principal 的负/正用例、版本撤销回归、session 安全测试、浏览器登录与直接 API 验收 | GET operation 无未授权副作用；OMO authority 和 G0 运行/绑定门均通过；未经授权数据路由仍拒绝 |
| DCP-21B 三类主体 | 接入真实 Agent workload identity/Mandate 与业务人员身份源/Space RoleAssignment | 三主体真实 provisioning receipt；分别有 Principal、RoleAssignment/Mandate 版本及撤销证据；不存在假主体 fixture | 每类允许与拒绝流程都由服务器真实身份验证；任一类未达到则该类不开通 |
| DCP-21C 资源 scope | 扩展 DCP-20 至 Cockpit 与 Zhixing 所有 API/页面/操作；选择可信业务 producer；安全过滤与审计 | route × action × resource inventory；受信 producer schema 和来源证明；跨主体/项目负测；`:43191` 直连绕过测试 | 未授权 path/API/deep-link 均拒绝；边、计数、错误响应符合对象过滤契约 |
| DCP-21D 统一 Shell 发布 | Cockpit 统一导航与交互；Zhixing 内容以受保护投影整合；独立站点退为受保护兼容层 | 全流程浏览器 QA、p50/p95、重启恢复、权限变更端到端传播和 code identity 发布证据 | 页面产品、BFF、Zhixing 直连与后台数据请求都执行同一 policy revision |

完整 DCP-21 的验收要求：

1. OMO authority 是唯一 Principal 身份根；每个 session 的主体、Principal、OMO authority receipt 与凭证/RoleAssignment/Mandate 版本都有可复验来源，未知和 fixture 身份在生产拒绝。
2. 三类主体均完成真实 provisioning；管理员能力不等同于另一个 Principal，Agent/业务人员能力必须有当前委托或角色分配。
3. 登录、session rotation、idle/absolute expiry、logout、Principal/credential/RoleAssignment/Mandate revoke、服务重启和 authority 故障路径均有负测。
4. DCP-20 扩展后，Cockpit 和 Zhixing 的静态/动态页面、API、写操作、搜索和 deep links 全部有 capability/action/resource 归属；未知 surface 默认拒绝。
5. 所有 GET operation 都通过方法安全检查；执行型 operation 无法通过 GET 触发，迁至写方法的 operation 经过认证、CSRF、capability、scope 与审计检查。
6. 至少一条真实资源 producer 为所有对象写入可验证 scope；API、页面、聚合、边和计数不能越权或泄露对象存在性。
7. 管理员、Agent、业务人员分别完成一个允许用例和一个拒绝用例；前端 persona 篡改、伪造 actor/Principal/project 和直接 API 调用均不能改变授权结果。
8. 审计记录覆盖 allow/deny 并无秘密；authority、PEP、session store 或审计故障均 fail-closed。
9. 浏览器验证正常、401、403、对象级 404、部分 scope、空状态和故障状态；对象存在与否的响应状态、schema、headers 与字节长度一致；时序残余风险按固定采样协议记录，出现稳定区分时修复后重测，或由独立安全 reviewer 对具体剩余风险给出书面接受依据。
10. 独立 reviewer 通过，G0/M0 和 exact code identity 发布门通过后，才可以在受控候选中启用。

## 当前未完成事项

- `COCKPIT_AUTH_REQUIRED` 默认为 false；个别严格验证路径不能替代 Dashboard 总体授权。
- 还没有 Cockpit 与 OMO PrincipalAuthority 的主体解析/session adapter；当前 OMO 默认 authority 成员表也不是三类主体的生产目录。
- 没有 Agent→Principal→Mandate→资源 scope 的可信 Dashboard 链，也没有业务人员身份源→Space RoleAssignment→资源 scope 的端到端链。
- 决策图当前数据无 scope，暂不选作首个业务数据切片。
- DCP-20 还需增加 Zhixing `:43191` 首页快照、live API、data JSON 与所有可触发操作，并对 Cockpit API 与 Zhixing 数据面做运行态对账；当前发现 generic GET operation 可触发写提案、auto-heal、BOS invoke 和 loop step，属于启用 DCP-21A 之前必须关闭的安全阻断项。
- G0-BIND v1.3 仍为 `HOLD_STALE_BASELINE_AND_M0_FAIL`；共享 Workspace 有 57 项既存脏改动。不得以重置/清理共享目录解决，也不得在新证据、owner 生命周期和精确授权之前进行 production apply。

## 方案比较

| 方案 | 评估 | 决定 |
|---|---|---|
| 在 Cockpit 复制一个 Principal/Role 配置文件 | 会形成第二权威，无法证明撤销和 RoleAssignment version 与 OMO 一致 | 不采纳 |
| 仅复用 API key name/scopes 或管理员 key | 只能证明持有某 credential，不能确定自然人、Agent、Principal 或资源 owner | 不采纳 |
| 同源短期 session + OMO authority + sovereignty ledger + 共享 PEP | 复用已有权威边界，但需补 subject resolution、scope producer 和三类 provisioning | 推荐目标架构，分阶段启用 |
| 直接接入外部 OIDC | 当前没有已绑定并验证的 IdP；OIDC 只解决登录，仍需映射到 OMO Principal、Space RoleAssignment 和 Mandate | 作为未来 identity adapter，不绕过 OMO |

## 审阅请求

请 Principal 审阅本版身份模型、RoleAssignment/Mandate 写入授权契约、Zhixing 直连接口、GET 副作用紧急封闭门、四个阶段门，以及“Decision Graph 在可信 producer 到位前保持关闭”的边界。只有本版 spec 获得明确接受后，才进入实现；接受本版不代表满足 G0/生产部署门。
