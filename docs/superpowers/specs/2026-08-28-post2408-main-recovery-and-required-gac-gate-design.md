---
schema_version: specification/v1
spec_version: 1.0.4
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-09-02
bet_id: BET-Y1Q3-T6-15
risk_level: L3
human_gate: true
value_indicator_policy: false
type: ssot
last_updated: 2026-09-03
---

# Post-2408 Main Recovery 与 Required GaC Gate 设计

## 1. 决策与目标

采用已经书面批准的 **R1 → H1 → R2** 顺序：

```text
R1 baseline recovery
  -> H1 promote the existing gac-gate
  -> R2 repository hygiene and recurrence prevention
  -> Product P0 Wave A preflight
```

本设计处理的是共享主线被大体量合并重新污染后暴露出的治理失真：代码可以在 required contexts 通过时合并，
但完整 GaC、script registry、Python 语法、runtime artifact policy 或 ADR 状态仍可能失败。目标不是新增一套治理系统，
而是修复当前基线，并把已经存在的 `gac-gate` 从 advisory 演练提升为真正的 required merge admission。

本设计不证明个人价值。所有工程、CI、PR、canary 和运行证据都保持
`value_indicator_policy=false` / `value=NOT_PROVEN`。

## 2. 背景与问题：当前事实与证据边界

### 2.1 不可变观测快照

| Snapshot | 直接证据 | 结论 |
|---|---|---|
| `0356c8729` | 当时 root full GaC 通过，script registry active 与 baseline 对齐 | 最近已知绿基线；不是永久计数合同 |
| `30aa6a3c7` / PR `#2408` | 大范围多 surface 合并中，多个非 required workflow 失败，但 required contexts 通过 | 当前 required contexts 不覆盖完整治理基线 |
| `702d7f5b9` | `bin/ops/cli.py` 存在冲突标记且无法编译；script active 高于 baseline | 已观察到的回归样本；执行时必须重新验证 |
| `148737c5b` | 本 Spec clone 的 initial pinned base | 初稿基线；不是实现阶段的默认起点 |
| `5fc384c48` | 初稿完成前刷新到的 `origin/main`；新增成本/SLO/metrics 文件，required contexts 仍仅两项 | 并发推进仍在发生；提交前必须 rebase，执行时仍须重算 |
| `7d43ab97b` | bootstrap 提交前 fast-forward 后的 base | 本 draft 的提交基线；实现阶段仍必须从当时最新 main 新建 clone |

任何计数和文件集合都只能从相应 immutable SHA 的机器可读证据解析。R1/R2 执行者必须从执行时最新
`origin/main` 重新计算；本表 SHA 只定位证据，不是长期 SSOT。

### 2.2 已有机制，必须复用

1. `.github/workflows/gac-gate.yml` 已有名为 `gac-gate` 的 job 和 strict local-gate step。
2. `bin/gac/gac-local-gate.py` 是检查清单 SSOT；不得在新 workflow 复制清单。
3. `bin/ssot/script-registry.py` 与 `bin/_registry/scripts/**` 是 script registration 现有路径。
4. `.omo/_truth/registry/governance-checks.yaml::subtraction_quota.script_baseline` 是 baseline 当前权威字段。
5. `.omo/_truth/registry/ci-surfaces.yaml` 是 CI 接线事实 SSOT。
6. `bin/gac/gac-branch-protection.sh` 是 main protection 现有配置入口。
7. `bin/gac/omo-runtime-stamp-policy.py` 已能识别 tracked runtime files；
   `bin/ssot/root-directory-governance-scan.py` 已治理 root 目录形态。
8. Agent Workflow、独立 clone、PR、branch protection 和既有 GaC 构成唯一交付控制面。

### 2.3 直接观测到的缺口

1. `gac-gate` 的 `gac-local-gate (strict)` step 仍设置 `continue-on-error: true`。
2. main branch protection 只要求 `phase-gate` 与 `bet-done-transition`；`gac-gate` 不 required。
3. `ci-surfaces.yaml` 中 script-registry validation 没有权威 workflow binding；当前 schema/checker 只支持
   tool → workflow 级接线，不支持无人消费的 job/step 字段。
