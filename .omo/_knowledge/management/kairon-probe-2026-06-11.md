# R48 kairon 探路报告 (2026-06-11)

> 探查范围: `/Users/xiamingxing/Workspace/projects/kairon/`
> 探查人: worker-3

---

## 仓类型

**真仓** — 16 个 live installable Python packages 的 monorepo workspace，非 meta-stub。

证据:
- `pyproject.toml` 有完整 `[project]` 元信息 (name=kairon, version=0.1.1, requires-python>=3.13)
- `[tool.uv.workspace]` members = ["packages/*"]，16 个包通过 `uv sync` 可独立安装
- 包列表 (CLAUDE.md 记录): core-models, health-profile, kairon-lib-events, kairon-observability, kairon-pipeline, kairon-plugin-sdk, kairon-utils, codeanalyze, eidos, iris, kos, kronos, minerva, ontoderive, sophia, forge

---

## 现有 .jsonl 写调用

### 入口 #1: `eidos/adapters/eidos_to_bos.py:169`

```python
def _write_jsonl(self, record: dict[str, Any], filename: str) -> dict[str, Any]:
    file_path = SHAREDBRAIN_DATA_DIR / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"file": str(file_path), "record_id": record.get("task_id", "")}
```

- 调用方: `derivation_result_to_bos_loop()` (第 106 行) — 当 Agora MCP 不可达时 fallback
- 写文件: `{SHAREDBRAIN_DATA}/derivation_results.jsonl` (默认 `~/Workspace/projects/SharedBrain/data/derivation_results.jsonl`)
- 用途: kairon → SharedBrain 知识管道回写推导结果
- **无锁** — 简单 `open(..., "a")`，跨进程并发写会丢行

### 入口 #2: `kairon-utils/src/kairon_utils/versioning.py:161`

```python
async def _append_version_log(self, version: ContentVersion) -> None:
    version_file = self._get_version_file(version.source_id)
    try:
        with open(version_file, "a") as f:
            f.write(json.dumps(version.to_dict()) + "\n")
    except OSError as e:
        _log.error(f"Failed to write version log for {version.source_id}: {e}")
```

- 调用方: `record_version()` (第 93 行)
- 写文件: `{storage_dir}/{source_id}_versions.jsonl` (默认 `.omc/versioning/{source_id}_versions.jsonl`)
- 用途: 内容版本追踪 (ContentVersionTracker)，带 SHA256 hash + 版本链
- **无锁** — 同上，跨进程并发写存在丢行风险
- **async 函数** — 属于异步 API，与 omo AppendOnlyLog 的同步 API 不同

### 无其他 .jsonl 写入口

排除 `.venv/`、playwright driver 等外部依赖后，kairon 源码中仅上述两处 .jsonl 写操作。

---

## .omo/ 目录状态

**存在** — 完整 4-Plane 治理结构:

```
.omo/
├── INDEX.md
├── kairon-debt-registry.yaml
├── kairon-issue-ledger.md
├── _control/     (控制面)
├── _delivery/    (交付面)
├── _knowledge/   (知识面)
├── _registry/    (注册表)
├── _reports/     (报告)
├── _scripts/     (脚本)
├── _standards/   (标准)
├── _state/       (状态)
├── _tasks/       (任务)
└── _tests/       (测试)
```

但 **无 AppendOnlyLog 抽象**，无 `omo_io` 模块。

---

## AppendOnlyLog 等价物

**不存在** — kairon 无任何 `AppendOnlyLog` / `ZTimestampModel` / `append_only_log` 的等价抽象。

`versioning.py` 的 `ContentVersionTracker` 有部分重叠概念:
- 版本链 (previous_hash + SHA256)
- append-only 追加模式
- 读 tail / history

但缺少:
- **跨进程锁** (fcntl_lock)
- **ZTimestampModel mixin** (created_at/updated_at)
- **ts 字段** (所有 record 必须有 `ts` 字段用于 `since()` 查询)
- **SSOT 物理层抽象** (散在两个不同包各自实现)

---

## §12.2.3 5步接入清单

- [ ] Step 1: 在 `kairon-utils` 或新建 `kairon-io` 包内实现 `AppendOnlyLog` 抽象
  - 复制 omo 的 `omo/omo_io.py` 实现 (AppendOnlyLog + fcntl_lock)
  - 需处理 async/sync 差异 — kairon 的 versioning 是 async 的
- [ ] Step 2: 为 `ContentVersion` 和 `DerivationResult` 等数据类加 ZTimestampModel mixin
  - 增加 `created_at` / `updated_at` 字段
  - 统一 ts 字段格式 (ISO 8601 UTC)
- [ ] Step 3: 改造 `versioning.py` 的 `_append_version_log` 使用 `AppendOnlyLog` 替代 `open(file, "a")`
  - `ContentVersionTracker._get_version_file()` → `AppendOnlyLog(path).append()`
- [ ] Step 4: 改造 `eidos_to_bos.py` 的 `_write_jsonl` 使用 `AppendOnlyLog`
  - `EidosToBosAdapter._write_jsonl()` → `AppendOnlyLog(file_path).append()`
- [ ] Step 5: 在 `kairon/.omo/` 注册为 consumer，参考 omo 的 `omo_bos_metrics` 模式
  - 登记到 `.omo/registry/append-only-log-consumers.yaml`

---

## 接入工作量估算

**复杂**

原因:
1. kairon 的 `versioning.py` 是 **async 函数** (`async def _append_version_log`)，而 omo AppendOnlyLog 是同步 API，跨 async/sync 边界需要适配
2. 两个写入口分散在 `kairon-utils` 和 `eidos` 两个包，需要跨包协调
3. 需要新建 `kairon-io` 包或扩展 `kairon-utils` 作为 AppendOnlyLog 的宿主
4. 现有 `ContentVersion` 数据模型需要加 ts 字段才能被 `since()` 查询利用

---

## 备注

1. **优先级建议**: 接入收益中等 — 两处写入口都是 fallback 路径 (Agora MCP 可达时走 MCP)，真正高价值的日志路径反而有 MCP 层保护
2. **风险点**: kairon 的 versioning 使用 `storage_dir.glob("*_versions.jsonl")` 做统计，存在 glob 遗漏风险 (参考 omo 的 `tail(n)` 实现)
3. **可复用资产**: omo 的 `AppendOnlyLog` + `fcntl_lock` 实现可以直接复制到 kairon，无需重写
4. **版本链**: kairon 的 `previous_hash` 版本链设计比 omo 更完善 (SHA256)，可反过来贡献给 omo AppendOnlyLog 的改进
5. **探查边界**: 本次未深入 `minerva`/`kos` 包 — 它们可能有独立的持久化逻辑，待后续探查