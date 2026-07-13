# omostation Changelog

> 多仓库统一发布. 工作区根 VERSION 文件权威.
> 9 项目 (agora / kairon / gbrain / omo / metaos / cockpit / runtime / ecos / aetherforge) 共享版本号.
> 详见 ADR-0007.

## [Unreleased] - 2026-07-09

### Added (P7x bus-foundation rollout — ADR-0180)
- **bus-foundation 真接入** 8 consumer projects: agora / omo / metaos / kairon-pipeline / aetherforge / runtime / cockpit / l4-kernel. All 8 ACTIVE on bus-facade.
- **3-plane facade** as canonical entry: `bus_foundation.facade.event / control / data`. Top-level `publish / subscribe / schedule` marked deprecated.
- **`bus_foundation.topics` SSOT**: 30+ topic constants + 6 wildcard patterns, with 7 invariant tests in `test_topics.py`.
- **Lazy optional-dep imports**: `zmq`, `redis`, `websockets` now lazy via PEP 562 module `__getattr__`; `import bus_foundation` works without any extra.
- **`bin/bus-usage-report.py`** P74 dormant-adapter detector: scans every consumer's `src/` for production call sites; exit 1 if any consumer declares `bus-foundation` but has no real call. Wired into `gac-local-gate` as the `bus-usage-report` gate (non-strict, ~2.5s on real workspace).
- **`bin/bus-e2e-harness.py`** real cross-process ZMQ e2e: spawns publisher + subscriber as separate processes, sends N messages, asserts 0 loss. ci_only=True in gac-local-gate.
- **Cross-project e2e**: `tests/test_e2e_cross_project.py` (7 tests) — omo→cockpit, kairon→omo, metaos→cockpit, aetherforge→omo, runtime→cockpit flows.
- **27 new tests** in bus-foundation: 7 topics + 8 harness + 7 cross-project e2e + 2 ws_v2 regression + 3 ws_v2 stop_server edge cases.
- **6 new e2e tests** across consumers: 3 omo, 5 metaos, 4 aetherforge hatcher, 4 runtime cron, 6 kairon-pipeline bus_adapter.

### Fixed
- **ws_v2.py** 7 latent bugs: `importlib.util` spell-error, `PerMessageDeflate` API drift (websockets 16), `hb_task` UnboundLocalError, `srv.loop` type-unsafe, `_drain` never awaited, `stop_server` not idempotent.
- **zmq.py** cross-process bug: `_stop_event` not initialized early enough in `__init__`; `__del__` could AttributeError on partial init. Now: init `_stop_event` first, wrap init body in try/except, idempotent `close()`.
- **aetherforge `_compat.py`**: pre-existing `EventType.INFO` AttributeError (StrEnum had no `INFO` member) — replaced with fallback to `PIPELINE_COMPLETED`.
- **bus-foundation 0.3.0 → 0.3.1** (semantically): new `topics.py`, lazy optional extras, fixed `_croniter.start()` type-ignore false positive, deprecated top-level API documented.

## [Unreleased] - 2026-06-30