4. `gac-gate` 在 strict 前会执行 submodule pointer 同步、`git add`、generated digest 写入和
   `GAC_M1_SYNC_WRITE=1`；当前 success 可能来自被 CI 临时修改过的树，而不是 immutable PR final tree。
5. 已观察到新增活动脚本未登记、script baseline 未同步、Python 冲突标记、tracked runtime artifacts、
   proposal whitespace 和 ADR-0432 状态/内容矛盾。
6. 当前 `gac-branch-protection.sh` 使用整份 hard-coded PUT，不能证明只增加或回滚一个 context。
7. 现有 runtime/root scanners 对 tracked paths 有 blanket allow，尚不能审核 immutable final tree。
8. 这些事实可能随并发 main 推进而变化；执行时发现已由其他 PR 修复的项必须记为 `already_resolved`，不得重写。

## 3. 总体边界

### 3.1 In scope

- 恢复执行时最新 main 的可编译、script-registry 和 full GaC 基线。
- 把 ADR-0432 明确保持为 candidate / `UNPROVABLE`，并修复其结构性登记缺口。
- 让 existing `gac-gate` 的 strict step 真正阻断失败。
- 在成功 canary 后，将 existing `gac-gate` job context 加入 main required contexts。
- 从 Git index 移除误跟踪 runtime artifacts，同时保留本机数据。
- 扩展已有 runtime/root hygiene 机制，阻止同类 tracked artifact 再次进入 final tree。
- 做与本次污染直接相关的机械 whitespace 清理。
- 恢复被 archive 但仍被 Workflow、台账、blocking gate 或 strict 文档链接检查
  硬绑定的 canonical instruction pack、bin convergence manifest、root-directory
  policy、codebase-memory 与 knowledge-foundry SOP；恢复必须与 archive 源内容一致，
  仅可移除被 `git diff --check` 拒绝的无语义行尾空白。
- 修复 `ConstraintL0` 的既有 M2/M1 schema 一致性及 root M1 统计漂移，并以
  子仓先合、根 gitlink 后合的顺序恢复 latest-main admission。
- 修复 R1 直接触发的 root Agent Workflow 测试 harness 漂移：测试必须使用
  OMO 项目依赖环境，并且不再把已退役的 advisory external-agent audit 常量
  当作 canonical authority。

### 3.2 Explicitly out of scope

- 不新增 workflow、dispatcher、registry、数据库、broker、缓存或第二治理控制面。
- 不把 `phase-gate` 扩展成 full GaC；它继续只拥有阶段/owner-job 合同。
- 不接受、不完成、不提升 ADR-0432 的实证状态，不为其选择冲突中的指标值。
- R1/H1/R2a 不删除本机 runtime 数据，不改服务、LaunchAgent、plist、crontab、数据库内容或用户配置。
- R2b 只有在第二次精确人工授权后，才可执行 §7.3 列明的 producer stop/start、live checkout update、
  external backup 和 ignored restore；除此之外仍受上述禁止项约束。
- 不修改任何 BET 状态、completion evidence、value evidence 或 principal-bound value。
- 不做全仓 blanket cleanup，不顺手修复与执行时直接 failure set 无关的历史债。
- 不在 R1/H1/R2a/R2b 完成前启动 Product P0 Wave A writer。

### 3.3 2026-09-02 self-hosting recovery amendment

一次 archive move 将仍有 active consumers 的 operations contracts 移出其
canonical path，造成 `agent-workflow start`、`bin-scripts-convergence-audit` 与
strict `doc-link-check` fail-closed。该 amendment 恢复五个 archive 内容副本，
仅规范化被 `git diff --check` 拒绝的无语义行尾空白，并显式处理因此暴露的
`ConstraintL0` parent/required-property/计数漂移。
它不恢复其它 archive 文档、不登记广泛本机临时目录、也不把共享工作树的
ignored state 纳入 Git。

交付顺序固定为：bootstrap contract restore → normal T6-15 workflow → ecos
child schema repair and CI → root stats/gitlink adoption → fresh-clone GaC
replay。任一阶段出现 source drift、child CI 失败或新的 immutable failure
即停止，不以 escape 代替修复。

### 3.4 2026-09-03 R1 workflow-regression amendment

