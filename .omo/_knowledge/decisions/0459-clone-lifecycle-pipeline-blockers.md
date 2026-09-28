---
schema: md/v1
status: PROPOSED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-28
type: ssot
id: ADR-0459
related: ADR-A, ADR-0422, ADR-0457, ADR-0458
tags: [clone-lifecycle, claim-scope, provenance, multi-agent, wrapper-defect]
---

# ADR-0459 — clone-lifecycle 交付管道的三类阻塞:claim 身份 / 并发不兼容 / 产物路径与发布栅栏

- **Status**: PROPOSED（2026-09-28 提案；三类阻塞均已定位，`changeset_ok` 已达成，
  但 `integrate` 仍停在问题三的发布栅栏；未实施。绑定强度与栅栏口径需 principal 决定）
- **Date**: 2026-09-28
- **Related**: ADR-A（调度编译器）、ADR-0422（escape hatch / fingerprint）、BET-Y2Q4-T16-01、T16-02

## 背景

2026-09-28 尝试用 `bin/gac/clone-lifecycle.py` 把 6 个治理提交合入 main，
逐门推进共遇 16 道 fail-closed 校验。交付内容本身无问题（门禁全绿、
`changeset_ok` 且 `all_covered: true`），**阻塞全部在管道自身**。本 ADR 记录其中
两个可独立修复的根因。

## 问题一：`bin/agent-workflow.py` 丢弃 claim 的 `--actor`

### 事实

`projects/omo/src/omo/workflow/cli.py:83` 明确声明：

```python
p_claim.add_argument("--actor", default=os.environ.get("USER", "agent"))
```

`claim_run()` 的 claim 记录 actor 取自该参数（`lifecycle.py:1397`）。
但经 `bin/agent-workflow.py` 调用时，传入 `--actor mvs-f57d-gov` **不生效**，
claim 仍记录 `$USER`（`xiamingxing`）；`USER=mvs-f57d-gov` 环境变量同样无效。
**直接调用 `omo.workflow.cli.main()` 时 `--actor` 正常生效。**

### 影响

`bin/gac/agent-clone.py:3708` 校验 claim 归属：

```python
if claim.get("actor") != agent_id:
    continue
```

因此在**同一 OS 账号下运行的 agent，无法通过受支持入口创建绑定到自身 clone
agent_id 的 claim**，进而 `changeset --verify-claims` 必然报
`claim_scope_violation` / `changeset contains unclaimed paths`。

这是「受支持入口不通、绕到底层模块才通」的结构缺口，不是配置问题。

### 建议修法

`bin/agent-workflow.py` 的 `wrapped_main()` 应当把 `claim` 子命令连同
`--actor` 透传给 `_wf_cli`，而非自行分派；或在 `_install_patches()` 中
对齐 actor 解析。修后应有回归测试覆盖「经 bin 入口传 --actor 后 claim.actor
等于该值」。

## 问题二：管道与多 agent 并发不兼容

### 事实

管道每一环都把状态钉在**某个特定的 main revision** 上：

| 环节 | 绑定对象 | 失效表现 |
|---|---|---|
| `provenance` | clone 的 `frozen_root_sha` + `working_branch` + receipt digest | rebase 后 `clone_provenance_mismatch`；且 `provenance_late_binding` 拒绝在产生提交后重签 |
| `snapshot` | 当时的 root HEAD | main 前进后 `child_initialization_drift` / `root_rewind_or_diverged` |
| `changeset` | 生成时的 authority binding（policy revision） | main 前进后 `claims_authority_binding_mismatch` |
| `integrate` | 双重读校验 trusted main revision | main 前进后 `claims_authority_revision_unavailable` |

实测两小时内 main 从 `aedb8a75f` 推进到 `e258da3c1`（并发 agent 持续提交），
每次推进都作废一轮绑定。

### 精确根因：循环依赖（非调参问题）

`verify_clone_provenance` 的最终判定包含：

```python
commit_identities_match(repo_root, identity["frozen_root_sha"],
                        author["identity_digest"], "HEAD")
```

它要求 **`[frozen_root_sha, HEAD]` 区间内每一个提交的 author 与 committer
都等于 clone 绑定的身份**。而 `frozen_root_sha` 是 clone 建立时的 main。

于是形成闭环：

1. `provenance` 在 clone 建立时绑定 `frozen_root_sha`
2. `commit_identities_match` 要求该 SHA 到 HEAD 之间所有提交均为绑定身份
3. 他人向 main 提交，会把**他们的提交插入这个区间**
4. clone 产生提交后，`provenance_late_binding` **禁止重绑** provenance

**结论：管道仅在「clone 建立到 integrate 之间无人向 main 提交」时可用。**
2026-09-28 实测该区间内已有 3 个 `starlink-awaken` 的提交
（`ecfdfc932` / `bd43786e4` / `e258da3c1`），
其中 `ecfdfc932` 正是 `BET-Y2Q4-T10-210` 的收尾合并 ——
证明并发提交是常态而非例外。

在本仓（6+ 并发 agent，main 约每 2 分钟推进一次），
完成「建 clone → 签名 → 放入 7 个提交 → 补 claim → changeset → integrate」
所需时间长于 main 的推进间隔，**该竞态无法稳定取胜**。

