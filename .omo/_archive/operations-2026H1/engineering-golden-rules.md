---
lifecycle: pattern
owner: governance-team
last_updated: 2026-08-24
title: Engineering Golden Rules — 工程铁律 (防复发模板)
type: doc
---
# Engineering Golden Rules — 工程铁律 (防复发模板)

> 差距治理 S4 (UX-NOISE / 模板固化) 产出。
> 背景: PR #2058 修复的 2 个预存 flaky 问题, 固化为工程模板防止复发。
> 每个规则都有实证根因 (来自真实事故), 不是理论建议。

## TP-RELATIVE: 测试时序相对断言铁律

**触发**: 任何时序敏感测试 / CI 冷启动 / 跨机器运行。

**根因实证** (PR #2058): `tests/test_lifecycle.py` 曾用绝对时间断言
`manager._last_used[...] > 100.0`。`_last_used` 由 `time.monotonic()` 设置,
CI 冷启动 runner 的 monotonic 时钟 <100s (实测 83.75/86.51) → 必然 flaky fail。

**规则**:
```markdown
## 测试时序铁律
- 禁用绝对时间断言 (`> 100.0`、`>= now-100`、`>= time.time()-X`)
- 必须用相对断言: `before = f()` → `assert f() > before`
- 允许的绝对参考: `time.monotonic() - 100.0` (相对当前, 非硬编码绝对阈值)
- 触发: CI 冷启动 / 跨机器 / 时序敏感测试
```

**验收**: 测试可在冷启动 runner + 长跑机器上均稳定通过。

## PATH-ANCHOR: 脚本路径代码位置锚定铁律

**触发**: 任何脚本访问 workspace 外路径 / 解析配置文件 / 定位资源。

**根因实证** (PR #2058): `mof-enforce.py` 曾硬编码 `HOME/Workspace`,
且 `main()` 直接 `BOUNDARY_FILE.exists()` 绕过 fallback → cascading 独立 temp HOME
下 exit 2 "边界规则不存在"。

**规则**:
```markdown
## 脚本路径铁律
- 路径解析必须以代码位置为锚: `Path(__file__).resolve().parents[N]`
- 禁止硬编码 `HOME/Workspace`、绝对用户路径等环境假设
- 必须能在隔离环境 (cascading / temp HOME / CI sandbox) 独立运行
- 提供 fallback 链: 硬编码路径 → script-relative → 项目相对
- 触发: 任何脚本访问 workspace 外路径 / 解析配置文件 / 定位资源
```

**验收**: 脚本在 temp HOME / 独立 clone / CI sandbox 均可运行。

## CAP-OWN: 能力删除防腐铁律 (S1)

**触发**: 删除/重命名任何注册在 mof-capabilities.yaml 或 capability-registry 的能力。

**规则**:
```markdown
## 能力删除铁律
- 删除能力前, 注册表 (mof-capabilities.yaml) 必须同步移除或标注 deprecated
- 删除必须证明消费方引用归零 (bos:// 注册、CLI 命令、agora tools)
- `check-capability-ownership.py` 的 IMPL-EXISTS error → 禁止提交
- 类比: submodule-guard 保护 gitlink, CAP-OWN 保护能力
```

**验收**: `python3 bin/gac/check-capability-ownership.py` exit 0。

## PROJ-FORCE: SSOT-投影同步铁律 (S1)

**触发**: 修改任何 SSOT 源 (agent-workflows/profiles、mof-capabilities.yaml 等)。

**规则**:
```markdown
## SSOT-投影同步铁律
- 改 SSOT 源后, 必须同步对应投影 (projection-sync / capability-registry 生成)
- post-commit hook 已自动触发 (bin/ssot/post-commit-sync-check.py)
- 若投影漂移 (CI check-docs-drift fail), 说明 SSOT 改后没提交派生文档
- 生成物残缺 (totals=0) → 自动 revert, 勿提交 (CI 完整环境会重新生成)
```

**验收**: 改 SSOT 后 commit, 派生文档随 commit 同步 (无 check-docs-drift fail)。

## GOV-REBAL: 派生文档-only fast-track 铁律 (S5)

**触发**: 变更面全部为派生文档 (docs/generated/*、CLI-REFERENCE、CAPABILITY-MAP、INDEX-MCP)。

**根因实证**: 治理密度已达规模不经济拐点 — 纯派生文档变更 (投影重生成, 无真实语义变更)
也走全量 ADR 占号 + workflow 仪式, 治理成本与变更语义不成比例。

**规则**:
```markdown
## 派生文档 fast-track 铁律
- 纯派生文档变更 (derived-only) → 走 project-doc-change/state-sync 轻量 workflow, 不需 ADR 占号
- 判定工具: bin/gac/check-derived-only-fast-track.py (gate: derived-only-fast-track, 软信号)
- 混入源码/SSOT/治理代码 → 常规 gate, 无 fast-track
- 目的: 把治理仪式花在真实语义变更上, 不为投影重生成付费
```

**验收**: `python3 bin/gac/check-derived-only-fast-track.py --file docs/CLI-REFERENCE.md` 输出 fast-track 建议。

## AUTO-FIX: 漂移检测→分类→修复闭环铁律 (S5)

**触发**: 检测到漂移 (SSOT 变更未同步派生文档 / 注册表 path 缺失 / 新脚本未登记)。

**根因实证**: 治理闭环 E-D-P-C 缺 F (修复环) — 检测只报告不修复, agent 手动补派生文档,
周而复始。post-commit-sync-check 只覆盖"子模块指针变更"一种触发。

**规则**:
```markdown
## 漂移修复闭环铁律
- 检测→分类→修复闭环: bin/gac/auto-fix-loop.py (gate: auto-fix-loop)
- DERIVED-STALE/ORPHAN-SCRIPT → 可自动修复 (--apply 应用 make sync-all-docs / script-registry register)
- PATH-DRIFT → error 级阻断, 需人工判断 (删除 vs 迁移, 类比 S1 omo_lint 案例)
- 能自动修复的漂移不许只报告不修 (防 E-D-P-C 缺 F 复发)
```

**验收**: `python3 bin/gac/auto-fix-loop.py` exit 0 且无 error 级漂移。

## UX-NOISE: 命令密度可观测铁律 (S5)

**触发**: 新增 cockpit/CLI 命令 / 命令密度增长。

**根因实证**: cockpit CLI 命令 149+ (含子命令 157), 兜底组 "其他" 承载 100 命令 (63%),
机制密度超过心智带宽 — 命令发现依赖 grep, 无密度可观测性。

**规则**:
```markdown
## 命令密度铁律
- 命令密度/重复/易混淆定位: bin/gac/command-discovery.py (gate: command-discovery, 软信号)
- 单场景组命令 ≥ 25 → 密度超阈值信号 (建议收敛/拆组)
- 新命令应先想"放哪个场景组", 避免膨胀兜底组 ("其他")
- 发现层: `cockpit help <关键词>` 模糊搜命令
```

**验收**: `python3 bin/gac/command-discovery.py` 输出密度分布 + 超阈值组信号。

## RUN-ID-PLACEHOLDER: run-id 占位符铁律 (G7, 2026-08-24)

**触发**: 治理文档 (spec / closeout / 复盘 / 复盘模板) 写 run-id 或 workflow 示例。

**根因实证**: Droid-Shield 的 workspace 级拦截把文档里出现的真实格式 run-id
(如 `20260824T102541Z-governance-audit-d4e3ea25`) 当作运行时事实误报拦截 (CONV-3 被堵)。
治理文档频繁引用 run-id 示例 (spec 绑定 / closeout evidence), 导致无谓误报。

**规则**:
```markdown
## run-id 占位符铁律
- 治理文档写 run-id 必须用占位符, 不写真实格式完整字符串:
  - 正确: `<run-id>` / `<timestamp>-<workflow>-<hash>` / `20260824T...Z-<workflow>-<hash>`
  - 错误: 真实格式 `20260824T102541Z-governance-audit-d4e3ea25` 直接入文
- 确需引用真实 run-id 时, 显式标注为运行时事实 (如 "runtime fact: <run-id>")
- 模板/示例一律占位符化, 防 Droid-Shield workspace 级误报
```

**验收**: 治理文档 grep 无未标注的真实格式 run-id 字符串 (可被占位符正则匹配)。

## BASE-TREE-SNAPSHOT: GitHub API 建 commit 必须 base_tree 完整快照铁律 (T10 验收会话)

**触发**: 任何通过 GitHub API (gh api / REST / MCP) 建 commit / 更新分支 ref 推送交付物。

**根因实证** (2026-08-24, G5/G6 轮): 用 API 建 commit 时 `base_tree=None`
(GitHub 工具默认行为), 结果 tree 只有 7 个 G5/G6 文件 blob —— **`.github/workflows/`
整个被删**, GitHub 无法解析任何 workflow → CI **0 runs**。debug 链 (PR #2123 → API
重建 #2126 → workflow_dispatch 422 → 空 commit → force ref → close/reopen) 全部失败,
最后才发现分支上 workflow 文件 404。**GitHub Git Data API 的 tree 参数是完整快照,
不是 patch** —— 只列要改的文件 = 其余路径全部消失。

**规则**:
```markdown
## API 建 commit 铁律
- tree 必须带 base_tree: 父 commit 的完整 tree sha (base_tree=None = 整棵树被删)
- tree 只列变更 blobs + base_tree 指向完整父树, 二者缺一不可
- 推送后必须先验证 `.github/workflows` 存在 (gh api .../contents/.github/workflows?ref=<branch>)
- 验证通过再等 CI; 用 bin/gac/gh-api-push.sh 一键完成 (内置 base_tree + workflows 检查)
- 触发: 任何 GitHub API 建 commit / 更新 ref / 推送分支
```

**验收**: API 推送后 `.github/workflows` 存在 (48 个 workflow 不消失), CI 正常触发。

## SCHEMA-VALIDATOR-FIRST: schema 数据先读 validator 铁律 (T10 验收会话)

**触发**: 填写任何受校验的 schema 数据 (completion_evidence / receipt / 台账字段 /
注册表) 并依赖它通过 gate。

**根因实证** (2026-08-24, T10 closeout 轮): `bet-ledger complete` 连续三轮报错:
① `engineering.diff.ref must use repo:// or receipt://` (误用 `git://`);
② `merged_reachable_commit.ref is not reachable from origin/main` (伪造 40hex 未验证可达);
③ `OVERALL_STATE_MISMATCH: declared=None` (漏声明 overall_state)。
**报错驱动式填数据** —— 每步都是 validator 教的, 浪费三轮往返。

**规则**:
```markdown
## schema 数据铁律
- 填任何受校验数据前, 先读 validator 源码:
  - required keys: COMPLETION_DIRECT_EVIDENCE (各 status 的必填 key)
  - ref 协议枚举: _validate_evidence_reference (diff→repo://|receipt://,
    merged_reachable_commit→git://origin/main@40hex)
  - derived 判定: 三轴全绿才 outcome_accepted
- 引用 commit 先验证可达: git merge-base --is-ancestor <sha> origin/main
- 不写没验证过的 SHA / ref; 声明所有 derived 字段
- 触发: completion_evidence / attestation / 台账 / 任何 schema 数据
```

**验收**: schema 数据一次通过 validator, 无"报错驱动式"多轮往返。

## TIME-FIRST-TRIAGE: CI 失败先算时间戳再归因铁律 (T10 验收会话)

**触发**: 任何 CI 失败排查 / 判定是否"环境性 / flaky / 与改动无关"。

**根因实证** (2026-08-24, PR #2133): interface-check 稳定 fail (rerun 两次都 fail),
main 同 job pass。抓日志发现唯一差异是 `meta-doctor ok:false` ——
`system_health.yaml` 的 `last_scan` 超 48h SLA。main run (12:14) age=47.7h 恰好 pass,
我们的 run (12:38) age=48.1h 恰好 fail。**同一 commit 同一文件, 纯粹是运行时刻跨过
SLA 边界**。第一反应是"main 也红过 interface-check"→ 直接下"环境性"结论, 没先算
时间戳 (AGENTS.md 诊断三步法第 1 步没执行)。实际是**可修的状态过期**, 不是不可控环境。

**规则**:
```markdown
## CI 失败归因铁律
- 先算时间/age: date + 时间戳换算 (如 last_scan 距 now 多少小时 vs SLA)
- 别凭"main 也红过 / 之前见过"断定环境性 —— 先量化再归因
- heartbeat 状态文件过期 (.omo/state/system_health.yaml last_scan 超 SLA)
  → 是"可修的状态", 刷新即治本 (正常维护, 不是环境)
- 只有"反证找过 + 时间戳算过 + 与改动无关已证"才能标 blocked/环境性
- 触发: 任何 CI 失败 / flaky 判定 / 环境性 closeout
```

**验收**: 所有环境性 closeout 都附时间戳计算证据, 无凭印象归类。


## SCRIPT-BASELINE-SYNC: 新增 bin/ 脚本必须同步 subtraction_quota 铁律 (2026-08-25)

**触发**: 任何 PR 新增/修改 `bin/` 下 `.py`/`.sh` 脚本, 或 CI 报 `subtraction-quota`。

**根因实证** (2026-08-25, main 连续 3 次红): 并发 agent 在 PR 里新增 bin/ 脚本
(closeout-audit / worktree-init / gh-api-push → #2143, north_star_meter_v3 → #2145,
agent-presence → #2148, fix-frontmatter → #2146), 但**没在同一个 PR 里同步**
`governance-checks.yaml` 的 `gac.subtraction_quota.script_baseline`。合入后 main 立即红
(`bin/ 活跃脚本 N 超基线 M`), 只能事后补 baseline (如 #2154 486→487 这类跟随修复),
形成"加脚本 → main 红 → 补 baseline"的重复事故循环。根因是减法配额 (BET-Y1Q3-T6-05)
**只做全量计数, 不做 diff 感知**, 新增脚本无法在 PR 阶段被提前拦截。

**规则**:
```markdown
## 新增脚本同步铁律
- 在 PR 里新增 bin/ 下 .py/.sh → 必须同时改 governance-checks.yaml
  subtraction_quota.script_baseline = 当前 active 数 + 新增数
- CI 报 subtraction-quota 超限时, 错误消息带建议值 (script_baseline → N),
  照抄更新即可; 不要删/归档他人脚本去压数 (会误伤并发交付)
- 若只是改已有脚本/加 registry yaml (非 .py/.sh), 不需要动 baseline
- 触发: 任何新增 bin/ 脚本的 PR / subtraction-quota CI 失败
```

**验收**: 新增 bin/ 脚本的 PR 在合并前 gac-validate 通过 (baseline 已在同 PR 同步),
无事后 baseline 跟随修复。