fresh-main R1 对 `bin/gac/gac-local-gate.py` 的 timeout repair 触发了 root
Agent Workflow regression。该 regression 暴露两个既有 test harness 漂移：root
wrapper fixture 只安装 PyYAML，无法加载 exact Mesh admission 所需的 OMO project
dependencies；projection test 仍断言已退役的 advisory audit implementation detail。
本 amendment 仅把这两个直接失败的 root tests 纳入 write surface，保持生产
workflow、Mesh authority 与 external-audit advisory 行为不变。

## 4. 交付拓扑与状态机

R1、H1a、R2a 每个 repository 阶段使用独立 delivery attempt，不得在共享 Workspace checkout 写入。
R2b 是另行授权的 live-host migration，不是 repository writer；它只能在 §7.3 的精确步骤和宿主路径上操作。

```text
R1 latest-main recovery PR
  acceptance: compile + registry + targeted ADR checks + full GaC green
      |
      v
H1a gate-hardening PR
  acceptance: existing gac-gate strict failure is blocking + CI surface tests
      |
      v
H1b main canary
  acceptance: merged H1a main receives a completed successful gac-gate run
      |
      v
H1c protection mutation
  acceptance: live contexts = phase-gate + bet-done-transition + gac-gate
      |
      v
R2a repository hygiene PR
  acceptance: artifacts untracked from final tree + recurrence test green
      |
      v
R2b explicitly authorized host migration
  acceptance: external backup + checkout update + ignored restore + digest proof
      |
      v
Product P0 Wave A preflight
```

每阶段开始前必须：

1. fetch 最新 `origin/main`；
2. 创建新独立 clone；
3. 运行 `agent-workflow bootstrap/status`；
4. 使用绑定到本 Spec 的 candidate BET 启动正式 workflow；
5. 重新计算差异和 failure set；
6. 对已被主线吸收的修复执行 no-op，不制造重复 PR。

本 Spec 当前是 `status=draft`、`bet_id=unbound`。书面 Spec 复核通过后，必须先以单独授权的 binding PR：

1. 选择或新增一个唯一 candidate BET；
2. 同步把本 Spec frontmatter 改为 `status=accepted` 和 exact `bet_id`；
3. 计算 accepted bytes digest 并写入该 BET 唯一 `accepted_specifications` binding；
4. 通过 binding lint 后，才允许进入 writing-plans。

在该 binding PR 合并前，禁止实现 R1/H1/R2，也不得把当前 draft 当作 workflow admission contract。

## 5. R1 — Baseline Recovery 合同

### 5.1 执行时 truth snapshot

R1 必须先产出机器可读 snapshot，至少包含：

- base SHA、head SHA、merge-base；
- `bin/ops/cli.py` compile 和全仓 conflict-marker 检查结果；
- script-registry active count、registered count、missing/extra exact paths；
- `script_baseline` 当前值和 validator 返回码；
- full `gac-local-gate --strict` 失败项及真实日志；
- ADR-0432 frontmatter、ID、INDEX 状态和内容冲突；
- tracked runtime artifact exact paths；
- `git diff --check` exact findings；
- root gitlink reachability，作为不动 submodule 的反证。

snapshot 是证据，不进入新的 registry 或状态库。

### 5.2 Python 与 conflict-marker 恢复

- 若执行时 `bin/ops/cli.py` 仍含冲突标记，删除标记并保留 latest-main 两侧可兼容语义。
- 若冲突已消失，则不得重写该文件。
- 必须先运行真实 compile 失败作 RED，再做最小修复并重跑 compile。
- 全仓 conflict-marker gate 必须为 0；不得只验证单文件。

### 5.3 Script registry 与 baseline

- missing scripts 由 `bin/ssot/script-registry.py` 的执行时输出决定，不能复制观测快照中的四个路径。
- 每个实际 active script 只在现有 `bin/_registry/scripts/**` taxonomy 登记一次。
- entry 必须声明真实 owner、lifecycle、entry point 和现有 contract 所需字段；禁止 placeholder owner。
- 先使 `active == registered` 且 duplicate/orphan 为 0，再将 `script_baseline` 精确同步为执行时 active count。
- baseline 更新只能反映已验证活动集合；不得为绕过 subtraction quota 人为抬高。
- 若 active count 相比执行开始继续变化，停止提交，rebase 到最新 main 后重新计数。