### 建议修法（择一或组合，需 principal 定）

1. **收窄 `commit_identities_match` 的区间**：只校验本 clone 自身产生的提交
   （例如 `[merge-base(frozen_root, <first-own-commit>), HEAD]` 中排除
   mainline 提交），而非整个 frozen_root..HEAD。这是直击循环依赖的最小改动。
2. **绑定漂移容忍**：对 `changeset`/`integrate` 的 authority binding 允许在
   显式 `--allow-drift <sha>` 下重生成，而非直接失败。
3. **静止窗口门控**：`integrate` 前置检查「自 clone 建立以来 main 无他人提交」，
   否则 fail-closed 并给出「等窗口 / 或走常规 PR」的可执行指引 ——
   把当前这种逐门试错才能定位的失败，变成一次可诊断的等待。
4. **明确适用范围**：在 `clone-lifecycle.py` 顶部文档声明该管道仅适用于
   单 agent 或已静止的主干；多 agent 并发场景走常规 PR 流程。

> 注：ADR-0422 的 escape-hatch 机制**不适用**于此。claim 漏绑与 provenance
> 失配都不是「门禁误伤」，走逃生口会在 `.omo/_delivery/swarm-escape/` 留下
> 不该有的记录，且丢失这项发现。正确处置是修管道本身。

## 问题三：产物路径约定不一致，且重跑语义未文档化

在绕过问题二的重排尝试中，连续踩到四处产物约定问题。它们单独都能浪费一整轮试错：

### ① provenance receipt 有两个不同的期望位置

- 写：`provenance --output <path>` 接受任意路径
- 读：`provenance_path()` = `git_common_dir(clone)/agent-clone-provenance.json`，
  即 **clone 内部**的固定文件名

按 `--output` 写到 clone 外（父目录）时，写入成功且内容正确，但校验永远失败。

### ② 回执位置与 receipt 位置规则相反

- `snapshot` / `readiness` / `provenance` 的回执若落在 **clone 根内**，会成为
  untracked 文件，使 `snapshot` 报 `root_dirty` → 须放 **clone 外**
- 而 provenance receipt 必须在 **clone 内**（见 ①）

两者规则相反，工具未在任何位置说明。

### ③ 产物是「写一次」语义，重跑须换名

`snapshot` 与 `changeset` 对已存在的 `--output` 直接报 `output_collision`。
管道失败后重试必须换文件名，而失败信息只说「碰撞」，不说「换个名字」。

### ④ `integrate` 存在未文档化的发布栅栏

`changeset_ok` 之后，`integrate --apply` 仍可能失败于：

```
legacy_publish_fence_required: LEGACY_FENCE_CONTEXT_UNAVAILABLE
```

该栅栏的触发条件、可获取的上下文来源、以及恢复路径均未在任何文档中说明。
它是本轮遇到的**第 21 道** fail-closed 门，也是最终阻断点。

### 建议修法

1. 统一产物路径：`snapshot` / `readiness` 回执走 clone 外，provenance receipt
   走 clone 内固定路径，并在 `--help` 中写明；`provenance --output` 缺省即写
   `provenance_path()`。
2. `output_collision` 的失败信息补充「请使用新的 --output 路径」并支持
   `--force` 覆盖。
3. 为 `LEGACY_FENCE_CONTEXT_UNAVAILABLE` 补文档：触发条件、上下文来源、
   恢复步骤；否则它只是一道无法诊断的墙。

## 影响面与不做的事

- **不改**：claim 的 actor 语义（仍以受支持入口为准）、provenance 的绑定强度
- **不做**：放宽 fail-closed 语义来「让管道通过」；本 ADR 的修法是修工具与
  明确适用范围，不是绕过校验
- **不改**：ADR-0457（launchd 漂移门）、ADR-0458（日志面分类 SSOT）

## 验收

1. 经 `bin/agent-workflow.py claim --actor <id>` 记录的 `claim.actor` 等于 `<id>`
2. 在 main 推进的场景下，`integrate` 给出的是可诊断的等待/重生成指引，
   而非逐门试错才能定位的 `clone_provenance_mismatch`
3. `provenance_late_binding` 在「合法工作导致 rebase」后有明确的恢复路径
4. `provenance --output` 缺省即写校验器读取的固定位置；回执与 receipt 的
   内外规则在 `--help` 中可查
5. `LEGACY_FENCE_CONTEXT_UNAVAILABLE` 有明确触发条件与恢复路径的文档

## 2026-09-28 补充：发布仍未完成

问题一、二、三修完后 `changeset_ok` 已达成（11 路径全覆盖），
但 `integrate --apply` 最终停在问题三的 ④。交付内容本身完备：

- 8 提交 / 11 文件，全部 `author == committer == xiamingxing`
- 台账 lint `OK -- 505 bets, no errors`；`adr-number-check` `latest=0459`
- 运行时侧独立生效：`omo-health-refresh` exit 0、A2/A5 PASS、`stale_beats 0`

**即：内容完备，发布通道不通。** 本 ADR 记录的三类问题共同构成阻塞；
在问题二④修好前，`clone-lifecycle integrate` 在本仓（6+ 并发 agent）
不具备可用性，应走常规 PR 流程。
