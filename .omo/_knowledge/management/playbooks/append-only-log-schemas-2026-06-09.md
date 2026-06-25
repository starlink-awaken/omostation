---
category: playbooks
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: append-only-log-schemas-2026-06-09.md
deprecated-since: 2026-06-23

---

# AppendOnlyLog 6 个 Consumer Schema SSOT (Round 8 P2) — 2026-06-09

> **状态**: implemented (schema doc + 自动校验测试)
> **目的**: 锁住 6 个 consumer 的 record 形状, 防 schema 漂移 (Round 4 教训: omo_sync.details 字符串拍扁)
> **属性**: 历史 schema 治理记录 / reference only。本文保留当轮 consumer 设计与示例，不是当前运行频率、当前治理健康分或当前所有 consumer 实装真相 SSOT。

---

## §0 设计原则

- 字段含义 = 显式 SSOT (本文)
- 字段类型 = 显式 SSOT (本文)
- 字段缺失容错 = 缺则 "raw" 入 (AppendOnlyLog 默认行为)
- 字段漂移 = 立即报错 (CI lint 锁)

---

## §1 6 个 Consumer 总览

| # | 模块 | 落点 | record 形状 (核心字段) | 写入频率 |
|---|------|------|---------------------|----------|
| 1 | omo_audit | `~/runtime/audit/governance-audit.jsonl` | `{ts, action, debt_id, actor, details}` | 治理事件 (低频) |
| 2 | omo_bos_metrics | `.omo/_knowledge/bos-metrics.jsonl` | `{uri, status, elapsed_ms, transport, error, recorded_at}` | 每次 BOS invoke (高频) |
| 3 | omo_sync | `.omo/_knowledge/omo-sync.jsonl` | `{ts, kind, phase, health_score, dry_run, audit_checks, status}` | 每次 sync (低频) |
| 4 | omo_alert | `.omo/_knowledge/omo-alerts.jsonl` | `{ts, kind, severity, message, blocked_rate, failed_rate, threshold}` | 每次 alert (中频) |
| 5 | omo_event | `.omo/_knowledge/omo-events.jsonl` | `{ts, kind, source, payload}` | 用户主动 emit (低频) |
| 6 | omo_history | `.omo/_knowledge/governance-history.jsonl` | `{date, timestamp, total_score, grade, watchlist_count, source}` | 每次 audit (中频) |

---

## §2 每个 Consumer 详细 Schema

### 2.1 omo_audit

```yaml
record:
  ts: string          # ISO8601 UTC, "Z" 结尾 (例: 2026-06-09T02:00:00Z)
  action: string      # 治理动作 (例: "omo_sync", "governance_audit")
  debt_id: string     # 关联债务 ID (例: "OMO-SYNC"); 可空字符串
  actor: string       # 操作者 (例: "omo-sync", "omo-governance-cli")
  details: string     # 自由文本, 不含结构化数据 (避免 Round 4 拍扁坑)
example: |
  {"ts": "2026-06-09T02:00:00Z", "action": "omo_sync", "debt_id": "OMO-SYNC", "actor": "omo-sync", "details": "phase=28 health=77.5 dry_run=False"}
```

### 2.2 omo_bos_metrics

```yaml
record:
  uri: string              # bos://<domain>/<package>/<action>
  status: enum              # resolved | agora_unavailable | invalid_uri | endpoint_missing | timeout | error
  elapsed_ms: float         # 调 invoke 耗时 (毫秒)
  transport: string         # internal | stdio | http | agora (可空)
  error: string             # 仅 status != resolved 时填, 截断 200 chars
  recorded_at: string       # ISO8601 UTC, "Z" 结尾
example: |
  {"uri": "bos://memory/kos/search", "status": "resolved", "elapsed_ms": 12.3, "transport": "stdio", "error": "", "recorded_at": "2026-06-09T02:00:00Z"}
```

### 2.3 omo_sync

```yaml
record:
  ts: string              # ISO8601 UTC, "Z" 结尾
  kind: string            # 固定 "omo_sync"
  phase: int              # 当前 phase (例: 28)
  health_score: float     # 审计健康分 (0-100)
  dry_run: bool           # 是否 dry_run
  audit_checks: int       # audit checks 总数 (当前 6)
  status: enum            # "ok" | "error" — 本次 sync 状态
  error: string           # 仅 status=error 时填, "ClassName: msg" 形式
example: |
  {"ts": "2026-06-09T02:00:00Z", "kind": "omo_sync", "phase": 28, "health_score": 77.5, "dry_run": false, "audit_checks": 6, "status": "ok"}
```