### 5.4 ADR-0432 candidate / UNPROVABLE

R1 只允许结构性恢复：

- 添加合法 frontmatter；
- 使文件名、frontmatter ID 与 decisions INDEX 唯一一致；
- 显式标记 `status: candidate` 和 `evidence_state: UNPROVABLE`；
- 把 0.0 与 0.15 等互斥 axis 结果记录为 unresolved contradiction；
- 不选择其中一个值，不声称模型已经接受，不生成 completion/value evidence。

若现有 ADR schema 不支持 `evidence_state` 字段，使用正文中的明确 Evidence Status 小节，
不得私自扩展 ADR schema。

### 5.5 R1 acceptance

R1 PR 只有在下列条件全部满足时才可合并：

```text
python compile                         PASS
conflict-marker full scan              PASS
script registry validate               PASS
script active == registered == baseline PASS
ADR number/index/frontmatter checks    PASS
full gac-local-gate --strict           PASS
git diff --check                       PASS
root gitlinks unchanged and reachable  PASS
```

R1 不触碰 branch protection。任何主线并发使结果失效时，PR 必须更新到最新 base 并重跑，而不是沿用旧绿灯。

## 6. H1 — Promote Existing `gac-gate` 合同

### 6.1 H1a repository change

H1a 只深化已有 gate：

1. 先把 `.github/workflows/gac-gate.yml` 的 blocking path 改为 immutable-checkout、check-only：
   - 禁止在 strict 前执行 submodule pointer 修复、`git add` 或 generator `--write`；
   - submodule 使用 `source=head` 的只读 reachability/final-tree check；若现有同步脚本要保留，必须新增并测试
     `--check-only`，不得在 CI 写 index；
   - generator 使用既有 `--check`，没有 check mode 的 generator 必须先增加 check mode 及测试；
   - 移除 `GAC_M1_SYNC_WRITE=1`，MOF 只运行 read-only validate/check；
   - blocking checks 前后都运行 `git diff --exit-code`、`git diff --cached --exit-code` 和
     `git status --porcelain`，任何变化都 fail-closed。
2. 在 immutable tree 上移除 strict step 的 `continue-on-error: true`，或显式设为 `false`；
   其它明确 advisory steps 保持原语义。
3. 在 `.omo/_truth/registry/ci-surfaces.yaml` 将 script-registry validation 绑定到 existing
   `gac-gate` workflow。当前 schema 只写受支持的 workflow-level binding；strict job/step 的传递性由
   workflow focused test 证明，禁止写无人消费的 job/step 字段。
4. 将 `bin/gac/gac-branch-protection.sh` 深化为
   guarded double-read read-modify-write: GET A -> validate/hash -> GET B ->
   require digest equality -> one required_status_checks subresource PATCH -> GET C
   verify. The API lacks a proven server-side conditional unsafe write, so a
   residual GET-B/PATCH race remains and is bounded by a second human gate,
   receipt and context-only rollback.
   并把 desired contexts 定义为：

   ```text
   phase-gate
   bet-done-transition
   gac-gate
   ```

5. 增加或修正 focused tests，至少锁定：
   - blocking path 前后 checkout/index/worktree 均不变；
   - strict step 不允许 `continue-on-error: true`；
   - `gac-gate` job name 稳定；
   - CI registry 指向真实 workflow，workflow test 证明 script-registry/strict step 接线；
   - branch-protection writer 读取 live payload，只改变 required contexts 并保留全部其它设置；
   - expected-before 不匹配时零写入停止；
   - `--check` 对 aligned/drift/unreadable 分别返回 `0/1/2`；
   - rollback 只移除 `gac-gate`，不删除整份 protection。

H1a PR 本身尚不授权修改 live branch protection。

### 6.2 H1b canary

H1a 合并后必须观察 main 上由该 merge 触发的真实 `gac-gate`：

- run 使用合并后的 main SHA；
- job 实际 started，不是 queued/cancelled/startup_failure；
- strict step 真实执行并 success；
- job conclusion=success；
- Actions 平台无导致证据不完整的 unresolved incident。

本地全绿、PR merge、其它 workflow 绿或旧 run 绿都不能替代该 canary。

### 6.3 H1c live branch protection mutation

