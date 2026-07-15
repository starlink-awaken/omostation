---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-15
---

# omostation 演化护栏 (P76 + P77 沉淀 40 原则)

> **For agents**: 这是 omostation 治理演化的"宪法" — 每一原则都从一次具体的 debt 类收敛而来。
> 当你做出架构决策时, 先看这里. 当你治理一个 follow-up 时, 能从中找到对应原则。
> **Source-of-truth**: STRAT-P76 / STRAT-P77 路线图 + ADR-0155..0165.
> **Catalog location**: `.omo/standards/p76-principles.md` (Phase 11 落地, P77 STRAT § 2 Phase 2)

## 0. 原则汇总表 (Summary Table, P77-2-2 catalog-SSOT 形式化)

| code | name | 含义 |
|------|------|------|
| P76-6-1 | **envelope-durability** | 守门必须有持久化输出 |
| P76-6-2 | **6h-by-9-deck** | 单人监控压缩到 6h 周期, 9 个 manual 节奏 |
| P76-6-3 | **monitor-by-rule** | 自监控也用 GaC 规则写 |
| P76-6-4 | **observability-first** | cockpit 面板 = 出口守门 = 用户感知 |
| P76-6-5 | **vit-via-LLM-deferral** | LLM-assisted commit 推到 Phase 7+ |
| P77-2-1 | **principle-formalization-with-context** | 原则形式化保留"上下文", 不变成死的 checkbox |
| P77-2-2 | **catalog-SSOT** | 原则 catalog 是 SSOT, ADR § 2 是 mirror |
| P77-2-3 | **rule-per-principle** | 每个原则对应一条 GaC rule (enforcement path) |
| P77-2-4 | **anti-rollback-baseline** | 阶段尾必重放 baseline (governance ≥ 起点), 防回退 |
| P77-2-5 | **multi-agent-coordination-via-ssot** | 跨 agent 协作走 catalog, 不靠"应该都知道" |
| P77-3-1 | **strict-regex-by-boundary** | detector regex 必须有 boundary 断言, 避免 substring 误判 |
| P77-3-2 | **prefix-pattern-allowed** | URI 末尾 `/` 表 routing prefix, 不需具体服务注册 |
| P77-3-3 | **remediation-over-suppression** | unregistered 治本 = 补登 SSOT, 而非放宽 threshold |
| P77-3-4 | **hard-only-after-zero** | enforcement: hard 仅在治本完成 (unregistered=0) 后启用, 避免 CI 永红 |
| P77-3-5 | **tool-evolution-via-tests** | detector 升级必须先有测试断言新行为 |
| P77-4-1 | **yaml-comment-strip** | YAML parser 不 strip inline comment, detector 必须手动 strip (`  #` 分割) |
| P77-4-2 | **registry-uniq-by-name** | duplicate (同号同名) 是信息, conflict (同号不同名) 是错误 — 区分 severity |
| P77-4-3 | **ssot-by-canonical-name** | 跨仓 registry 冲突时, 取 protocols/port-registry.yaml 为 SSOT (I0 > L0) |
| P77-4-4 | **aligned-comment-padding** | 端口名对齐后, 注释对齐 (`name  # comment` 保持 2-space 分隔) |
| P77-4-5 | **multi-ssot-warning** | 多 SSOT 同一数据是技术债 — 治本 = 砍掉一个 (或显式 deprecation) |
| P77-5-1 | **port-registration-mandatory** | 任何 service 端口必须先在 SSOT 注册, 否则 hard fail |
| P77-5-2 | **legacy-external-allowlist** | 外部服务允许硬编码 + 显式 LEGACY_OK_PORTS (otel/vite/lm-studio/family-hub) |
| P77-5-3 | **environment-variable-preferred** | 优先用 env var, 而不是字面量 (修真修真, Phase 6 入口) |
| P77-5-4 | **port-context-pattern** | detector 必须用 7+ port-context 模式覆盖 (PORT=/port=/--port/host:port/...) |
| P77-5-5 | **detector-evolution-via-catalog** | detector 升级必须先有测试断言新行为 (沿用 P77-2-3 + P77-3-5) |
| P77-6-1 | **e2e-test-for-advisory-tool** | advisory 工具必须有 E2E 测试验证不动手时无害 |
| P77-6-2 | **tier-test-for-fallback** | 每级 fallback 都必须有测试证明不崩溃 |
| P77-6-3 | **gateway-status-documentation** | 外部 LLM gateway 不可达时, 必须文档化不可达状态 |
| P77-6-4 | **tool-logic-test-before-e2e** | 测试先覆盖纯逻辑函数, 再 E2E |
| P77-6-5 | **catalog-update-per-phase** | 每 phase 收口必更新 catalog 原则表 (P77-2-2 强化) |
| P77-7-1 | **env-var-SSOT** | port→env_var 映射 SSOT 在 port-registry.yaml env_vars 段 |
| P77-7-2 | **literal-fallback** | env var 读取必须有 literal fallback, 防空 env 时崩溃 |
| P77-7-3 | **env-only-enforcement** | `env-only` 类型端口必须通过 env var 引用 |
| P77-7-4 | **root-first-submodule-later** | 治理工具根仓先行, submodule 代码后续迁移 |
| P77-7-5 | **cross-repo-env-contract** | 跨仓间 env var 命名必须一致 |
| P78-1 | **dead-port-cleanup** | 端口功能收敛后必须从 SSOT 显式标记 status: deprecated |
| P78-2 | **transport-declaration** | 每个注册端口必须声明 transport 类型 (stdio/http/sse/udp) |
| P78-3 | **conflict-lifecycle** | conflicts_pending 不再 pending 时必须转 resolved 或清理 |
| P78-4 | **ssot-status-machine** | 注册表每个条目标 status: active|deprecated|reserved |
| P78-5 | **registry-as-source** | port-registry 是传输方式和状态的 SSOT |
| P79-1 | **baseline-replay-after-phase** | 每 phase 收口后重放 governance baseline |
| P79-2 | **bin-config-ssot-alignment** | bin/ 和 config/ 的端口引用必须与 port-registry 一致 |
| P79-3 | **foundry-deck-per-governance-axis** | 每治理轴对应一个 foundry deck |
| P79-4 | **catalog-health-metric** | 原则数和 GaC 规则数作为可观测指标写入 foundry |
| P79-5 | **zero-planned-tasks** | 治理收口目标: planned tasks 清零 |
| P76-7-1 | **llm-advisory-not-autonomous** | LLM 只 generate suggestion, 永不 auto-apply |
| P76-7-2 | **tier-graceful-fallback** | LLM provider 3-tier — aetherforge → ollama → heuristic |
| P76-7-3 | **cron-real-deployment** | "投产" 不止写 plist, 必须 launchctl load |
| P76-7-4 | **evidence-honest-closure** | task close 必须有真 evidence |
| P76-7-5 | **resolve-not-stub** | 物理未实现的 placeholder, 必须决议 |
| P76-8-1 | **submodule-PR-not-coupling** | 跨仓 PR 独立提交, 不在主仓 commit submodule 内容 |
| P76-8-2 | **l0-honest-read** | 不 mock L0 数据; 真读 .yaml |
| P76-8-3 | **dead-path-tool-fallback** | 工具检查应该 first-level + projects/*/first-level 双路 fallback |
| P76-8-4 | **incremental-commit-anti-clean** | 每 sub-task 完成立即 commit, 防 X-Plane clean worktree 丢失工作 |
| P76-9A-1 | **git-native-trigger** | 不用 polling / daemon, 用 git 已有 hooks 机制 |
| P76-9A-2 | **sidecar-not-injection** | suggestion 写侧车 `.commit-suggestion`, 不直接修改 commit msg |
| P76-9A-3 | **fail-silent-not-fail-block** | hook 失败 → 不阻 commit |
| P76-9A-4 | **heuristic-default** | 本地调 `--no-llm` 不依赖外部服务可用 |
| P76-9A-5 | **respect-developer-intent** | `-m` / `-F` / amend / merge / squash 全部跳过 |
| P77-1 | **consistency-by-tool** | 跨仓一致性靠自动 verifier 守护 |

## 分类索引 (按 ADR 来源)

| 阶段 | ADR | 原则数 | 主线 |
|------|-----|------|------|
| Phase 6 | ADR-0160 | 5 | foundry runtime |
| Phase 7 | ADR-0161 | 5 | LLM + foundry cron 真集成 |
| Phase 8 | ADR-0162 | 4 | 真工程 follow-up 治本 |
| Phase 7.x | ADR-0163 | 5 | commit-assist hook |
| P77 Phase 1 | ADR-0164 | 1 | 跨仓一致性 |
| **P77 Phase 2** | **ADR-0165** | **5** | **演化护栏 catalog 自身** |
| **P77 Phase 3** | **ADR-0166** | **5** | **跨仓 unregistered 治本 (threshold 0 + hard)** |
| **P77 Phase 4** | **ADR-0167** | **5** | **跨仓 port-registry 一致性 (6 端口对齐)** |
| **P77 Phase 5** | **ADR-0168** | **5** | **跨仓端口硬编码扫描 (4 端口补登 + hard)** |
| **P77 Phase 6** | **ADR-0169** | **5** | **commit-assist E2E 验收 (19 测试 + heuristic bug 修)** |
| **P77 Phase 7** | **ADR-0170** | **5** | **端口 env var 重构 (25 env var 映射 + root repo 迁移)** |
| **P78** | **ADR-0172** | **5** | **端口注册表收敛 (deprecated 清理 + transport 字段)** |
| **P78 Phase 2** | **ADR-0173** | **5** | **基线重放 + Foundry v2 (bin/config 对齐 + health 95 + 10-deck)** |
| **合计** | — | **60 (55 ADR-internal + 5 hook)** | — |

> 注: P76 STRAT 原 claim "40 原则" 是早期估计. 实际沉淀 (按 ADR 表格) = **30 原则** (4-5 per phase × 6 phases). 数字更准.

## 1. Phase 6 (Knowledge Foundry runtime) — ADR-0160

### P76-6-1: envelope-durability
**含义**: 守门必须有持久化输出, 无 envelope = 不收门
**反例**: 写个"自监控"但只 print 到 stdout (发现漏执行, 但状态机下次启动没记忆)
**含义代码**: foundry run ledger 必须写到 `runtime/omo/_delivery/foundry/<id>.yaml` 而不是只在 stdout

### P76-6-2: 6h-by-9-deck
**含义**: 单人监控压缩到 6h 周期, 等价于 9 个 manual 节奏
**设计**: Knowledge Foundry 9-deck (omo-sync/compliance/p74-silent/mof-drift/m4-health/bootloader/debt-closed/submodule-bump/brief-gen) 在单次 cron 触发内全部跑完

### P76-6-3: monitor-by-rule
**含义**: 自监控也用 GaC 规则写, 不靠临时输出
**实施**: `CR-FOUNDRY-MONITOR` 规则 (governance-checks.yaml), 不是 foundry 自身的 doc

### P76-6-4: observability-first
**含义**: cockpit 面板 = 出口守门 = 用户感知
**实施**: `docs/operations/knowledge-foundry-monitor.md`, 不是每用户独立查 9 个 stdout

### P76-6-5: vit-via-LLM-deferral
**含义**: LLM-assisted commit 推到 Phase 7+, 不在本期 (避免 LLM 调度状态机)
**注**: Phase 6 显式不引入 LLM; 默认走 heuristic (l0_consumer 模式)

## 2. P77 Phase 2 (演化护栏 catalog 自身) — ADR-0165

### P77-2-1: principle-formalization-with-context
**含义**: 原则形式化保留"上下文", 不变成死的 checkbox
**反例**: 把 40 原则简化成 "P76-X-Y 满足/未满足" 二元表 → 失掉"为什么"和"反例"
**实践**: catalog 每条原则有 code + name + 含义 + 反例 + 实践, 不只是 ✓/✗

### P77-2-2: catalog-SSOT
**含义**: 原则 catalog 是 SSOT, ADR § 2 是 mirror — 防 source split
**反例**: 原则散落 5 个 ADR 各自不同版本
**实践**: 本 catalog 是真源, ADR § 2 引 "see .omo/standards/p76-principles.md § x"

### P77-2-3: rule-per-principle
**含义**: 每个原则对应一条 GaC rule (enforcement path)
**反例**: 原则只在 docstring, 无 check
**实践**: 5 新 GaC rules (PRINCIPLE-FOLLOWED / EVIDENCE-DECLARED / PR-CHECKLIST-COMPLETE / CROSS-REPO-CHECK / BASELINE-REPLAYED) 守护 5 治理护栏原则

### P77-2-4: anti-rollback-baseline
**含义**: 阶段尾必重放 baseline (governance ≥ 起点), 防回退
**反例**: phase 收口但 doc 漂回旧值
**实践**: `CR-BASELINE-REPLAYED` 规则, 每次 phase 收尾跑 governance score 验证

### P77-2-5: multi-agent-coordination-via-ssot
**含义**: 跨 agent 协作走 catalog (single source), 不靠"应该都知道"
**反例**: agent 2 假设 agent 1 已读某 ADR, 结果没读
**实践**: catalog 是必读 frontmatter, AGENTS.md 引用 catalog 路径

## 2.5. P77 Phase 3 (跨仓 unregistered 治本) — ADR-0166

### P77-3-1: strict-regex-by-boundary
**含义**: detector regex 必须有 boundary 断言, 避免 substring 误判
**反例**: `bos://memory/kos` 错误匹配 `bos://memory/kos/search` 的子串, 误判 unregistered
**实践**: regex 加 `(?![a-z0-9_/-])` 边界断言; 严格后 56 → 17 unregistered (减 39 false positive)

### P77-3-2: prefix-pattern-allowed
**含义**: URI 末尾 `/` 表 routing prefix, 不需具体服务注册
**反例**: 把 `bos://analysis/code/` (用作 startswith 前缀) 强制注册为真服务, 跑不起来
**实践**: detector 排除 trailing `/` URI; SSOT 仍可有真服务 (e.g. `bos://analysis/codeanalyze/scan`)

### P77-3-3: remediation-over-suppression
**含义**: unregistered 治本 = 补登 SSOT, 而非放宽 threshold
**反例**: 治本 = 把 threshold 调到 100 → 假装绿
**实践**: Phase 3 17 unregistered 全补登 SSOT (134 total), threshold 默认 0

### P77-3-4: hard-only-after-zero
**含义**: enforcement: hard 仅在治本完成 (unregistered=0) 后启用, 避免 CI 永红
**反例**: 改 enforcement: error 但 unregistered=56 → CI 永红
**实践**: Phase 1 advisory (threshold 20) → Phase 3 治本完成 → enforcement: error

### P77-3-5: tool-evolution-via-tests
**含义**: detector 升级必须先有测试断言新行为 (P77-2-3 rule-per-principle)
**反例**: 改 regex 边界断言, 旧测试 (--threshold 0 应 fail) 失效
**实践**: Phase 3 加 8 测试, 旧测试 1 个调整 (threshold 0 永远 pass, 改用 -1 测 fail 路径)

## 3. Phase 7 (LLM + foundry cron 真集成) — ADR-0161

### P76-7-1: llm-advisory-not-autonomous
**含义**: LLM 只 generate suggestion, 永不 auto-apply
**硬门**: 即使 LLM 100% confidence 也不能 git commit. developer 必须 `git commit -F .commit-suggestion` 显式接受

### P76-7-2: tier-graceful-fallback
**含义**: LLM provider 3-tier — aetherforge → ollama → heuristic
**实用**: 网慢 / 网不可达 / 网关宕 → fallback 第二层 → fallback 第三层 (永远不阻塞)

### P76-7-3: cron-real-deployment
**含义**: "投产" 不止写 plist, 必须 launchctl load + 验证 launchd 触发
**反例**: 写了 plist 但没 `launchctl load` → 实际没跑

### P76-7-4: evidence-honest-closure
**含义**: task close 必须有真 evidence; "drift detector 0" 仍需 radar_cron 输出
**反例**: 直接 `omo task done ID` 不带 evidence → 假装关闭 (ophist 反模式)

### P76-7-5: resolve-not-stub
**含义**: 物理未实现的 placeholder, 必须决议 (要么实现要么标 status), 不留隐含承诺
**应用**: `mesh-router` 不再在 doc 标 "需要 git submodule init", 而是 doc 标 `status: implemented-in-bin`

## 3.5. P77 Phase 4 (跨仓 port-registry 一致性) — ADR-0167

### P77-4-1: yaml-comment-strip
**含义**: YAML parser 不 strip inline comment, detector 必须手动 strip (`  #` 分割)
**反例**: `'agora-mcp-http             # [Phase 9] comment'` 被整串当 service name → 误判 conflict
**实践**: `_strip_yaml_comment()` helper 在 detector 中调用, 6 false positive → 0

### P77-4-2: registry-uniq-by-name
**含义**: duplicate (同号同名) 是信息, conflict (同号不同名) 是错误 — 区分 severity
**反例**: 把 6 duplicate 算 conflict → 修真修真, 永远 fail
**实践**: `find_port_conflicts()` 区分 `type=duplicate` vs `type=conflict`, summary 分两个 count

### P77-4-3: ssot-by-canonical-name
**含义**: 跨仓 registry 冲突时, 取 `protocols/port-registry.yaml` 为 SSOT (I0 > L0)
**反例**: 当冲突时, 留两个 — 修真修真
**实践**: 8080 + 9290 对齐到 protocols 名称 (`ontoderive-web` + `llm-gateway`)

### P77-4-4: aligned-comment-padding
**含义**: 端口名对齐后, 注释对齐 (`name  # comment` 保持 2-space 分隔)
**反例**: `name#comment` (无空格) 或 `name # comment` (1-space) → _strip_yaml_comment 解析不到
**实践**: 对齐后所有端口用 `name  # comment` 格式 (2-space)

### P77-4-5: multi-ssot-warning
**含义**: 多 SSOT 同一数据是技术债 — 治本 = 砍掉一个 (或显式 deprecation)
**反例**: 6 duplicate 永远留着 — "反正 detector 知道是 info, 修真修真"
**实践**: 留作 P78 large refactor, 当前只做 0 真 conflict 治本

## 3.6. P77 Phase 5 (跨仓端口硬编码扫描) — ADR-0168

### P77-5-1: port-registration-mandatory
**含义**: 任何 service 端口必须先在 SSOT 注册, 否则 hard fail
**反例**: 7430 (agora internal) 16 处硬编码, 不在 SSOT → 跨仓 port 冲突盲区
**实践**: `bin/ssot/check-hardcoded-ports.py` detector, unregistered=0 修真修真

### P77-5-2: legacy-external-allowlist
**含义**: 外部服务 (otel/vite/lm-studio/family-hub) 允许硬编码 + 显式 LEGACY_OK_PORTS
**反例**: 把 4318 (otel) 当 unregistered → 修真修真, 永远 fail
**实践**: 5 LEGACY_OK_PORTS (1234/3000/3001/4318/5173) 显式豁免 + 注释

### P77-5-3: environment-variable-preferred
**含义**: 优先用 env var, 而不是字面量 (修真修真, Phase 6 入口)
**反例**: `port=7422` 字面量 → 部署漂移 / 修真修真
**实践**: 治本方向: 把已注册 port 改成 env var 引用, detector 保留豁免 (Phase 6 留作)

### P77-5-4: port-context-pattern
**含义**: detector 必须用 7+ port-context 模式覆盖 (PORT=/port=/--port/host:port/...)
**反例**: 只检测 `port=NNNN` → 漏掉 16/19 hardcoded sites
**实践**: 7 patterns (PORT = / port= / --port / host:port / localhost / 127.0.0.1 / 0.0.0.0)

### P77-5-5: detector-evolution-via-catalog
**含义**: detector 升级必须先有测试断言新行为 (沿用 P77-2-3 + P77-3-5)
**反例**: 加新 pattern 但不更新 test → 修真修真
**实践**: 10 phase-5 测试 + 1 catalog 引用 (5 原则 P77-5-1..5)

## 3.7. P77 Phase 6 (commit-assist E2E 验收) — ADR-0169

### P77-6-1: e2e-test-for-advisory-tool
**含义**: advisory 工具必须有 E2E 测试验证不动手时无害 (P76-7-1 fail-safe 特化)
**反例**: commit-assist 是 advisory（不阻断 commit），但无测试 → 沉默失效半年
**实践**: 19 测试覆盖 heuristic/fallback/integration/tier; CR-COMMIT-ASSIST-E2E 规则

### P77-6-2: tier-test-for-fallback
**含义**: 每级 fallback 都必须有测试证明不崩溃 (P76-7-2 特化)
**反例**: aetherforge 不可达 → 抛 Exception → 整个 commit-assist 不工作
**实践**: `test_aetherforge_unreachable_graceful()` + `test_ollama_unreachable_graceful()` 断言返回 None

### P77-6-3: gateway-status-documentation
**含义**: 外部 LLM gateway 不可达时, 必须文档化不可达状态 + 时间戳, 不留"应该可用"假设
**反例**: aetherforge 挂了 2 周, 没人知道, 一直 fallback 到 heuristic
**实践**: ADR-0169 § 1.4 写明 "aetherforge: 不可达 (2026-07-07)"

### P77-6-4: tool-logic-test-before-e2e
**含义**: 测试先覆盖纯逻辑函数 (heuristic/parser), 再 E2E — 修真修真反模式
**反例**: 先花 30 分钟搭 temp git repo 做集成测试, 但 heuristic_subject bug ([-1] vs [0]) 几秒就暴露
**实践**: 19 测试中 14 个是纯逻辑/单元测试, 只有 3 个是集成

### P77-6-5: catalog-update-per-phase
**含义**: 每 phase 收口必更新 catalog 原则表 (P77-2-2 强化)
**反例**: P77 Phase 2-5 没更新 INDEX.md → INDEX 停更在 ADR-0052
**实践**: 本 phase 新增 P77 § 到 INDEX.md

## 3.8. P77 Phase 7 (端口 env var 重构) — ADR-0170

### P77-7-1: env-var-SSOT
**含义**: port→env_var 映射 SSOT 在 port-registry.yaml env_vars 段, 不分散代码里
**反例**: 各仓各自定义 AGORA_INTERNAL_PORT = 7430 → 跨仓不一致
**实践**: protocols/port-registry.yaml env_vars: 段, 25 端口映射, 各仓引用

### P77-7-2: literal-fallback
**含义**: env var 读取必须有 literal fallback (= SSOT 端口值), 防空 env 时崩溃
**反例**: `port = int(os.environ["LLM_GATEWAY_PORT"])` 无 fallback → env 未设置时 KeyError
**实践**: `port = int(os.environ.get("LLM_GATEWAY_PORT", "9290"))`

### P77-7-3: env-only-enforcement
**含义**: `env-only` 类型端口必须通过 env var 引用, detector 检测字面量 → warning
**反例**: 7422 是 env-only 但代码仍 `port=7422` → detector 未检测
**实践**: types: 段标记 env-only, CR-ENV-VAR-PORT 规则守护

### P77-7-4: root-first-submodule-later
**含义**: 治理工具根仓先行 (SSOT/migration helper), submodule 代码后续逐步迁移
**反例**: 想一次性全仓 refactor → 工程量巨大, 数月不动
**实践**: Phase 7a root repo, 7b+ 逐个 submodule PR

### P77-7-5: cross-repo-env-contract
**含义**: 跨仓间 env var 命名必须一致
**反例**: agora 用 AGORA_MCP_HTTP, omo 用 AGORA_HTTP_PORT → 运维混淆
**实践**: protocols/port-registry.yaml SSOT 命名, 各仓引用

## 3.9. P78 (端口注册表收敛) — ADR-0172

### P78-1: dead-port-cleanup
**含义**: 端口功能收敛后必须从 SSOT 显式标记 `status: deprecated`
**反例**: 8765/9090 收敛到 cockpit 后仍在 `ports:` 段无标注 → 新人误用
**实践**: `status: deprecated` + `transport: deprecated` 标记

### P78-2: transport-declaration
**含义**: 每个注册端口必须声明 transport 类型 (stdio/http/sse/udp)
**反例**: 新 reader 看到 3100 不知道是 stdio 还是 HTTP
**实践**: port-registry 结构化: 每个端口有 `name`, `transport`, `status`, `note`

### P78-3: conflict-lifecycle
**含义**: conflicts_pending 不再 pending 时必须转 resolved 或清理
**反例**: 8765/9090 收敛 2 周后仍在 conflicts_pending → 误导
**实践**: 已从 conflicts_pending 删除, 保留在 conflicts_resolved 供追溯

### P78-4: ssot-status-machine
**含义**: 注册表每个条目标 `status: active|deprecated|reserved`, 无隐含状态
**反例**: `# 收敛后已释放端口` 注释 vs 真代码 — 注释不执行
**实践**: `status: deprecated` 硬字段

### P78-5: registry-as-source
**含义**: port-registry 是传输方式和状态的 SSOT, 不从代码推断
**反例**: `mcp_transport_defaults` 注释又写一遍 transport → 双源
**实践**: transport 字段已入 ports 段, mcp_transport_defaults 保留供参考

## 4. Phase 8 (真工程 follow-up 治本) — ADR-0162

### P76-8-1: submodule-PR-not-coupling
**含义**: 跨仓 PR 独立提交 — 不在主仓 root commit submodule 内容
**实践**: aetherforge 仓 PR 跟主仓 PR 各自走自己的 repo. `git submodule update --init` 即可跟进

### P76-8-2: l0-honest-read
**含义**: 不 mock L0 数据; 真读 .yaml, 接受路径硬编码脆弱性
**反例**: aetherforge l0_consumer.py 真读 M1 *.yaml; 没用 fake dict 假装消费 8 个 namespace

### P76-8-3: dead-path-tool-fallback
**含义**: 跨仓路径不在根, 工具检查应该 first-level + projects/*/first-level 双路 fallback
**实施**: `bin/ssot/check-dead-path-refs.py` 接受 `.omo/{path}` OR `projects/ecos/.omo/{path}`