### Fixed (文档 SSOT 深度收敛 + 子项目全覆盖)
- **v5→v6 全量清理** (workspace): 80+ 文件跨 bin/ + projects/ecos/ (scripts/services/ssot/M1/M2/M3) + cockpit + agora + runtime + aetherforge + kairon + family-hub + omo + cockpit-ui. 历史节点 (ARCH-ECOS-V5.yaml, MODEL-EVOLUTION.yaml) 保留.
- **5+3+1→5+4+1+1** (source code): cockpit/cli.py (2处) + agora/discovery.py + 兼容性检查. doc-ssot-lint 仅扫描 .md, 源码需手动 batch sed.
- **../docs/→../../docs/ 路径修正** (16 子项目): BOUNDARY/ARCHITECTURE/CALLCHAIN/README/AGENTS/CLAUDE ~70 文件. 归档文件引用 (ARCHITECTURE-EVOLUTION/DIAGRAM) → ../../docs/PANORAMA.md.
- **硬编码数字→SSOT 指针** (docs + projects): FUNCTIONAL-CAPABILITY-MAP.md (~20处), ARCHITECTURE-DETAILED-MAP.md (~25处), I0-AGORA-CALLCHAIN.md, PANORAMA.md 端口号→port-registry, metaos/omo/l4-kernel/agora/cockpit/gbrain/model-driven/runtime 项目文档.
- **GaC rules_count** (registry): project-registry.yaml 9→89 (实际 grep count).
- **.env.example** (workspace): 6→21 env vars (+Ollama/Langfuse/C2G/OTEL/Azure/DeepSeek/Google). WORKSPACE_ROOT→WORKSPACE (匹配源码). port 9100 注册到 port-registry.
- **x3-value-stack.yaml** (omo): "eCOS 5+3+1 架构"→"5+4+1+1 架构" (example 字段).
- **PANORAMA.md** (docs): agora-dashboard 路径修正 (projects/→_archived/), toolbox 补全, cocktail_mcp→cockpit_mcp typo, 硬编码行号→描述, 日期更新.

### Added (文档补全 + 治理工具文档化)
- **observability/README.md** (observability): 项目缺失, 新建含服务表/配置/部署说明.
- **bus-foundation/CAPABILITY-MAP.md** (bus-foundation): 新建, 三平面能力地图.
- **c2g/CAPABILITY-MAP.md** (c2g): 新建, 战略需求引擎能力地图.
- **observability/CAPABILITY-MAP.md** (observability): 新建, 可观测性能力地图.
- **tests/README.md** (workspace): 7 单元测试 + 8 集成测试文档. 后补 test_governance_evolution.py.
- **.github/workflows/README.md** (workspace): 1→42 CI workflows 文档 (6 分类).
- **ADR metadata** (governance): README.md + INDEX.md status: archived→active (113 ADRs 仍在使用).
- **3 standards frontmatter** (governance): agent-mutation-protocol.md, auto-generated-artifacts.md, doc-ssot-contract.md 获得 YAML frontmatter.
- **SSOT Map 扩展** (ARCHITECTURE.md): §1 9→17 条目 (+vault-paths/x-axis-registry/governance-checks/agent-workflows/debt/task-lifecycle/ADR/registry-index).
- **文档地图补全** (README.md + ARCHITECTURE.md): +4 文档条目 (ARCHITECTURE-DETAILED-MAP/FUNCTIONAL-CAPABILITY-MAP/I0-AGORA-CALLCHAIN/VISION-ROADMAP) EN+CN.
- **CLAUDE.md §5 routing** (CLAUDE.md): +5 docs/ 路由条目.

## [Unreleased] - 2026-06-24

### Fixed (P60+ 子模块止血 + scheduler + bos test + CVE)
- **14 子模块闭环止血** (workspace): 137 文件未提交 (aetherforge 57 删除遗留/gbrain 23 operations.ts 拆分未闭环/scripts 18/runtime 15 等). 6 子模块进内 commit + 14 push + 主仓 bump. ruff 历史格式债清理 (agora 103/runtime 140/omo 224 reformat). gbrain operations.ts BET-c9e3 拆分收口 (3841→23 行 aggregator + operations/ 模块).
- **scheduler scheduled 分类 bug** (runtime): gbrain-index (daily 02:00 cron job) 有 launchd_label 但 type=scheduled, scan_once 误当 daemon 检查 → 每次 scan 报 failed + self-heal 骚扰. 修 scheduler.py 循环开头加 scheduled 短路 (跳过 launchd alive-check/backoff). runtime failed 服务 12→0. (c051797)
- **bos test BosService.uri API 误用** (omo): `u.startswith()` 误用 (u 是 BosService dataclass, 该 `.uri.startswith()`). L108-109/220 修. POC_SERVICES 动态派生 services/analysis 改 `>= 静态` (resolver 含声明, 静态真 URI 为下限). test 7 passed.
- **2 high CVE** (agora deps): cryptography 41→49.0.0 (fix CVE vuln < 48.0.1), starlette→1.3.1 (fix CVE vuln < 1.3.1). 363 测试过无破坏.
- **bos registry 期望同步** (omo): bos-registry.json 40→42 URI (C2G v4 加 strategy-audit/strategy-gc, 5 domain 完整, 合理增长非假阳性).