只有 H1b 成功后，才允许通过深化后的 `bin/gac/gac-branch-protection.sh` 对 live main protection 做一次精确更新。
guarded double-read read-modify-write: GET A -> validate/hash -> GET B ->
require digest equality -> one required_status_checks subresource PATCH -> GET C
verify. The API lacks a proven server-side conditional unsafe write, so a
residual GET-B/PATCH race remains and is bounded by a second human gate,
receipt and context-only rollback.
脚本必须 GET 当前完整 protection payload，验证脱敏 digest 与 expected-before context set，
只把 `gac-gate` 合并进 contexts，保留其它所有可写字段，再 PATCH 和 GET 验证 exact after set。
expected-before 不恰为审议时集合时必须停止，由人类重新审议；不得覆盖未知新增设置。

禁止：

- 删除 `phase-gate` 或 `bet-done-transition`；
- 改 review 数、enforce-admins、force-push、deletion 或 linear-history 设置；
- 直接调用 API 写一个与仓内脚本不同的临时配置；
- 在 platform outage、queued-only 或 context name 未稳定时启用 required gate。

若 `gac-gate` 在启用后因平台机制故障无法产生 context，回滚只移除新增的 `gac-gate` required context，
保留原两项与 repository-side blocking 修复；回滚必须留下 API before/after receipt。

## 7. R2 — Hygiene 与复发预防合同

### 7.1 R2a — Repository final-tree untrack

- exact 集合由执行时 `git ls-files`、last-green comparison 和 existing runtime policy 共同确定。
- 对确定为 runtime/output/cache/database/heartbeat/smoke snapshot 的文件，只从 repository final tree untrack；
  `git rm --cached` 在 delivery clone 中只能证明 repository patch，不得声称 live host 数据已保留。
- canonical docs、immutable governance evidence、checked-in fixtures 和明确声明的 runtime contract 文件不得误删。
- 若分类不确定，保持 tracked 并标为 `UNPROVABLE`，不得猜测。

### 7.2 复发门

优先深化 `bin/gac/omo-runtime-stamp-policy.py`，因为它已经拥有 runtime 分类责任；
只有 root-level 非 `runtime/` artifact 无法被该机制表达时，才最小扩展
`bin/ssot/root-directory-governance-scan.py`。两者不得重复登记同一规则。

门禁必须：

- 只读；
- 接受 immutable `--treeish`，使用 `git ls-tree -r` 审核 final tree，而非工作树启发式；
- 移除“只要 tracked 就 allowed”的 blanket allow；
- 对 tracked forbidden artifact fail-closed；
- 对允许的 `runtime/README.md`、contract YAML、fixture 或显式 allowlist 通过；
- 输出 exact relative paths；
- 不依赖未提交工作树状态推断 final tree；
- 在现有 `gac-local-gate`/`gac-gate` 接线中复用，不新增 workflow。

### 7.3 R2b — Explicit host retention migration

R2a 合并不证明运行宿主保留。R2b 是独立、第二次精确人工授权的 host operation，也是本设计中
“不得写共享 checkout”规则的唯一窄 carve-out；必须：

1. read-only 解析 live Workspace 和实际 runtime owner paths；
2. 在 tracked checkout 之外创建有 owner/权限记录的备份，计算每个保留对象的 digest；
3. 停止会并发写这些对象的具体 producer；未确认 producer 时不得迁移；
4. 更新 live checkout 到已合并 R2a main；
5. 将批准对象恢复到 ignored runtime 落点，不恢复到 Git-tracked 状态；
6. 复验 digest、SQLite integrity（如适用）、owner/permissions 和 producer restart；
7. 写脱敏 before/backup/after/rollback receipt，再允许清理临时备份。

R2b 未执行或任一 digest/owner/producer 证据缺失时，retention 与 operational 均为 `UNPROVABLE`，
不得解锁 Wave A。R2b 不得借本 Spec bootstrap waiver 执行。

### 7.4 Mechanical hygiene

- 只清理 R1 snapshot 直接列出的 proposal trailing/EOF whitespace。
- 不改 proposal 语义、状态、决策、时间或证据。
- `git diff --check` 必须为 0；大范围格式化或 generated churn 禁止混入。

### 7.5 R2 acceptance