### 2.4 omo_alert

```yaml
record:
  ts: string              # ISO8601 UTC, "Z" 结尾
  kind: string            # 固定 "kei_threshold"
  severity: enum           # "high" | "medium" | "low" | "info"
  message: string         # 人类可读 alert 描述
  blocked_rate: int       # 当前 blocked/h 计数 (触发 alert 时记录)
  failed_rate: int        # 当前 failed/h 计数
  threshold: int          # 触发 alert 的阈值
example: |
  {"ts": "2026-06-09T02:00:00Z", "kind": "kei_threshold", "severity": "high", "message": "🔴 KEI blocked rate: 12/hour (threshold: 10)", "blocked_rate": 12, "failed_rate": 0, "threshold": 10}
```

### 2.5 omo_event

```yaml
record:
  ts: string              # ISO8601 UTC, "Z" 结尾
  kind: string            # 用户定义 (例: "my_event", "pipeline_done")
  source: string         # 事件来源 (例: "cli", "my_script", "omo_daemon")
  payload: string         # 自由 JSON 字符串, 业务方负责结构
example: |
  {"ts": "2026-06-09T02:00:00Z", "kind": "my_event", "source": "cli", "payload": "{\"k\": \"v\"}"}
```

### 2.6 omo_history

```yaml
record:
  date: string            # "YYYY-MM-DD" 形式 (UTC) — 必填
  timestamp: string       # ISO8601 UTC, "Z" 结尾 — 必填
  total_score: float      # 审计总分 (0-100) — 必填
  grade: string          # "A+" | "A" | "B" | "C" | "D" | "F" — 必填
  watchlist_count: int    # watchlist 项数 — 必填
  source: string         # 写入来源 (例: "omo_daemon", "omo-cli governance") — **OPTIONAL** (Round 8 P2 新加, 老记录无)
  # 用户业务字段: 任意 key, 写入时自动注入 date/timestamp 后排最前
example: |
  {"date": "2026-06-09", "timestamp": "2026-06-09T02:00:00Z", "total_score": 100.0, "grade": "A+", "watchlist_count": 0, "source": "omo_daemon", "checks": [...]}
```

---

## §3 通用约定 (所有 consumer 共享)

1. **时间戳字段**: `ts` (omo_audit/bos_metrics/sync/alert/event) 或 `recorded_at` (omo_bos_metrics) 或 `timestamp` (omo_history)
   - 格式: ISO8601 UTC, "Z" 结尾 (例: `2026-06-09T02:00:00Z`)
   - **无微秒**, `_utc_now()` 自动 strip microsecond + 加 "Z"
2. **缺失字段**: 必填字段缺失时, AppendOnlyLog 解析为 `{"raw": "..."}` 落 raw (容错, 不抛)
3. **多余字段**: 保留 (forward compat)
4. **JSON parse 错**: 落 `{"raw": "first 200 chars of line"}` (AppendOnlyLog 默认)

---

## §4 自动校验 (Round 8 P2 收尾)

`tests/test_append_only_log_schemas.py` 自动跑 6 个 schema 检查:
- 读所有 .omo/_knowledge/*.jsonl
- 对每个文件, 抽前 N 条 + 后 N 条
- 按本 SSOT 校验必填字段存在
- 失败时打印 schema mismatch 详情

未来 Round (P3+): 接入 Pydantic 模型 + 写时校验, schema 漂移立即 fail-fast.

---

## §5 Schema 漂移检测 (设计)

3 层防御:
- **本 SSOT 文档**: 字段含义 + 类型 + 示例
- **测试 `test_append_only_log_schemas.py`**: 跑现有 log, 校验字段存在
- **未来 Pydantic**: 写时强校验 (Round 9+)

每加新 consumer / 改字段, 必须:
1. 更新本 SSOT
2. 更新 consumer 代码
3. 跑 schema 测试, 0 失败
4. (未来) Pydantic 模型加进 AppendOnlyLog.append
