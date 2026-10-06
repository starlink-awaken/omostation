---
schema_version: specification/v1
spec_version: 1.0.0
title: KOS/MOS P0 四项修复 — SQL 授权器、CJK 意图路由、默认后端真值、FTS body 分词
bet_id: BET-Y2Q4-T3-04
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-06
---

# KOS/MOS P0 四项修复 (specification/v1)

本 spec 承载一个跨双仓的 P0 修复 campaign，覆盖 `bin/gac/mcp-server-kos.py`（父仓）
与 `projects/knowledge/kairon/packages/{kos,mos}/`（kairon 子模块）。
四项目标证据均在 2026-10-06 于 worktree `ws-kos-mos-p0`（root `2ae225751`，
kairon 子模块 `915fc76`）实读确认。

> 交付边界：kairon 内改动必须在子模块内提交并单独 bump 父仓 gitlink；
> 本 spec 不把两仓混作一次提交。

---

## Item 1 — `query_custom_sql` 用子串黑名单拒绝合法读 (P0)

**证据（实读，2026-10-06）：**
- `bin/gac/mcp-server-kos.py:216-237` — `handle_query_custom_sql` 用
  `forbidden_keywords = {"insert","update","delete","drop","alter","create","replace","vacuum"}`
  对 `sql.lower()` 做**子串**匹配；任何含 `create` 的合法读（如
  `SELECT created_at FROM documents`）被误拒为 `Security violation`。
- `bin/gac/mcp-server-kos.py:26-64` — 已存在真正的授权器 `_authorizer`，
  由 `conn.set_authorizer(_authorizer)`（`:64`）在 `get_db_connection()` 内挂载，
  按 SQLite action code（INSERT=18/UPDATE=23/DELETE=9/ATTACH=24/DETACH=25）拒写，
  并限定 read-only PRAGMA 与敏感函数。

**修复方向：** 删除子串黑名单（`:216-237` 的 `forbidden_keywords` 循环），
以 `get_db_connection()` 内已有的 `sqlite3` authorizer 作为唯一守卫。

**验收标准：**
- `SELECT created_at FROM documents` 不再被判写操作，能正常返回（或返回数据库层结果）。
- `INSERT` / `UPDATE` / `DELETE` / `DROP` / `ALTER` / `CREATE TABLE` 等写语句仍被拒
  （由 authorizer 阻断，报错语义清晰）。
- 无新增依赖、无新增文件；未删除 authorizer。

---

## Item 2 — MOS 意图路由 CJK 分支不可达 (P0)

**证据（实读，2026-10-06）：**
- `projects/knowledge/kairon/packages/mos/src/mos/routing.py:32-40` —
  `_CODE_RE` / `_PREF_RE` / `_ENTITY_RE` / `_TASK_RE` / `_CARD_RE` / `_FILE_RE`
  各自把**整个 alternation**（含 CJK 分支）包进 `\b(...)\b`。
  `str` pattern 的 `\w` 是 Unicode 感知、包含 CJK，所以 CJK 串内部处处是词字符，
  `\b文档\b` 因 `文档路径` 中 `文档` 两侧无边界而不成立 → 六条 CJK 分支全部不可达。
- `projects/knowledge/kairon/packages/mos/src/mos/routing.py:41` — 注释已写明规则
  「avoid `\b` for CJK tokens」，但只有 `_TEMPORAL_RE`（`:42-45`）遵守。
- pin 测试 `projects/knowledge/kairon/packages/mos/tests/test_routing_matrix.py:756-792`
  当前**断言该缺陷仍活**（`test_cjk_word_boundary_defect_is_pinned`）。
  该文件在 canonical 工作树 **未跟踪**（`git status` 显示 `??`），
  在 worktree 子模块检出中**不存在**，须在本次修复中重新落地为受版本控制的测试。

**修复方向：** 把六条 pattern 中 CJK 分支移出 `\b` 断言（只对 ASCII 分支保留词边界），
使 `\b文档\b` 这类失效断言变为可达；同步把 pin 测试改写为「修复后必须通过」的真测试。

**验收标准：**
- 六条意图各对一句代表性中文自然语句分类正确（`code_structure` / `task_debt` /
  `preference_self` / `entity_relation` / `card_ops` / `file_note`），使用完整问句而非裸关键词。
- 六条 ASCII 形式分类不变（含 `\b` 语义：`taskforce` / `recard` / `vaulted` 等更长词仍不匹配）。
- 新测试在修复前代码上**先失败**（防空绿），修复后通过。
- 干净环境（`MOS_LIVE_GBRAIN` 未设置）全量 MOS 套件绿。

