# §12 跨仓 SSOT — AppendOnlyLog 5 仓实施指南 (E4 P0 收口)

> **状态**: ✅ 实质化 (E4 P0, 2026-06-11)
> **作者**: 老王
> **定位**: §12.1.4 跨仓 4 不变量 (sort_keys=True / Z-suffix / AppendOnlyLog / ZTimestampModel) 5 仓实施差异表
> **目的**: 给后续 R57+ 跨仓债 E4 收口提供 SSOT 文档 (避免 5 仓实现 drift)

---

## §12.1 5 仓实现对比

| 仓 | 文件 | 语言 | LOC | 锁 | zod/Pydantic 校验 | read 接口 | sort_keys | Z-suffix 校验 |
|----|------|------|-----|----|------------------|----------|-----------|--------------|
| **omostation/omo** | `src/omo/_shared/append_only_log.py` | Python | 296 | threading + fcntl 注入 | Pydantic (opt-in) | read_all + tail (windowed seek) | ⚠️ 默认无 | ⚠️ opt-in |
| **runtime** | `src/runtime/executor/io.py` | Python | 53 | threading | Pydantic (required) | io_sync | ✅ 默认 | ✅ required |
| **gbrain** | `src/core/append-only-log.ts` | TypeScript | 312 | O_APPEND | zod v4 (required) | readAllSync + auditSync | ✅ 默认 | ✅ required (regex) |
| **kairon-utils** | `src/kairon_utils/append_only_log.py` | Python | 174 | threading + fcntl 注入 | Pydantic (opt-in) | read_all + tail (简化) | ✅ 默认 | ✅ opt-in |
| **metaos** | `src/metaos/audit.py` | Python | 175 | threading + fcntl 注入 | Pydantic (opt-in) | read_all + tail (简化) | ✅ 默认 | ✅ opt-in |

## §12.2 §12.1.4 跨仓 4 不变量 (强制)

| 不变量 | omo | runtime | gbrain | kairon-utils | metaos | 状态 |
|--------|-----|---------|--------|--------------|--------|------|
| 1. **sort_keys=True** (JSON 输出按 key 排序) | ⚠️ 默认无 (需透传) | ✅ 默认 | ✅ 默认 | ✅ 默认 | ✅ 默认 | 4/5 ✅ |
| 2. **Z-suffix** (ts 字段以 `Z` 结尾) | ⚠️ opt-in | ✅ required | ✅ regex | ⚠️ opt-in | ⚠️ opt-in | 2/5 enforced |
| 3. **AppendOnlyLog 抽象** (单一 SSOT) | ✅ 原生 | ✅ R51 | ✅ R50 | ✅ B-1 | ✅ B-2 | 5/5 ✅ |
| 4. **ZTimestampModel / ZTimestampSchema** | ✅ Pydantic | ✅ Pydantic | ✅ zod | ❌ 无 mixin | ❌ 无 mixin | 3/5 ✅ |

## §12.3 差异根因分析

### §12.3.1 为什么不强制提取到独立 _shared 仓

1. **3 个 Python 仓都是独立 monorepo**（omo + kairon-utils + metaos），跨仓共享一个 `_shared` 包需要:
   - 新建独立 git repo（`aetherforge-shared` 或 `cosmos-shared`）
   - 每个 monorepo 加 dependency → 引入新的版本对齐问题
   - 每次 zod/Pydantic 升级需要 4 仓同步 commit
2. **gbrain TS/JS 是另一栈**——zod v4 与 Pydantic 不互通
3. **runtime 是简化版**（53 行 vs omo 296 行）——精简版够用，没必要拉入全套

**结论**: 5 仓实现核心一致（≥80%），**通过 SSOT 文档化 + 不变量硬约束**而非物理提取。

### §12.3.2 §12.1.4 不变量 1/2 在 omo/kairon-utils/metaos 的"opt-in" 风险