### P76-8-4: incremental-commit-anti-clean
**含义**: 每 sub-task 完成立即 commit, 防 X-Plane 反复 clean worktree 丢失工作
**应用**: P77 阶段我学到 — X-Plane 每 5-10 分钟 clean 一次 inactive worktree, 没 commit 的 WIP 全部消失

## 5. Phase 9A (commit-assist pre-commit-msg hook) — ADR-0163

### P76-9A-1: git-native-trigger
**含义**: 不用 polling / daemon, 用 git 已有 hooks 机制
**实施**: `prepare-commit-msg-commit-assist` 自动 trigger on `git commit`

### P76-9A-2: sidecar-not-injection
**含义**: suggestion 写侧车 `.commit-suggestion`, 不直接修改 commit msg (P76-7-1 advisory)
**反例**: 把 LLM output 直接 cat >> commit msg → 违反 advisory 硬门

### P76-9A-3: fail-silent-not-fail-block
**含义**: hook 失败 → 不阻 commit (P76-7-3 implicit)
**实施**: `exit 0` 永远, 即使 LLM 不可达 / 网慢

### P76-9A-4: heuristic-default
**含义**: 本地调 `--no-llm` 不依赖外部服务可用
**实施**: heuristic tier P76-7-2, 写 commit-assist 优先调 heuristic (offline-first)