- R2a final tree 不再包含被批准的 runtime artifacts。
- focused policy tests 覆盖 forbidden/allowed/ambiguous 三类。
- full `gac-local-gate --strict`、`git diff --check` 和 fresh-clone checkout 通过。
- main post-merge `gac-gate` 成功，且 required context 真实出现在 protection API。
- R2b 的外部 backup、live checkout update、ignored restore、digest/integrity/owner/producer receipt 全部通过；
  否则 host retention 必须报告 `UNPROVABLE`。

## 8. 并发、PR 与写面规则

1. R1、H1a、R2a 各自唯一 PR、唯一独立 clone、唯一正式 workflow run；R2b 是独立 host operation receipt。
2. 同一阶段最多一个 writer；只读 reviewer 可并行。
3. 每个 PR 从开始时最新 main 创建；旧 clone 不复用。
4. 任何 required write surface 必须在 workflow claim 和 WorkPacket 中精确列明。
5. 子模块默认不变；若 truth snapshot 发现 gitlink failure，只报告并另开 child-first/root-last 设计，
   不把 gitlink recovery 混进本合同。
6. D0 交付为 add → commit → tag → push/PR；merge 后立即验证 main 并退役 clone。

## 9. Evidence 与 closeout

每阶段 closeout 至少记录：

- immutable base/head/merge SHA；
- changed paths 与 scope verdict；
- workflow run id、claims、verify/closeout 状态和 locks=0；
- focused tests、full GaC、CI run/job/step URLs 或 IDs；
- branch protection before/after（仅 H1c）；
- runtime files retained-on-host proof（仅 R2b，必须脱敏）；
- unresolved/UNPROVABLE 项与 rollback 建议；
- `value=NOT_PROVEN`。

任何 failure、platform outage、证据缺失或并发漂移都只能报告 `BLOCKED` / `UNPROVABLE`；
不得伪造 status、跳过 required context、提高 baseline 掩盖 failure 或将 BET/ADR 标 done/accepted。

## 10. Product P0 Wave A 解锁条件

Wave A（WP1 + WP4）只能在下列直接证据全部存在后开始：

1. R1 merged main full GaC green；
2. H1a merged，main `gac-gate` canary success；
3. live branch protection exact required set 含 `gac-gate`；
4. R2a merged main，tracked runtime final-tree regression gate green；
5. R2b host retention migration 直接证据通过；
6. 本 Spec 已完成 accepted frontmatter、ledger binding 和 writing-plans；
7. Product P0 parent/child BET 仍为 candidate，value 保持 `NOT_PROVEN`。

解锁只允许开始受治理的 Wave A；不证明任一 Product P0 child、父 BET或个人价值完成。

## 11. 验收标准

1. **R1 恢复执行时最新 main 的真实治理基线。**
   - 验证方式：在 fresh full clone 对 immutable merged SHA 运行 §5.5 全部命令，并核对 main CI run。
   - 证据类型：clone provenance、命令日志、exact failure/repair snapshot、merge SHA、main CI run receipt。

2. **H1a 的 blocking `gac-gate` 在 immutable final tree 上运行且零写入。**
   - 验证方式：focused workflow tests；blocking checks 前后运行 index/worktree/tree digest 比较；
     对一个确定失败 fixture 验证 job 非零退出。
   - 证据类型：测试日志、workflow YAML diff、pre/post tree receipt、失败 canary log。

3. **H1b/H1c 只在真实 main canary 后增量增加 existing `gac-gate` required context。**
   - 验证方式：读取 main SHA 对应成功 run；比较 live protection before/after；运行深化后的 `--check`。
   - 证据类型：Actions run/job/step receipt、脱敏 protection payload digest、guarded-update receipt、check exit code。

4. **R2a 从 immutable final tree 排除 forbidden runtime artifacts，且 checker 可重复读取。**
   - 验证方式：在 PR final tree、synthetic merge ref、merged main 和 fresh clone 上运行 treeish policy；
     验证 forbidden/allowed/ambiguous fixtures。
   - 证据类型：treeish SHA、focused test log、exact path findings、main `gac-gate` receipt。

5. **R2b 在第二次精确人工授权下保全 live-host 数据。**
   - 验证方式：逐项比较 backup 前、checkout update 后和 ignored restore 后的 digest/owner/permissions；
     对 SQLite 执行 read-only integrity check，并验证 producer stop/start receipt。
   - 证据类型：脱敏 before/backup/after/rollback receipt、digest、integrity result、producer lifecycle receipt。