---

## Item 3 — 生产后端默认关闭，默认 recall 返回 fixture/stub (P0)

**证据（实读，2026-10-06）：**
- `projects/knowledge/kairon/packages/mos/src/mos/adapters/live_backends.py:28-38` —
  `_flag(name, default="0")` 默认值是 `"0"`：`live_kos_enabled()`（`MOS_LIVE_KOS`）与
  `live_gbrain_enabled()`（`MOS_LIVE_GBRAIN`）**默认关闭**。
- `projects/knowledge/kairon/packages/mos/src/mos/service.py:155-177` —
  构造函数在无注入时装配内存/fixture 后端（`InMemoryRawBackend` / `InMemoryThetaBackend` /
  `Mem0ShadowAdapter` …），并把 `neo4j` 搜索后端挂在 `NEO4J_URI` 门（未设则空命中）。
- `.omo/_truth/registry/memory-os.yaml:19-26,54-55,153,197,311` —
  `env_defaults` / 状态表把 live 后端标注为 `MOS_LIVE_KOS=1`、`MOS_LIVE_GBRAIN=1`、
  `NEO4J_URI`-gated；即「生产后端默认 OFF」是**声明层面**的事实。

**修复方向（二选一，须在 spec 中固定）：**
（A）默认启用真实后端（改 `_flag` 默认值 / `service.py` 装配），或
（B）保持默认 OFF，但把「当前处于 fixture 模式」在 `status` / recall 输出中**显式可见**。
无论选哪条，默认 recall 都不得再静默返回 fixture/stub 数据而不加标注。

**验收标准：**
- 默认（无 live 环境变量）调用 recall：结果携带明确的 fixture/stub 标识，
  或真实后端被启用且非 stub 数据。
- `memory-os.yaml` 的 `env_defaults` 与代码实际默认值一致（消除声明≠事实）。
- 相关测试覆盖默认路径与 live 路径两种模式。

---

## Item 4 — `documents_fts` 的 body 未分词 (P0)

**证据（实读，2026-10-06）：**
- `projects/knowledge/kairon/packages/kos/src/kos/indexer/engine.py:714` —
  `cursor.execute(fts_sql, (d["doc_id"], _tokenize_cn(d["title"]), d["body"], "", d["canonical_path"]))`
  —— **title 走 `_tokenize_cn`，body 直接写原文**。
- `projects/knowledge/kairon/packages/kos/src/kos/tokenize.py:8` — 明文不变量：
  「任何写 `documents_fts` 的地方都用 `fts_text()`，任何 `MATCH` 的参数都用 `fts_query()`」。
  `fts_text()`（`:48-50`）= `tokenize_cn()`。
- `projects/knowledge/kairon/packages/kos/src/kos/tokenize.py:43-44` —
  `tokenize_cn` 在 `jieba` 不可用时 `return text`（原文），**静默**；调用方无法区分
  「已分词」与「jieba 缺失退化为原文」，正是 FAIL-20260513-005 的失败模式。

**修复方向：** 先**穷举全部写 `documents_fts` 的路径**（不止 `engine.py:714`；
须 grep 所有 `documents_fts` 写入点并逐一核对），把 body 也接入 `fts_text()`；
让 jieba 缺失退化为原文这件事**可观测**（记录/警告/暴露标志），而非静默。

**验收标准：**
- 所有写 `documents_fts` 的路径统一经 `fts_text()`（title 与 body 一致）；
  逐路径点名核对，不得假设只有一处。
- jieba 缺失导致的原文退化在运行时可观测（日志/状态标志/测试断言其一），不再静默。
- FTS 写入/查询分词一致性测试通过（中文关键词召回不再依赖调用方遗漏）。

---

## 交付与边界

- 四项均为 P0，属同一 campaign；`bet-execution` 从本 BET 的 `write_surfaces` 取写面，
  可同时覆盖父仓与 kairon 路径。
- **子模块交付**：`packages/{kos,mos}/**` 改动在 `projects/knowledge/kairon` 内提交，
  再单独 bump 父仓 gitlink；`bin/gac/mcp-server-kos.py` 与 `.omo/_truth/registry/memory-os.yaml`
  属父仓，正常提交。
- 既有任务记录 `.omo/tasks/active/BET-Y2Q4-T10-CJK-ROUTING.yaml`（item 2，pending，
  无 spec binding）**reconcile 进本 BET**，不作为独立可启动单。
- 本 spec 不授权：重排 `classify_intent` 检查顺序（另见
  `BET-Y2Q4-T10-TEMPORAL-PRECEDENCE`）、增删既有路由关键字、扩展路由表。
