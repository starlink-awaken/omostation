# AetherForge 深度审计报告

> 架构完整性 · L0 支撑 · 代码质量 · 性能瓶颈
> 2026-06

---

## 一、L0 MOF 支撑分析

### 1.1 覆盖率

```
M1 命名空间总数: 37 个
AetherForge 消费: 4 个 (11%)
已建模但未消费: 33 个 (89%)
```

| 消费方 | 读取的命名空间 | 状态 |
|:--------|:---------------|:----:|
| `TopologyScanner.load_static_nodes()` | `compute_engine/` | ✅ |
| `M1Loader` | `compute_engine/` + `compute_node/` + `hardware_asset/` + `network_zone/` | ✅ |
| `PricingRegistry` | `model/` (MODEL-PRICING-*) | ✅ |
| `QuotaEngine` | `quota_definition/` | 🟡 已加载但数据未完全利用 |
| `RouteScheduler` | `routing_policy/` | ❌ 尚未实现 |

**33 个命名空间未接入:**
`agent/`, `entity/`, `protocol/`, `specification/`, `workflow/`, `skill/`, `decision/`, `lesson/`, `intent/`, `pattern/`, `component/`, `service/`, `artifact/`, `mechanism/`, `bosroute/`, `cognitive_framework/`, `convention/`, `domain/`, `mcptool/`, `outcome/`, `process/`, `action/`, `architecture/` ...

### 1.2 路径硬编码问题

```
compute_engine/ 路径在 5 个文件中硬编码:
  llm_gateway/cli.py:28
  llm_gateway/mcp_server.py:15
  mesh/api/models_cli.py:16
  mesh/topology/scanner.py:27
  aetherforge/config.py:61
```

🔴 **ecos 仓库移位置则全部失效。**

---

## 二、架构问题 (6 类)

### 🔴 A 类: 重复实现

| 重复内容 | 出现位置 | 差异 |
|:---------|:---------|:-----|
| 重试逻辑 | `gateway/retry.py` vs `swarm/retry_policy.py` | 不同 API，不同默认值 |
| A2A 协议 | `swarm_engine/a2a_protocol.py` (498行) vs `swarm_engine/engine/a2a_protocol.py` (492行) | 几乎相同 |
| 兼容层 | `dispatch_compat.py` (350行) vs `dispatch/compat.py` (349行) vs `engine/dispatch/compat.py` (218行) | 同一份代码三副本 |
| SQLite 连接 | 7 个类各自 `sqlite3.connect()` | 无连接池，无统一模式 |
| 重导出桩 | `binding_strategies.py` / `call_dispatcher.py` / `capability.py` | 各一行 `from .core.xxx import *` |

### 🔴 B 类: 静默吞异常 (25+ 处)

```python
# 遍布整个代码库的模式:
try:
    do_something()
except Exception:
    pass  # 不日志、不计数、不重新抛出
```

最严重的:
- `worker/callbacks.py` — 6 个 hook 全吞异常（用户注册的回调失败完全不知道）
- `pool/cost_db.py` / `worker/object_store.py` — 成本记录/对象存储写失败静默
- `gateway/metrics.py` — 指标导出失败静默

### 🟡 C 类: 循环导入脆弱性

```
pool/manager.py ↹ worker/dispatcher.py
  → manager.py 用 deferred import 避免崩溃
  → 任何重构若移到模块级别即崩溃
```

### 🟡 D 类: 性能热点

| 热点 | 原因 | 影响 |
|:-----|:------|:------|
| `get_quota()` 同步等待 codexbar | 每个 Provider 串行 subprocess | 大盘首次加载 25s+ |
| `NetworkScanner._discover_mdns_hosts()` | DNS 超时等待 | 每次扫描 4-6s |
| `pool/health_check_all()` | TCP 端口探测串行 | N 个节点 × 2s |
| `credentials.py` SQLite 连接 | 每次调用 open/close | 无连接池，高频调用慢 |
| `_compat.py` (270行) | 所有 stub 在 import 时加载 | 拖慢 swarm 导入速度 |

### 🟡 E 类: 配置漂移

`aetherforge.yaml` 的 `pool.workers_per_node` → 代码实际从 `TaskDispatcher.provision_all()` 读取
`worker.message_bus_persist` → 代码从未消费此配置

### 🟢 F 类: 测试缺口

| 模块 | 测试状态 |
|:-----|:---------|
| `gateway/providers/` (9 个) | ❌ 零单元测试 |
| `gateway/metrics.py` | 🟡 间接测试 |
| `gateway/quota_engine.py` | ❌ 零单元测试 |
| `mesh/topology/m1_loader.py` | ❌ 零单元测试 |
| `mesh/topology/network_scanner.py` | ❌ 零单元测试 |
| `mesh/worker/callbacks.py` | 🟡 间接测试 |
| `mesh/worker/object_store.py` | 🟡 间接测试 |
| `swarm/group_chat.py` | 🟡 间接测试 |
| `swarm/graph_workflow.py` | 🟡 间接测试 |
| `swarm/monitor.py` | ❌ 零单元测试 |

---

## 三、修复优先级

| 优先级 | 问题 | 影响 | 建议方案 |
|:------:|:------|:------|:---------|
| **P0** | 静默吞异常 (25+ 处) | 生产问题无法追踪 | 全部加 `_log.exception()` 或 `_log.warning()` |
| **P0** | 路径硬编码 (5 处) | ecos 移动即崩溃 | 集中到 `config.py` 统一管理 |
| **P1** | 重复实现: 重试逻辑 | 维护成本翻倍 | 统一到 `gateway/retry.py`，swarm 引用 |
| **P1** | 重复实现: A2A 协议 | 两端不同步 | 删除 `engine/a2a_protocol.py`，保留一个 |
| **P1** | 重复实现: 三层 dispatch_compat | 350 行死代码 | 保留一份，标记 DEPRECATED |
| **P1** | SQLite 连接无池化 | 高频调用性能差 | 创建 `DBPool` 上下文管理器 |
| **P2** | 测试缺口 (10+ 模块) | 重构无安全保障 | 为高优先级模块加测试 |
| **P2** | 配置漂移 (2 处) | 配置不生效 | 消费未使用的配置项 |
| **P2** | 循环导入 (pool↔worker) | 重构风险 | 重构依赖方向 |
| **P3** | _compat.py 270 行 stub | 混淆真实接口 | 逐步替换为真实实现 |
| **P3** | 33 个 M1 命名空间未接入 | L0 信息浪费 | 按需逐个接入 |

---

## 四、架构迭代建议

### 短期 (当前 Sprint)

1. **修复 P0**: 25+ 处 `except: pass` → `except Exception as e: _log.exception()`
2. **修复 P0**: 路径硬编码统一到 `Config.M1_DIR`
3. **消除重复**: 重试逻辑统一 + A2A 去重 + dispatch_compat 去重

### 中期 (下个 Sprint)

4. **SQLite 连接池**: `DBPool` 上下文管理器，`with DBPool(path) as conn:`
5. **测试覆盖**: gateway providers + quota_engine + network_scanner 单元测试
6. **L0 消费**: 接入 `agent/`、`entity/`、`protocol/` 等关键命名空间

### 长期 (架构重构)

7. **干掉 `_compat.py`**: 替换 270 行 stub 为真实实现
8. **Provider 插件市场**: 让社区能贡献 Provider
9. **统一 Event/Metrics 总线**: 告别各自为政的 SQLite