6. **Product P0 Wave A 在全部前置条件前保持锁定。**
   - 验证方式：检查本 Spec accepted binding、R1/H1/R2a/R2b closeout 和 Product P0 candidate/value 状态。
   - 证据类型：ledger binding lint、workflow closeout receipts、protection API、BET status snapshot。

任一 assertion 缺少其列明 evidence type 时，结论必须为 `UNPROVABLE`，不得用其它成功信号替代。

## 12. 反指标

本 Spec 不把以下项目作为成功度量：

- commit、PR 数量或 diff 规模；它们只表示供给侧活动。
- 测试总数、GaC check 数或 dashboard 健康分；只有覆盖本 assertion 的直接证据有效。
- script baseline 的升高；baseline 只能同步已证明的真实活动集合，不能代表质量提升。
- `gac-gate` workflow 出现或旧 run 成功；必须是 immutable target SHA 的真实 blocking run。
- tracked artifact 数量下降；未证明 live-host 保全时 operational 仍是 `UNPROVABLE`。
- Agent、reviewer 或文档自报完成；不得替代 main、API、runtime 和人类授权证据。
- Product P0 child/parent status 或个人价值提升；本工作恒为 `value=NOT_PROVEN`。

## 13. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | 直接推进 Product P0 vs 先恢复 main | 先 R1 → H1 → R2 | 当前 required contexts 可漏过完整治理失败，继续并行会放大污染 |
| 2 | 新建 gate vs 复用 `gac-gate` | 复用并深化 existing job | 避免第二 CI 权威和 context 漂移 |
| 3 | 扩大 `phase-gate` vs 保持职责单一 | 不扩大 | phase gate 只拥有阶段/owner-job 合同，不复制 full GaC |
| 4 | CI 自修复后验证 vs immutable final-tree check | immutable、check-only、零写入 | 被 CI 临时改写的树不能代表可合并树 |
| 5 | 全量覆盖 protection vs guarded double-read 增量更新 | guarded double-read，只增/删 `gac-gate` | 保留并发新增设置与既有安全属性，支持精确回滚 |
| 6 | CI registry 增加 job/step 字段 vs 使用现 schema | workflow-level binding + focused test | checker 只消费 workflow 字段，禁止声明无人执行的合同 |
| 7 | 工作树扫描 vs immutable treeish | `git ls-tree` final-tree policy | PR/merge admission 必须证明提交树，而非本地瞬态 |
| 8 | repo untrack 同时声称宿主保全 vs R2a/R2b 分离 | 分离 | clone index 变化不能证明 live host 文件仍存在 |
| 9 | ADR-0432 接受一个冲突指标 vs candidate/UNPROVABLE | 保持 candidate/UNPROVABLE | 当前直接证据互斥，不能选择性升级 |
| 10 | 当前 draft 直接绑定 BET vs 先书面复核 | draft/unbound，复核后另行 binding PR | 遵守用户审批顺序和 exactly-one accepted binding |

## 14. 自举授权

本 draft Spec 与对应 waiver 使用一次性无 BET 自举，因为 requirement-iteration start 对无 `--bet` 的需求文档
明确 fail-closed。授权只覆盖这两个新文档；见
`.omo/_truth/governance-evidence/waiver-2026-08-28-post2408-recovery-gac-required-spec-bootstrap.md`。

## 15. 变更历史

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-08-28 | 初始 draft；吸收双 reviewer 对 immutable CI、CAS protection、treeish policy 和 host retention 的审查 | Codex / human-principal authorized |
| 2026-09-02 | 1.0.2：增加 archive self-hosting restoration 与 ConstraintL0 cross-repo recovery 顺序 | xiamingxing authorized |
| 2026-09-03 | 1.0.3：strict CI 复现两条仍被 active documents 引用的 archive 断链，补入最小恢复面；仅移除 Git 质量门拒绝的行尾空白 | xiamingxing authorized |
| 2026-09-03 | 1.0.4：R1 strict gate timeout 修复暴露两个 root workflow regression test harness 漂移，纳入最小测试面 | xiamingxing authorized |