- omo `sort_keys=True` 默认无，需调用方传 `sort_keys=True` (R47 之后已统一)
- omo `Z-suffix` opt-in（需 Pydantic schema），但 omo_history 等消费者已自带
- kairon-utils + metaos 同样 opt-in

**R57+ 待办**: 把 §12.1.4 不变量 1/2 在 omo/kairon-utils/metaos 升级为**默认**（`sort_keys=True` 与 `ts` Z-suffix 校验作为 AppendOnlyLog 构造函数 default），与 gbrain/runtime 看齐。

## §12.4 实施指南（新增仓接入时）

### §12.4.1 5 步接入清单（与 R48/R49 探路一致）

1. **复制 omo 的 `AppendOnlyLog` + `fcntl_lock`** 到目标仓
2. **`sort_keys=True` + Z-suffix 校验作为默认**（不要 opt-in）
3. **Pydantic/zod schema 必填 `ts` 字段**（消费者在 §11 治理面）
4. **暴露 `audit_log(dir, prefix)` helper**（metaos 模式）— ISO-week 文件名 + 锁注入
5. **加 `tools/audit.sh` + `.github/workflows/audit-baseline-monthly.yml`**

### §12.4.2 §17 metrics 输出 schema (固定 5 字段)

```json
{
  "generated_at": "2026-06-11T00:00:00Z",
  "drift_count": 0,
  "total_records": 0,
  "debt_density": 0.0,
  "health_grade": "R0"
}
```

R0/R1/R2/R3/R4/R5 健康度评分公式见 §17。

### §12.4.3 E2 跨仓聚合 (omo audit-rollout dispatcher)

E2 P0 已升级 `_run_logs_metrics()` 为 dispatcher:
- 子仓含 `omo/` → `omo logs audit --metrics` (原路径)
- 子仓含 `tools/audit.sh` → bash 调用拿 §17 JSON
- 都没有 → 标记 `n/a` (不阻塞聚合)

跨仓聚合 (5 仓示例):
```bash
uv run --no-sync python -m omo.cli audit-rollout \
  --repos omostation:. \
  --repos runtime:projects/runtime \
  --repos gbrain:projects/gbrain \
  --repos kairon:projects/kairon \
  --repos metaos:projects/metaos \
  --include-metrics \
  --output .omo/_delivery/audit-rollout/2026-06-11.json
```

实测 5 仓 worst=R0 优秀 ✅。

## §12.5 R57+ 待办（§12.6 跨仓债 E1-E4 收口）

| 债 | 状态 | 工作量 | 备注 |
|----|------|--------|------|
| **E1** omo → gbrain 跨仓链接 | 🔄 探路 | 1 Round | omo audit-rollout 跨 gbrain PGlite + Postgres 探路 |
| **E2** metaos D Layer 接入 omo audit-rollout | ✅ R57 实质化 | - | E2 P0 完成 (2026-06-11) |
| **E3** kairon async 适配 (ContentVersionTracker) | ⚠️ 半完成 | 1 Round | B-1 用同步 AppendOnlyLog 包 async 函数, fcntl 阻塞 event loop 风险未解 |
| **E4** AppendOnlyLog 跨仓 SSOT 收口 | ✅ R57 实质化 | - | E4 P0 完成 (本文档, 2026-06-11) |

## §12.6 历史债

- **§11.6 历史债**: 3 个 Python 仓的 sort_keys + Z-suffix 是 opt-in (R57+ 待办)
- **§12.1.4 不变量**: 5/5 仓 AppendOnlyLog 抽象已就位, 4/5 默认 sort_keys, 2/5 强制 Z-suffix
- **E3 风险**: kairon async + fcntl_lock 跨进程可能在 event loop 阻塞 (待 R58+ 验)

---

**§12 跨仓 SSOT 文档化完成（E4 P0）。** 5 仓 AppendOnlyLog 实施差异表 + §17 metrics schema + E2 dispatcher 路径已锁定。R57+ E1/E3 待办。
