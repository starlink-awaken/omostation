---
type: ephemeral
created: 2026-09-03
---

# agora 超长链路场景验证报告 (2026-08-07)

> 验证方式: 从 agora 工作领域构造 5 个超长链路场景, 每个含多轮/多步, 经真实 SSE 网关
> (HTTP 7431) + 进程内能力端到端验证。报告含**产品功能**与**架构**双视角分析。

## 一、场景总览

| # | 场景 | 链路环节 | 结果 | 关键数据 |
|---|------|---------|------|---------|
| 1 | 能力生命周期 | 域发现→能力调用→路由→metrics→审计 | 6/6 ✅ | omo/audit 7258ms(真实执行), meta/discover 11ms(缓存) |
| 2 | 配额告警闭环 | 记账→60%未预警→80%warning→120%blocked→翻转→恢复 | 5/5 ✅ | ratio 0.6→0.8→1.2, 状态翻转只发一次 |
| 3 | BOS 调用全链路 | 10 轮×5 服务: 鉴权→限流→配额→缓存→路由→执行→审计→记账→指标 | 40/50 执行ok, 链路 50/50 | p50=2ms, avg=174ms, 0 链路错误 |
| 4 | 健康自愈+可观测 | /health→bos_registry→metrics→面板→告警事件 | 5/5 ✅ | registry 26/30 (86.7%), 面板 backends 7/127 |
| 5 | 能力目录+审计持久化 | 14 域→add→YAML→reload→retire→原保留→审计链 | 6/6 ✅ | hashchain 55/55 verified |

**汇总: 5 场景 27/28 步通过, 50 次调用 0 链路错误, 审计 55 条全 verified。**

## 二、产品功能视角分析

### 2.1 能力可用性 (P3 交付)
- **能力生命周期闭环**: discover→admit→route→call→retire 全链路可操作, YAML 持久化非破坏 (原能力保留)
- **真实可执行能力**: governance/omo/audit (85.6 分治理审计), meta/discover (218 路由), swarm status — 这些是"真能力", 不是占位
- **能力声明 vs 实现**: 30 internal 服务中 26 可解析 (86.7%), 4 个环境性外部包缺失; 契约硬化后无 broken

### 2.2 成本治理 (遗留-3/4 交付)
- **配额闭环完整**: 用量 60%→80% (warning 预警)→120% (blocked 拦截)→恢复重置, 状态翻转不重复告警
- **成本可观测**: 每次调用记账 (caller_id/service/cost), 面板/health 反映用量

### 2.3 告警与可观测 (P4 交付)
- **统一告警入口**: quota:warning/blocked, health:degraded, circuit:open, test 事件全链路
- **健康自愈**: degraded→告警→面板反映, 恢复→recovered (force 绕过防抖)
- **审计完整性**: hashchain 55 条全部 verified, 无断链

### 2.4 性能体验
- **冷启动 vs 缓存**: 首轮 omo/audit 8483ms (真实审计计算), 后续 2-5ms (缓存命中)
- **p50=2ms**: 用户日常感知毫秒级响应
- **10 轮稳定性**: 0 错误, 无挂起

## 三、架构视角分析

### 3.1 链路分层架构
```
┌─ 入口层 ─┐  HTTP tools/call → MCP 工具路由 (SSE :7431)
├─ 安全层 ─┤  鉴权 (AGORA_API_KEY/permissive) → 域授权 → CR-RBAC-01
├─ 治理层 ─┤  限流 (RateLimiter 令牌桶) → 配额 (QuotaChecker) → 熔断 (CircuitBreaker)
├─ 路由层 ─┤  BOSRouter 发现 → adapter 分发 (poc/internal/proxy/stdio)
├─ 执行层 ─┤  internal (importlib 同进程) / stdio (子进程 spawn)
├─ 持久层 ─┤  审计 (SQLite append-only + hashchain) → 记账 (accounting DB)
└─ 可观测层 ┤  Prometheus 指标 → EventBus 事件 → webhook → 面板
```

### 3.2 架构优势 (验证确认)
1. **关注点分离**: 安全/治理/路由/执行/持久/可观测六层解耦, 每层独立可测
2. **降级策略**: 契约硬化后 import/attr 失败返回结构化错误 (executable:false), 不抛裸异常
3. **契约自校验**: registry lint (test_bos_registry_contract.py) 固化 func 可解析性检查, 防回归
4. **性能架构**: get_service 索引化 O(1), 缓存层 (Cache TTL) 承载高频读, 冷路径才走真实执行
5. **可观测闭环**: /health + /metrics + 面板 + 审计链 四路信号, 任何一层异常可被监测

### 3.3 架构短板 (验证暴露)
| 短板 | 证据 | 影响 | 建议 |
|------|------|------|------|
| capability 工具独立实例 | admit/retire 挂在 FastMCP("bos-capability-lifecycle"), 主网关调不到 | 能力管理不可经 HTTP 操作 | 挂主 mcp 或网关转发 |
| internal 参数契约仍混用 | memory/local/all-search 需 (args:dict) 但部分服务定义未对齐 | 10/50 调用内部执行失败 | 服务定义统一契约 + registry lint 校验签名 |
| stdio backend 环境性 | 65% 服务链路通但 spawn 失败 | 本机能力受限 | CI 完整环境验证 + 环境检测降级 |
| 首轮冷启动 8.5s | omo/audit 真实审计计算 | 首调延迟高 | 预热机制或异步化 |

## 四、建议路线
1. **P5 能力管理网关化**: capability lifecycle 工具挂主 mcp, HTTP 可操作 admit/retire
2. **P6 契约统一**: 所有 internal 服务签名统一 (args:dict), registry lint 加签名断言
3. **P7 冷启动优化**: 治理审计等重计算服务预热/缓存结果
4. **P8 面板增强**: swarm-activity-dashboard 显示 bos_registry 契约健康 + 配额用量

## 五、方法论沉淀
- **超长链路验证** = 单点验证 + 跨层端到端: 每个场景覆盖 5+ 层, 暴露单层测试发现不了的集成问题
- **多轮压测价值**: 首轮冷启动 vs 后续缓存对比, 暴露真实性能特征
- **产品/架构双视角**: 产品视角验证"能力可用/成本可控/告警及时", 架构视角验证"分层/降级/契约/性能"