### P76-9A-5: respect-developer-intent
**含义**: `-m` / `-F` / amend / merge / squash 全部跳过 (developer 显式意图)
**触发条件**: 仅 `git commit` (无 source arg) 才触发 hook

## 6. P77 Phase 1 (跨仓一致性) — ADR-0164

### P77-1: consistency-by-tool
**含义**: 跨仓一致性靠自动 verifier 守护, 不靠 review memory
**实施**: `bin/ssot/check-cross-repo-consistency.py` + `CR-CROSS-REPO-CONSISTENT` GaC 规则

## 7. 沉淀原则 — 治理护栏 (新增 5 个 GaC rules 计划)

| 新 GaC rule | 守护哪个原则 |
|-------------|--------------|
| `CR-PRINCIPLE-FOLLOWED` (X1) | 任意 phase 主交付前, ADR § 2 沉淀原则 列全 (P77-2-1) |
| `CR-EVIDENCE-DECLARED` (X4) | ADR closeout 引用 ≥1 evidence path (P76-7-4) |
| `CR-PR-CHECKLIST-COMPLETE` (X1) | 每个 PR 的 `--title` 不空 + body 含 why/what/next |
| `CR-CROSS-REPO-CHECK` (X3) | 5+ unregistered BOS URI 不允许 (P77-1, relates_to CR-CROSS-REPO-CONSISTENT) |
| `CR-BASELINE-REPLAYED` (X2) | 每次阶段尾 governance score 必 ≥ 起点 (P77-2-4 anti-rollback-baseline) |

