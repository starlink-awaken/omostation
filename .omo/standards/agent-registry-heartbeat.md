---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# Agent Registry Heartbeat, Cache & Identity Gate — M2.2

> 状态: active | 版本: v1.0 | 关联: M2.2-AGENT-REGISTRY-HEARTBEAT
> 适用范围: agentmesh Gateway, Agora Registry, 所有注册 Agent

---

## 1. 问题陈述

当前 Agora Registry 是 MCP 服务发现的单点。如果 Registry 不可达：
- 新 Agent 无法获取路由信息
- 已运行 Agent 无法刷新身份 token
- 恶意 Agent 可能注入假服务

## 2. Heartbeat 策略

### 2.1 正常流程

```
Agent → Registry: POST /api/heartbeat {agent_id, identity_token, ttl: 60}
Registry → Agent: 200 OK {status: "renewed", expires_at}
```

- Agent 每 60s 发送 heartbeat
- TTL 默认 60s，Registry 返回实际过期时间
- 连续 3 次 heartbeat 失败 → Agent 标记为 `zombie`

### 2.2 Heartbeat 超时处理

| 状态 | 条件 | 行为 |
|------|------|------|
| active | heartbeat < 60s ago | 正常路由 |
| stale | heartbeat 60-180s ago | 仍可路由，发警告 |
| zombie | heartbeat > 180s ago | 取消路由，通知管理员 |
| dead | zombie > 24h | 自动注销 |

### 2.3 Registry 不可用时

当 Registry 整体不可达时：

```python
# Local cache behavior
if registry_unreachable:
    # 1. 使用本地缓存的路由表（最后同步版本）
    local_cache = load_local_cache()
    
    # 2. 拒绝新 Agent 注册（防注入）
    new_registration_allowed = False
    
    # 3. 现有 Agent 继续使用缓存路由
    #    但不更新 heartbeat
    agent_uses_cached_routes = True
    
    # 4. 缓存有效期：最长 15 分钟
    if cache_age > 900:  # 15 min
        agent_enters_safe_mode()  # 只读模式
```

## 3. 本地缓存行为

| 场景 | 读操作 | 写操作 | Heartbeat |
|------|--------|--------|-----------|
| Registry 正常 | 实时查询 | 实时写入 | 正常发送 |
| Registry 不可达 <5min | 缓存可用 | 缓存写入，队列同步 | 本地标记 |
| Registry 不可达 5-15min | 缓存可用 | 拒绝 | 本地标记 |
| Registry 不可达 >15min | 降级只读 | 拒绝 | 告警 |

## 4. Agent Identity 验证规则

### 4.1 Identity Token

```yaml
# Agent identity token schema
agent_id: str            # 唯一标识，如 "minerva-worker-01"
agent_type: str          # "research" | "indexer" | "gateway" | "orchestrator"
capabilities: [str]      # ["read", "write", "admin"]
identity_token: str      # JWT 或 HMAC 签名
issued_at: ISO-8601
expires_at: ISO-8601
public_key: str          # 用于签名验证
```

### 4.2 身份验证流程

```
1. Agent 启动 → 生成 keypair → 发送 register 请求
2. Registry 验证 → 签发 identity_token (JWT, 24h 有效)
3. 每次 heartbeat → 附带 identity_token
4. Registry 验证 token → 返回更新后的 token（续期）
5. Token 过期 → Agent 被标记为 zombie
```

### 4.3 恶意 Agent 注入缓解

| 攻击场景 | 缓解措施 |
|----------|----------|
| 伪造 agent_id | Registry 签发 HMAC-signed token，无法伪造 |
| 重放攻击 | Token 含 timestamp + nonce，60s 窗口 |
| 注册超量 Agent | 每 identity_key 最多 5 个 agent |
| 提权 | capability 必须在注册时声明，不可变更 |
| Registry 不可达时注入 | 新注册被拒绝（见 §2.3）|

## 5. Deadlock 检测

Agent 死锁检测规则：

| 检测项 | 条件 | 行为 |
|--------|------|------|
| 任务超时 | Agent 执行任务 > 30min 无进展 | 发送 probe，标记可疑 |
| Heartbeat 停跳 | 3 次 miss | 标记 zombie，重新调度任务 |
| 重复任务 | 同一任务被 2+ agent 认领 | 停止新调度，人工介入 |
| 循环依赖 | Agent A → B → A 互相等待 | 超时检测 + 强制取消 |

## 6. 测试/验收场景

| 场景 | 输入 | 预期输出 |
|------|------|----------|
| 正常 heartbeat | Agent 每 60s 发送 | Registry 返回 `renewed` |
| Heartbeat 超时 | 停止发送 180s | Agent 标记 `zombie`，取消路由 |
| Registry 宕机 5min | 断开 Registry | 缓存路由可用，新注册拒绝 |
| Registry 宕机 15min | 持续不可达 | Agent 进入 safe mode |
| 恶意 agent 注入 | 伪造 agent_id 注册 | HMAC 验证失败，拒绝 |
| Token 过期 | 24h 不续期 | Agent 标记 zombie |
| 死锁检测 | 任务 30min 无进展 | Probe 发送，任务可重新调度 |

## 7. 集成方案

Phase 2 M2.2 不要求完整实现所有组件，但要求：

1. ✅ **策略已设计**（本文件）
2. **Agora Registry 扩展**: 注册时附带 identity_token / heartbeat 字段
3. **agentmesh Gateway 集成**: 发送 heartbeat + 本地缓存
4. **Ops/Hermes 集成**: 告警 zombie agent + 审计日志

当前阶段优先级：完成设计和 Agora Registry schema 扩展。