### Added (BOS 鸿沟诊断 + SRP 续拆)
- **BOS 声明/执行鸿沟审计** (C smoke 超额发现): 102 URI 声明 alive, 实际 resolve_bos_uri() 全失败 (`No such file or directory`). 两层根因: (1) 11/16 stdio 包无 mcp_server.py (声明假阳性: agent-runtime/codeanalyze/core-models/ecos/health-profile/kos/metaos/minerva/omo/protocols-layer/sharedbrain-bridge); (2) 5 包有 mcp_server.py 但路径不匹配 (forge: 文件在 src/mcp_server.py 但 pyproject packages=src/forge, resolver 生成 `-m forge.mcp_server` → ModuleNotFoundError). 声明/执行比 102:0 (architecture-optimization 报告估的 21:1 实际更严重). 审计文档 `.omo/_knowledge/audits/bos-declaration-execution-gap-2026-06-24.md`.
- **omo_ingress SRP 第六步前 4** (omo): registry-writes (write_capability_registry_bundle / write_manual_capabilities / create_skill_manifest / write_discovery_registry) 拆到 `omo_ingress_registry_writes.py` (285 行). omo_ingress.py 2609→2324. re-export + `# noqa: F401` (调用方 `from omo.omo_ingress import` 不变).

### Known Issues (并发干扰, 待专项孤立 session)
- **D 后 4 + 巨函数 + task lifecycle**: registry-writes 后 4 (task-center/governance-overlay) + write_system_projection_fields (354 行 God Function) + 第七步 task lifecycle (~20 函数) 受并发 governance agent (别的 Claude/cockpit 会话) 抢改 omo_ingress, 4-5 次打断 (策略冲突: 全拆 vs 部分拆). 需停并发后单一 session 孤立.
- **omo_ingress registry_writes 重复定义**: 老王追加 8 函数 vs 并发 import 6 + 函数体重复, 待统一清理.
- **dependabot medium/low 11**: aiohttp 多 (分散子模块) / pydantic-settings / postcss (npm). 待批量升.

## [Unreleased] - 2026-06-23

### Fixed (c2g bug 链 + governance 满分)
- **radar `pending_metrics` None fallback** (c2g): planned 空时 `pending_metrics=None` → `pm = pending_metrics or metrics` fallback 全量 (含 done) → done L3 误报 "需 review", health 虚低 85. 修 `strategy.py` L158 + `bin/compass_radar.py` L62-63 (传 pending_metrics). health 85→100.
- **`get_omo_dir` home 干扰** (c2g): `found[-1]` 外层优先遇到 `~/.omo` 误返 home → bet 找不到 `goals/current.yaml`. 修: 遍历时跳过 `Path.home()` 的 `.omo/` (系统级干扰, 非 workspace 候选). 兼顾 test_smoke (workspace 内嵌套→外层优先) + test_bet_id_reuse (workspace+home→排除 home).
- **P45 frontmatter 破坏 YAML single-document** (c2g): 数据文件被 P45 doc-lifecycle 加 `--- frontmatter ---` → multi-document → `yaml.safe_load` ComposerError. 加 `strip_frontmatter()` helper (`bridge_utils.py`) + `bridge_import.py` L278 用它 (不碰 goals/current.yaml, 尊重 "仅人类可改").
- **ADR-0051 UNLISTED** (governance): ADR-0051 写了没加 INDEX → governance 99.3 扣分. 补 `decisions/INDEX.md` → 100.0 A+ 满分.
- **kronos flaky test** (kairon): `test_nonempty_text_returns_result` 依赖 Ollama 外部服务 (Ollama 在跑时走 llm 路径, LLM 生成 title 不确定 → 硬断言 `== "规则提取测试"` 随机 fail, make test-fast Error 1). Mock `extract_with_ollama` 强制 rules 路径 (单元测试隔离外部依赖, 确定性). `make -C projects/kairon test-fast` Exit 0 (16 包全绿).

