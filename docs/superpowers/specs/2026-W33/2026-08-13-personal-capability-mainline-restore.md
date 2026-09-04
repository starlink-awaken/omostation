---
lifecycle: contract
owner: governance-team
version: 1.0.0
last_updated: 2026-08-13
type: ssot
last_updated: 2026-09-03
---

# 个人价值能力主线恢复与子模块防回退规范

## 背景

`BET-Y1Q2-T2-01`、`BET-Y1Q2-T2-02` 与 `BET-Y1Q2-T4-02` 已交付并通过定向测试，
但交付提交只保存在 OMO/Cockpit 的 agent 分支与 tag。根仓曾直接指向这些 feature
提交，后续 submodule main 自动升级又把 gitlink 移回未包含上述能力的子仓 `main`。

因此台账仍声明 `done`，当前根仓主线却不能稳定重放 personal signal、personal dogfood
CLI 和 personal outcome observation。这是交付持久化缺口，不是新增产品功能需求。

## 目标

将三个已完成 BET 的累计能力无损移植到 OMO 与 Cockpit 当前 `origin/main`，在子仓 PR
合并后再更新根仓 gitlink，并让根仓的子模块指针事务默认拒绝指向未进入子仓
`origin/main` 的提交。

## 冻结输入

| 子仓 | 当前恢复基线 | 已交付能力来源 |
|---|---|---|
| OMO | `87d99ddcc3a4ae1c2db3790ddd4a69629c91aec4` | `57d219c50a0ee64e0d73105bca9542acbdb37a41` → `a1f8478b2d50a8dd04de2e890d4e48d465a1dbfe` → `9b05450fe8760a6388356e229fa3c2a6313634c8` |
| Cockpit | `906d009e59c471f044e2571e2050ac42b5bf9b37` | `9105de37e6ddae5365ead57b4c5c9eaced3d79bd` → `1807318b2a7495d34a69b83db39f3472843e63ee` → `ee8644fe12ff63da3762105cb17ee6192cf044f3` |
| 根仓 | `4fb7d4f86a56713df3f7e2ae0b059b029b4c34a2` | 子仓合并后的 `origin/main` 提交 |

这些 SHA 是恢复来源与审计锚点，不要求通过覆盖当前主线来保持字节级相同。实现必须以
当前子仓 `origin/main` 为基线解决冲突，禁止回退 T1-14/T1-15、Documents、Facts、KEMS
或其他已经进入主线的能力。

## 集成顺序

1. OMO writer 在独立 clone 中从 OMO 当前 `origin/main` 建分支，恢复三个累计提交并测试。
2. OMO PR 审查通过后先合并；Cockpit 最终验证必须使用已包含恢复能力的 OMO main。
3. Cockpit writer 在另一独立 clone 中从 Cockpit 当前 `origin/main` 建分支，恢复三个累计提交并测试。
4. Cockpit PR 合并后，根集成 clone 才可更新 OMO/Cockpit gitlink。
5. 根仓增加通用 main-ancestry 门：待提交 gitlink 必须可由对应子仓 `origin/main` 到达。
6. 根 PR 合并后，从全新干净 main checkout 运行公开 CLI/API 的 never-send 烟测。

不得直接把根仓继续指向 `origin/agent/*`，也不得用根 gitlink 临时指针代替子仓 PR。

## 行为合同

### OMO

- `PersonalEpisodeService` 支持受控本地信号摄入、完整执行上下文重放、系统/用户产出来源记录、
  人工 Outcome 与价值观测。
- 同一 signal 的因果 Episode 与幂等身份保持稳定；角色变化重放不得生成重复 Episode。
- 查询和观察保持只读，不泄露正文、绝对路径、source URI、digest 或凭证。
- 不削弱现有 worker admission、spec revalidation、Workflow Mesh 或 Ledger 验证。

### Cockpit

- 提供 personal signal ingest 与 `cockpit workflow mesh personal` 的 setup/ingest/confirm/draft/
  feedback/status 路径。
- draft 必须经过 OMO/Agora PEP，产物固定 `never_send=true`；任何失败不得外发或创建真实外部任务。
- feedback 支持 verdict、review duration 和 estimated time saved；非法负数、NaN、Infinity 在写入前拒绝。
- HTTP/CLI/status 不返回正文、绝对路径、source URI、digest、credential 或本地 evidence URI。
- 不回退当前 Documents、Facts、KEMS、Runtime 或 MCP 能力。

### 根仓持久化

- 根仓 gitlink 更新只能指向子仓 `origin/main` 可达的完整 40 位 commit。
- `submodule-reachability-gate.py` 保留远端可达性校验，并新增/启用精确 main-ancestry 校验。
- 查询远端、fetch、对象校验或 main-ancestry 任一失败均 fail closed；不得部分 stage 指针。
- 该门只约束新的/待验证指针，不通过删除 tag 或历史分支伪造完成。

## 验收标准

1. OMO 恢复分支基于冻结 `origin/main`，三个历史能力的目标回归和当前 orchestration/worker
   回归同时通过；无历史主线文件被删除或回退。
2. OMO PR 合并后，新 OMO commit 可由 `origin/main` 到达。
3. Cockpit 恢复分支基于冻结 `origin/main`，personal API/CLI、现有 episode projection 与当前
   Documents/Facts/KEMS 定向回归同时通过。
4. Cockpit PR 合并后，新 Cockpit commit 可由 `origin/main` 到达；根仓再更新两个 gitlink。
5. main-ancestry 负测证明：仅存在于 `origin/agent/*` 的提交即使远端可达，也不能通过根指针门；
   `origin/main` 祖先可通过；查询失败时 index/HEAD 不变。
6. 干净根仓 main 可发现 personal CLI/API，并完成一条真实本地 `never_send` 链；不得发送邮件、
   写外部日历、创建真实任务或调用未批准 provider。
7. Ledger 查询不改变 count/hash；真实 Human Outcome 若尚需用户审阅，必须诚实保持 0，不能用
   合成样本或工程 PR 顶替。

## 非目标

- 新增第二信号源、邮件/日历/提醒事项 adapter、自动 watcher、daemon 或 cron。
- 新增 UI、第二任务数据库、第二 Workflow Mesh、Ledger DDL 或新顶级项目。
- 自动外发、自动批准、A3 自主执行、家庭/组织/多租户、exactly-once 或崩溃恢复。
- 在本 BET 接入新 Agent、Ruflo、Multica、Kandev live adapter 或实现 Blueprint R1。
- 重写已经通过审查的 personal feature；仅允许解决当前主线冲突和必要兼容修复。

## 回滚与断路器

子仓 PR 未合并前可删除恢复分支；根 gitlink 未更新前当前 main 不受影响。若恢复需要修改
Ledger DDL、Workflow Mesh 状态机、真实外部副作用、删除当前主线能力，或两天内不能把历史
提交与当前 main 合并，应停止并拆分兼容修复，不得以直接 pin agent 分支绕过。

若根仓 main-ancestry 门会阻断既有合法发布流，先以显式命令/事务模式上线并记录存量，禁止
未经证据直接把所有历史 gitlink 一刀切为硬失败。
