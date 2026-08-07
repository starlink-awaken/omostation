# agora P3/P4 真实场景验证评估报告 (2026-08-07)

> 验证方式: 重启 SSE 加载最新代码 → 构造真实 BOS 调用场景 → 多轮跑测 → 端到端评估。
> 结论: **核心功能全部生效, 发现并修复 2 个 pre-existing bug, 稳定性优秀。**

## 一、验证场景与结果

### 场景 1: BOS 调用 + 配额记账 (遗留-3)
| 验证点 | 结果 |
|---|---|
| 真实 BOS 调用 (bos://meta/discover) | ✅ 返回 218 路由, source=cache |
| 配额记账落库 | ✅ accounting DB 新增 admin 2 条记录 (08-07 timestamp) |
| caller_id 解析 | ✅ admin (permissive 本地调用) |
| 缓存命中不记账 | ✅ 设计正确 (缓存无实际成本) |

### 场景 2: 配额超限拦截 + 告警 (遗留-3/4)
| 验证点 | 结果 |
|---|---|
| 配额超限拦截 | ✅ allowed=False, usage_ratio=5.0, remaining=0 |
| blocked 告警触发 | ✅ quota:blocked 事件 + Prometheus 指标 |
| health:degraded 告警 | ✅ agora_alerts_total{event="health:degraded"} = 1.0 |

### 场景 3: 能力目录写闭环 (P3)
| 验证点 | 结果 |
|---|---|
| bos_capability_admit | ✅ 返回 active/admitted, YAML 写入 (200→201) |
| YAML 持久化 | ✅ bos://p3test/demo/echo 进入 bos-services.yaml |
| bos_capability_retire | ✅ 状态 active→deprecated 持久化 |
| 测试数据清理 | ✅ p3test 移除, 还原 200 |

### 场景 4: 可观测性 (P1/P2/P4)
| 验证点 | 结果 |
|---|---|
| /metrics bos_calls_total | ✅ capability/compute + persona 各 1 |
| /metrics agora_alerts_total | ✅ health:degraded = 1.0 |
| swarm 面板 agora_health | ✅ degraded + backends 7/127 + audit_24h=3 |
| audit hashchain | ✅ audit_chain ok |

### 场景 5: 稳定性 (多轮)
| 验证点 | 结果 |
|---|---|
| 10 轮 resolve_bos_uri | ✅ 全部稳定返回, ~0.03s/轮 (缓存命中) |
| 5 轮 status 确认 | ✅ 5/5 ok |

## 二、验证发现并修复的 Bug (PR #1081)

### Bug 1: `_publish_bos_event` 签名不匹配 (HIGH)
- **位置**: `tools_bos/_helpers.py:85`
- **现象**: 签名 `(bus, uri, status, **extra)` vs 调用方 5 参 `(bus, uri, action, status, duration_ms)` → **TypeError, 事件发布全失败**
- **根因**: god-module split 时重构签名未同步调用方
- **修复**: 按调用约定恢复 5 参签名 (action/status/duration_ms)
- **影响**: 修复前 BOS 调用事件 (audit/monitoring) 静默失败

### Bug 2: `bos_capability_lifecycle` import 失败 (MED)
- **位置**: `tools_bos/bos_capability_lifecycle.py:162`
- **现象**: `from agora.bus import get_event_bus` 失败 (bus 已迁移 bus_foundation) → **capability 工具注册被跳过**
- **根因**: 模块迁移后 import 路径未更新
- **修复**: 改 `from agora.core.state import get_event_bus`
- **影响**: 修复前 admit/retire 工具完全不可用 (即使 P3 写方法已实现)

## 三、评估结论

### 达成 (P1-P4 全链路真实生效)
1. **配额计费**: 记账→拦截→告警 完整链路验证
2. **统一告警**: EventBus + webhook + Prometheus 指标 (quota/health/circuit)
3. **能力目录写闭环**: admit→persist→retire 端到端
4. **可观测**: /metrics 指标 + 面板 + hashchain 全绿

### 遗留 (非阻断)
1. **capability 工具独立实例架构**: bos_capability_admit/retire 挂在独立 FastMCP 实例 (bos-capability-lifecycle), 未暴露到主网关 /v1/tools/call。修复后独立实例可用, 但主网关仍调不到。**需架构决策**: 挂主 mcp 或网关转发。
2. **backends 7/127 alive**: 环境性 (外部包缺失), 已用 enabled 过滤。
3. **yaml.safe_dump 重写风险**: P3 save() 用 safe_dump 会重写 bos-services.yaml (格式/注释丢失)。当前测试验证 OK, 但生产调用前应确认 YAML 结构兼容。

## 四、方法论沉淀
- **"验证"是发现深层 bug 的最有效手段**: 2 个 pre-existing bug (签名漂移 + import 迁移) 都是单测覆盖不到的集成级问题, 真实调用才暴露
- **测试数据污染**: p3test 写回 YAML 后需清理, safe_dump 重写风险 → 测试用临时文件, 生产操作谨慎