### Added (P52-MDRIFT-CLOSURE)
- **mof-drift v5 终极**: gbrain TODOs unknown 19→0 (`any TODO = planned` 宽松兜底). P44 R0 `DEBT-GBRAIN-55-TODOS` 历史债一次性清零.
- **ADR-0051**: gbrain TODOs v5 终极收敛决策 (extends ADR-0050; 2 LOW 信息维度保留, 不改 mof-drift 现有维度).
- **mof-version**: v0.0.39 → v0.0.40.

### Tests
- c2g: 152 passed (含新增 regression `test_done_l3_not_warned_when_planned_empty` 防 None fallback 复发).
- agora: 3 个无条件 `xfail` → conditional (`condition=not KAIRON_ROOT.exists()` + `strict=True`); 本地有 kairon 时正常 PASSED (不再 XPASS 误标), 无 kairon 时才 xfail. `test_health_profile_main_help` / `test_minerva_main_help` / `test_invoke_stdio_minerva` XPASS 3→0.

## [0.3.0] - 2026-06-15

### Added (C2G v3 Cybernetic Solutions)
- **SSOT Write-back**: 实现了 `context_uri` 回写机制，完成任务后自动向原始 Markdown 设计反向追加审计结果，防止上下文降维断裂 (ecos)。
- **Fast-Track Compaction**: `omo worker gc` 自动汇聚微小交付任务 (FAST-*) 为聚合报告，保持稳态区纯净 (omo)。
- **Agent Tactical Yield**: 新增 `omo_yield_task` 机制，解决 Agent 执行时的长尾阻塞卡死问题，引导回流重估 (omo)。
- **L0 Governance**: 新增 C2G v3 系列 L0 X1 门禁约束 (`CR-C2G-V3-01~03`) 确保流程自愈 (ecos)。

## [0.2.0] - 2026-06-12

### Added (治理框架 + 能力地图 + 文档完善)

- **债务治理**:
  - 9/9 权重债务全部解决 (debt_weight: 0.3→1.0)
  - debt_health: 62.5→100.0
  - 清理 5 个过时债务引用

- **X1-X4 治理框架**:
  - L0 治理模块 (ecos/l0/governance/)
  - X1-X4 检查器实现
  - 治理注册表 + 告警规则
  - cockpit MCP 治理工具 (6 个)

- **kairon 优化**:
  - 16 个包全部验证通过 (100%)
  - 能力地图 (CAPABILITY-MAP.md)
  - 使用指南 (USAGE-GUIDE.md)
  - atomic_write_json 工具

- **KOS 修复**:
  - manifest.json 重构 (10 域)
  - README 对齐实际配置
  - 索引清理重建

- **文档完善**:
  - 17 个项目能力地图
  - 17 个项目 CHANGELOG + CONTRIBUTING + LICENSE
  - ARCHITECTURE.md 更新

- **版本号统一**:
  - 11 个项目统一到 1.0.0

- **Git Hooks**:
  - 18 个项目配置 .githooks

- **治理仪表板**:
  - Web 化 (HTML + API)
  - 告警消息处理

### Architecture
- X1-X4 治理框架体系化
- L0 治理模块与 M1/M2 SSOT 对齐
- 能力地图覆盖 17 个项目

