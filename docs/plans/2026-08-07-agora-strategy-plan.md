---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# agora 系统性分析与战略规划 (2026-08-07)

> 本方案系统审视 agora 从 P1 到 P8 的全部成果与验证暴露的短板,
> 制定四个阶段的架构与实现方案, 分步骤落地。

## 一、系统性现状分析

### 1.1 已建成能力 (P1-P8, 16 PR)

| 阶段 | 能力 | 验证状态 |
|------|------|---------|
| P1 | 网关基础: 进程池/代理/路径 env 化/deploy | ✅ 全量测试 |
| P2 | 可观测: /metrics + 审计 hashchain + 双进程统一 | ✅ 60 步复杂场景 |
| P3 | 能力目录写闭环: add/retire/save 持久化 | ✅ 8 阶段治理闭环 |
| P4 | 统一告警: EventBus + webhook + 指标 | ✅ 故障自愈 |
| P5 | 能力管理网关化: HTTP admit/retire | ✅ HTTP 端到端 |
| P6 | 契约统一: registry lint 签名断言 | ✅ 27 passed |
| P7 | 冷启动优化: 缓存 + 预热 | ✅ 8.5s→0ms |
| P8 | 面板增强: 契约健康上屏 | ✅ dashboard 显示 |

### 1.2 验证暴露的短板 (按严重度排序)

| # | 短板 | 严重度 | 影响 |
|---|------|--------|------|
| S1 | registry lint 未进 CI 门禁 | 高 | 契约漂移 PR 后才暴露 |
| S2 | 配额 cost_usd 恒 0 (无 token 统计) | 高 | "成本治理"名不副实 |
| S3 | 大响应 11KB+ 崩 json.loads | 中 | 客户端解析失败 |
| S4 | 告警事件无人消费 | 中 | 告警不达用户 |
| S5 | stdio backend 环境性 (65%) | 中 | 声明 vs 实现鸿沟 |
| S6 | 共享 checkout 滞后 | 低 | 工具版本漂移 |
| S7 | 无全链路 trace | 中 | 延迟定位靠猜 |
| S8 | 单实例无故障域 | 低 | 扩展性受限 |

### 1.3 架构成熟度评估

- **分层架构**: 六层完整 (安全/治理/路由/执行/持久/可观测) ✅
- **契约一致性**: P6 后无 broken (86.7%) ✅ 但缺 CI 强制
- **数据一致性**: 审计 hashchain 69/69 ✅
- **治理闭环**: 能力生命周期 + 配额 + 告警全链 ✅ 但告警消费缺环
- **性能**: p50 2ms, 冷启动已优化 ✅
- **生产就绪度**: 高, 但计费真实性与 CI 门禁待补

## 二、战略规划 (四阶段)

| 阶段 | 主题 | 目标 | 对应短板 |
|------|------|------|---------|
| 阶段 1 | **契约强制** | registry lint 进 CI, 漂移 PR 期拦截 | S1 |
| 阶段 2 | **真实计费** | token 统计 + 真实成本, 治理名副其实 | S2 |
| 阶段 3 | **响应健壮** | 大响应分页/转义, 客户端零失败 | S3 |
| 阶段 4 | **告警达用户** | 告警事件消费 (通知面板/文件), 闭环 | S4 |

## 三、架构与实现方案

### 阶段 1: registry lint 进 CI (S1)

**目标**: 契约漂移在 PR 阶段拦截, 而非事后。

**方案**:
1. agora CI (deploy-smoke 或独立 job) 加 `pytest tests/unit/test_bos_registry_contract.py`
2. 主仓 gac-local-gate 加 agora registry lint 检查项 (若主仓门禁覆盖子模块)
3. lint 失败 → PR 必 fail (required check)

**落地文件**:
- `.github/workflows/*.yml` (agora): registry-contract job
- 主仓 `bin/gac/gac-local-gate.py`: 可选加检查

### 阶段 2: 配额真实计费 (S2)

**目标**: cost_usd 反映真实 token 成本, 配额治理"名副其实"。

**方案**:
1. resolve_bos_uri 成功后获取 token 统计 (input/output)
   - internal 服务: 函数可返回 usage; stdio 进程: 从响应解析
2. cost = estimate_cost(input_tokens, output_tokens) — accounting.py 已有
3. 记账含 token 字段 (CallRecord 已支持)
4. 无 token 统计时回退: 按调用计 1 次 (成本 0) 保留流水

**落地文件**:
- `src/agora/mcp/resolver/api.py`: internal 响应提取 usage
- `src/agora/server/tools_bos/registration.py`: 记账传 token

### 阶段 3: 大响应处理 (S3)

**目标**: 11KB+ 响应客户端可解析。

**方案**:
1. resolve_bos_uri 返回时对 result 做 JSON 安全处理 (ensure_ascii + 转义 control char)
2. 大结果 (>10KB) 加 `truncated: true` + `truncated_length`, 可选分页参数
3. 客户端 (cockpit web) 适配

**落地文件**:
- `src/agora/server/_response.py`: `_ok()` 大响应保护
- `src/agora/server/tools_bos/registration.py`: 截断标记

### 阶段 4: 告警消费端 (S4)

**目标**: 告警从"发出"到"通知到人"。

**方案**:
1. 告警事件持久化: EventBus 订阅 `quota:*`/`health:*`/`circuit:*` → 写入告警日志 (JSONL)
2. 面板消费: swarm-activity-dashboard 读告警日志显示最近告警
3. 可选邮件/webhook (已有 webhook, 补订阅器)

**落地文件**:
- `src/agora/mcp/agora_alerts.py`: 告警日志写入
- 主仓 `bin/gac/swarm-activity-dashboard.py`: 告警视图

## 四、分步推进路线

| 步骤 | 动作 | 验证 |
|------|------|------|
| 1 | 阶段 1: registry lint 进 CI | PR 契约漂移被拦 |
| 2 | 阶段 2: 配额真实计费 | 记账含 token + 真实 cost |
| 3 | 阶段 3: 大响应处理 | 11KB 响应客户端可解析 |
| 4 | 阶段 4: 告警消费端 | 告警日志 + 面板显示 |

每步: agora commit → main → 主仓 bump → PR → 合并 → 验证。

## 五、风险与缓解

| 风险 | 缓解 |
|------|------|
| CI 加检查致现有 PR 失败 | 先 shadow (只记录) 后 fail |
| token 统计复杂 (stdio 解析) | 内部优先, stdio 回退计次 |
| 大响应截断丢数据 | 提供分页参数, 截断只加标记不丢 |
| 告警日志膨胀 | 轮转 + 只存最近 N 条 |

## 六、后续战略方向 (规划后)

- **能力市场**: 能力定价/发现/采购/退役 (P3 目录 → 市场)
- **全链路 trace**: request_id 贯穿 8 层
- **声明驱动生成**: 从 POC_SERVICES 自动生成测试/文档/mock
- **多实例部署**: 网关多实例 + 负载均衡

## 七、落地状态 (2026-08-08 标注)

- **阶段1 契约强制**: ✅ registry lint 已在 CI
- **阶段2 真实计费**: ✅ resolve_pricing 混合三层 (记账价=市场价)
- **阶段3 响应健壮**: ✅ _safe_result 大响应截断
- **阶段4 告警消费**: ✅ JSONL 持久化 + list_recent_alerts
- **能力市场**: ✅ P0-P5 全落地 (定价/发现/账单/采购记录/市场总览/采购门槛)
