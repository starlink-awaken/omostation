---
type: ephemeral
created: 2026-09-03
---

# agora 全领域真实场景验证评估 (第二期: Documents 领域矩阵, 2026-08-07)

> 验证方式: 提取 /Users/xiamingxing/Documents 13 个领域 → 每个领域 3-5 个不同类型场景
> (检索/分析/治理/流程/记忆/知识) → 经真实 SSE 网关 (HTTP 7431) 端到端调用 → 精确判定
> (外层 ok + 内层 result.ok 才算成功)。
> 结论: **BOS 网关链路 100% 正常; 内部服务实现 35% 可用, 暴露 3 类系统性契约漂移。**
> **后续修复 (2026-08-07, agora 41b60de)**: 契约漂移已修复 — func_name 重映射 + 参数契约智能适配 + registry lint (防回归) + /health bos_registry 可观测 + get_service 索引化。

## 一、领域×场景矩阵

| 领域 | 场景类型数 | 链路可达 | 真实执行 ok | 说明 |
|---|---|---|---|---|
| @工作文档 | 5 (分析/治理/审计/检索/记忆) | ✅ | ✅ omo/audit | inspect 函数漂移 |
| @学习进化 | 5 (审计/知识/分析/记忆/元数据) | ✅ | ✅ evolution/loop + audit | quality/audit 参数错 |
| @驾驶舱 | 4 (知识/分析/记忆/治理) | ✅ | ✅ omo/audit | bus/event 缺 topic |
| @家庭生活 | 4 (分析/记忆/检索/治理) | ✅ | ✅ omo/audit | search 参数错 |
| KOS-Inbox | 3 (知识×2/记忆) | ✅ | ❌ | stdio backend 不可 spawn |
| _inbox | 3 (分析/记忆/检索) | ✅ | ✅ omo/audit | search 参数错 |
| @个人 | 3 (检索/治理/记忆) | ✅ | ✅ omo/audit | search 参数错 |
| @OPC | 3 (工作流/审计/知识) | ✅ | ✅ omo/audit | swarm 函数漂移 |
| @创意创作 | 2 (记忆/知识) | ✅ | ❌ | search 参数错 |
| @公共 | 2 (检索/治理) | ✅ | ✅ omo/audit | search 参数错 |
| Claude | 2 (分析/记忆) | ✅ | ❌ | stdio backend 不可 spawn |
| Zotero | 2 (分析/知识) | ✅ | ❌ | stdio backend 不可 spawn |
| _knowledge | 3 (归档/检索/治理) | ✅ | ✅ omo/audit | vault search 参数错 |

## 二、验证结果分层

### 层 1: BOS 网关链路 (40/40 = 100% ✅)
- 路由可达: 13 域全部注册 (list_bos_domains: memory 46/capability 39/governance 33/...)
- 鉴权: permissive 模式全部放行 (AGORA_API_KEY 空 + auth_permissive)
- 限流/配额/缓存/审计: 全部通过 (bos_calls_total 指标 + accounting 记账)
- 无 DENIED/EMPTY/HTTP 错误 (除 meta/discover 大响应解析器限制)

### 层 2: internal 服务真实执行 (5/14 = 35% ✅)
| 服务 | 结果 |
|---|---|
| bos://governance/omo/audit | ✅ 85.6 分 B 级 (真实治理审计) |
| bos://governance/evolution/loop | ✅ loop 存活 + 时间戳 |
| bos://meta/discover | ✅ 218 路由 (响应大解析器限制) |

### 层 3: stdio backend (26/40 = 65% 链路通但不可执行)
- 原因: P1 遗留环境性包缺失 (kos/minerva/iris backend 无法 spawn)
- 非 BOS 链路问题, 是 backend 部署问题

## 三、发现的系统性缺陷 (3 类契约漂移)

### 缺陷 1: 函数引用漂移 (func_name 未随重构更新)
```
# module 'omo.omo_inspect' has no attribute 'run_full_inspection'  (POC_SERVICES 引用旧函数名)
# module 'agora.mcp.swarm' has no attribute 'get_swarm_status'     (swarm 模块重构后 func_name 失效)
```
**影响**: 声明存在但执行必败, 误导"能力可用"。
**根因**: god-module split / 模块重构后 services_internal.py 的 func_name 未同步。

### 缺陷 2: internal 函数参数契约不一致 (核心)
```
# audit_knowledge_quality() missing 2 required positional arguments: 'text' and 'query'
# publish() missing 1 required positional argument: 'topic'
# _memory_all_search() got an unexpected keyword argument 'query'   (期望 args: dict, 被展开)
```
**根因**: resolver/api.py:370-373 `func(*args, **kwargs)` 将 resolve_bos_uri 参数**展开**传给 func;
但部分函数签名是 `(args: dict)` (期望整体 dict), 部分要命名参数。**无统一契约**。
**修复建议**: internal 调用统一传 `(args_dict,)`, 或按函数签名适配 (inspect.signature 检测 `args` 参数)。

### 缺陷 3: stdio backend 环境性不可用 (非代码缺陷)
```
# error: No such file or directory (os error 2)  — kos/minerva/iris backend 无法 spawn
```
**根因**: 本机缺包 (P1 遗留), 完整环境 (CI) 可用。

## 四、评估结论

### 达成
1. **BOS 网关链路完整可靠**: 40/40 场景路由可达, 鉴权/限流/配额/审计/缓存全通过
2. **真实可执行场景验证成功**: 治理审计 (85.6分) + evolution loop + meta discover
3. **配额/告警/能力目录在真实调用下全链路生效** (上期已验)

### 遗留 (需治理)
1. **函数引用漂移**: services_internal.py func_name 与实现不匹配 (3+ 处)
2. **internal 参数契约**: 无统一约定, 展开 vs dict 混用 → 需统一为 `(args: dict)`
3. **注册表健康检查缺失**: 无工具校验 func_name 可解析 + 签名匹配 (应加 registry lint)

## 五、方法论沉淀
- **外层 ok ≠ 执行成功**: 必须解析到内层 result.status, POC/缓存错误会被外层吞掉
- **验证要按契约分层**: 链路 (鉴权/路由) vs 执行 (func 可解析/签名匹配) vs 环境 (backend spawn)
- **POC_SERVICES 声明是"能力承诺"**: 承诺 30 internal 服务可用, 实际 5 个签名匹配 → 声明与实现鸿沟需闭环
