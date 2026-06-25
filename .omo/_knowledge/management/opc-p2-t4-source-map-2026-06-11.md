---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# OPC-P2-T4 source-map 字段化

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P2 (Memory spine) T4 — source/timestamp/owner/freshness 字段化
> **目的**: 让 T3 output 每条结果都声明 4 字段, 满足 Gate C "outputs include source metadata"
> **链接**: OPC-P2-T3 recall-flow / T5 memory-metrics

---

## §1.0 一句话总结

**OPC-P2-T4 source-map 落地 4 字段 schema (source/timestamp/owner/freshness) + 5 边界映射表 + 验证正则 + 实施 3 阶段, 让 recall-flow 的每条 output 强制声明元数据。**

## §1.1 4 字段 schema (Pydantic + zod 双栈)

```python
# Pydantic schema (Python 仓)
class SourceMap(BaseModel):
    source: str           # bos:// URI 或本地路径
    timestamp: str        # ISO 8601 UTC, Z-suffix
    owner: str            # 仓名 + 责任人
    freshness: str        # 人类可读 "1d ago" / "3h ago" + ISO 双重表示
    boundary: str         # 5 边界之一: memory/ontology/work/asset/governance
    
    model_config = ConfigDict(
        json_schema_extra={
            "required": ["source", "timestamp", "owner", "freshness", "boundary"],
        }
    )
```

```typescript
// zod schema (TypeScript 仓, gbrain)
const SourceMapSchema = z.object({
  source: z.string().url(),
  timestamp: z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/),
  owner: z.string(),
  freshness: z.object({
    iso: z.string(),  // ISO 8601 duration
    human: z.string(), // "1d ago"
  }),
  boundary: z.enum(['memory', 'ontology', 'work', 'asset', 'governance']),
});
```

## §1.2 5 边界映射表

| 边界 | source 格式 | timestamp 来源 | owner 字段示例 |
|------|------------|----------------|----------------|
| **bos://memory/** | `bos://memory/{type}/{id}` | gbrain `pages.updated_at` | `gbrain:agent-A` |
| **bos://ontology/** | `bos://ontology/{type}/{id}` | kairon-KOS `nodes.created_at` | `kairon:@kairon-team` |
| **bos://work/** | `bos://work/{type}/{id}` | cockpit `contracts.modified_at` | `cockpit:@user-id` |
| **bos://asset/** | `bos://asset/{type}/{id}` | metaos `assets.timestamp` | `metaos:@owner-h-id` |
| **bos://governance/** | `bos://governance/{type}/{id}` | .omo `_state/system.yaml` | `omo:@owner` |

**注**: 实际实施时, 各 owner 仓的物理字段名不同, source-map 通过 URI namespace 反向解析映射。

## §1.3 freshness 计算规则

```python
def compute_freshness(timestamp_iso: str, now: datetime) -> dict:
    """计算 fresh/iso 双重表示."""
    ts = datetime.fromisoformat(timestamp_iso.replace('Z', '+00:00'))
    delta = now - ts
    
    iso = f"P{delta.days}DT{delta.seconds//3600}H{(delta.seconds%3600)//60}M{delta.seconds%60}S"
    # ISO 8601 duration
    
    if delta.days >= 30:
        human = f"{delta.days // 30}mo ago"
    elif delta.days >= 1:
        human = f"{delta.days}d ago"
    elif delta.seconds >= 3600:
        human = f"{delta.seconds // 3600}h ago"
    elif delta.seconds >= 60:
        human = f"{delta.seconds // 60}m ago"
    else:
        human = f"{delta.seconds}s ago"
    
    return {"iso": iso, "human": human}
```

**freshness 分级 (T5 度量用)**:
- 🟢 **fresh**: < 1d
- 🟡 **recent**: 1d-7d
- 🟠 **stale**: 7d-30d
- 🔴 **expired**: > 30d

## §1.4 验证正则 (linter 候选)

```python
SOURCEMAP_REGEX = re.compile(
    r'^{'
    r'"source":\s*"(?P<source>bos://[^/]+(/[^/]+)+|/[a-zA-Z][a-zA-Z0-9_/.-]+|@[^:]+:[^/]+(/[^/]+)?)",'
    r'"timestamp":\s*"(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z)",'
    r'"owner":\s*"(?P<owner>[a-zA-Z0-9_./@-]+(?::[a-zA-Z0-9_./@-]+)?)",'
    r'"freshness":\s*\{(?:"iso":\s*"[^"]+",\s*"human":\s*"[^"]+")\},'
    r'"boundary":\s*"(?P<boundary>memory|ontology|work|asset|governance)"'
    r'(?:,\s*"extras":\s*\{[^}]+\})?'
    r'}$'
)
```

## §1.5 实施分阶段

1. **T4.1** (本 Round): 设计文档 + schema + 验证正则
2. **T4.2** (R57+): Pydantic + zod schema 实装到 5 仓 (omo/runtime/kairon-utils/metaos/gbrain)
3. **T4.3** (R58+): cockpit output 集成 source-map 字段 + freshness 计算

## §1.6 累计 Gate C acceptance

- ✅ kairon/gbrain/metaos persistence risks resolved (T0)
- ✅ memory boundaries defined (T1)
- ✅ memory URI 路由表设计 (T2)
- ✅ one real question flows collect→ingest→search→output→archive (T3)
- ✅ search surfaces declare scope (T3 含 scope 声明)
- 🔄 **outputs include source metadata (T4, 本 doc 落地, 实施待)**

---

**OPC-P2-T4 设计完成。** 4 字段 schema + 5 边界映射 + freshness 计算 + 验证正则就位。R57+ 推进 T4.2 5 仓 schema 实装。