> 治本路径: Phase 2 (W3-4) 实施这 5 个 GaC 规则. Phase 3 (W5-6) 升级 `CR-CROSS-REPO-CHECK` 为 hard.

## 7. 演进指南 (Evolution Guide)

新原则如何加入:
1. 在某个 phase 收口的 ADR 里, § 2 列原则 (≥3 原则)
2. 在本文档 (catalog) 加对应 §x 段
3. 在 INDEX.md 标 §2 段 (ADR 的 doc link)
4. 引入 GaC rule 守护 (如有 enforcement 路径, P77-2-3 rule-per-principle)

新 phase 命名规则:
- `P<major>-<digit>-<digit>` 顺序
- `P77-2-3` = P77 路线图 Phase 2 第 3 原则 (已用, see § 2)
- `P77-3-1` = P77 路线图 Phase 3 第 1 原则 (TBD)
- `P77-4-N` = P77 路线图 Phase 4 (TBD)

## 8. 现状快照 (Status Snapshot, 2026-07-07)

- **catalog**: 12 ADR 来源, 共 60 原则
- **GaC 规则**: 173
- **planned tasks**: 0
- **governance**: 95 A+ (P78 baseline replay)
- **foundry**: v2 — 10-deck (新增 port-governance deck)

---

*最后更新: 2026-07-08 · 60 原则沉淀 · P78 Phase 2 (基线重放 + Foundry v2) · ACTIVE*
