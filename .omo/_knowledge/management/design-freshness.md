# P1-FRESHNESS_AUTO + X2-NO_FRESHNESS 方案

> 2026-06-06 | 状态: design-locked

## 目标
X2 抗熵真正落地：自动化协议校验、服务审计、周报生成。

## 现状
- `scheduler.py` — 有健康扫描但无 freshness 追踪
- `matrix.py` — 服务注册表，无 age 字段
- `protocol.py` — 协议加载，无定期校验
- 周报: 手动运行 `omo-debt report`

## 设计方案

### 1. Freshness 追踪 (已实现)
在 `scheduler.py` 中添加:
- `_freshness: dict[str, float]` — 每个服务的最后健康时间戳
- 健康检查成功时更新
- 超过 N 次扫描不可达 → 标记 stale
- `runtime matrix list` 显示 freshness age

### 2. 协议保鲜 (Phase 2)
在 `scheduler.py` 中添加每日协议校验:
- 加载 `L0-registry.yaml`
- 对每个 active 协议，检查其 spec_url 是否可达
- 记录到 `.omo/evidence/freshness/`

### 3. 自动周报
在 `cli.py` 添加 `runtime report weekly`:
```bash
# 聚合:
# - 服务状态变化
# - 新增 stale 服务
# - 债务进展 (从 .omo/debt/)
# - 协议变更
```

参考: `scheduler.py`, `cli.py`, `protocol.py`