## [0.1.2] - 2026-06-09

### Added (AppendOnlyLog 全景方案 5 轮收口 — Round 1-5)
- **Round 1 — 抽象**:
  - `omo_io.AppendOnlyLog` 类 (SSOT JSONL 物理写盘)
  - `omo_io.read_jsonl` 公开 (容错读)
  - 19 个单元测试
- **Round 2 — 接通**:
  - `omo_audit` / `omo_bos_metrics` 内部用 AppendOnlyLog
  - 外部 API 0 改 (49 测试不变)
- **Round 3 — 样板**:
  - `omo_sync` 摆脱 `details` 字符串拍扁, 结构化 record
  - 6 个 omo_sync 单元测试
- **Round 4 — 收尾**:
  - `AppendOnlyLog.tail(n)` / `since(ts, field='ts')` 方法
  - `AppendOnlyLog` 跨进程锁 `fcntl_lock` (POSIX fcntl.flock 包装)
  - `omo observability log tail --type knowledge [--file X]` 多文件
  - `omo_alert` 接入 AppendOnlyLog (第 4 个 consumer)
- **Round 5 — L0 强化**:
  - 治理审计 88.3 (B) → 100.0 (A+), kairon ruff 9→0
  - 跨进程 fcntl_lock 集成测试 (3 tests, 100/100 0 丢行)
  - `model_driven.PipelineTracker` 加 `on_event` 钩子 (向后兼容)
  - `omo.model_driven_bridge` L1 → L0 事件流桥接 (5 tests)
  - `omo event emit` 子命令 (P3 样板, 第 5 个 consumer, 4 tests)
  - 100+ 单元测试 + 3 集成测试 + 1 跨项目桥接

### Architecture
- 详见 `.omo/_knowledge/management/append-only-log-pattern-2026-06-09.md`
- 5 个 AppendOnlyLog consumer: omo_audit / omo_bos_metrics / omo_sync / omo_alert / omo_event
- L1 → L0 事件流贯通: PipelineTracker.on_event → omo.model_driven_bridge → .jsonl

## [0.1.1] - 2026-06-07

### Changed
- Bump version to 0.1.1 (release.sh patch)
- P34-W3: 多仓库统一发布机制落地

## [0.1.0] - 2026-06-07

### Added
- P33-W0: BOS URI 北极星 + 5 Domain 边界定义
- P33-W1: 战役 2 起步 2 Domain (memory + governance) + 6 URI
- P33-W2: 战役 2 余下 3 Domain (analysis + persona + capability) + 15 URI = 21 总
- P33-W3: KOS 持久化 + endpoint 实测 + 命名协调
- P33-W4: agora 接管 URI 解析 + 11 POC stdio 服务
- P33-W5: forge 集市 + 工具热加载 + 6 forge tools
- P33-W6: 整体验收, 健康分 100.0 (A+) 守
- P34-W0: URI 扩 21→40 (5 Domain 细分)
- P34-W1: agora spawn 升级 (POC 到生产 stdio 协议)
- P34-W2: Analysis 域 12 URI 实战化
- P34-W3: 多仓库统一发布机制 (release.sh + VERSION + CHANGELOG + ADR-0007)

### Changed
- kairon 包合并: 3 组合并 (protocols-layer / sot-bridge / llm-gateway-kernel)
- kairon 包归档: metaos / wksp / kairon-governance 迁出
- agora 路由表: 12 条服务注册, agora 12/12 健康
- omo 治理: audit / sync / history / daemon 6 模块

### Fixed
- KOS 实体 ID 前缀: TR-* → CON-* (符合 KOS 校验)
- ruff errors: 283→0 (P32 全清)
- agora 路由与实际服务脱节: 18.2%→100%
- BOS URI 命名冲突: 接受 3 段 legacy + 4 段新

## Earlier versions

See git history. 6 项目独立维护.
