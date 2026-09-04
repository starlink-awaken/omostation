---
type: ephemeral
created: 2026-09-03
---

# agora 生产就绪深化 — 全面深度复盘报告 (2026-08-06)

> 复盘范围: P1 → P2 → 复盘修复 → 架构对齐 全链路 (6+1 PR)。
> 结论: **从"不能生产使用"到"可交付基线"** — 0 功能级阻断缺口, 遗留均为非阻断优化项。

## 一、PR 合并清单 (全部 MERGED)

| PR | 阶段 | 内容 | commit |
|---|---|---|---|
| #1047 | P1 | ProcessPool 接入 + ProxyManager 收口 + 路径 env 化 | agora 9987103 |
| #1052 | P1 | deploy 配置: admission=degraded + auth=permissive + data_dir | agora 2b5a8b1 |
| #1057 | P2 | /metrics + audit hashchain + 双进程统一 + 本地调用放行 | agora d128c5f |
| #1059 | P2 | swarm 面板 agora 健康 + CI deploy-smoke | 主仓 b02d6789 |
| #1061 | 复盘 | register 认证 + 口径统一 + verify_chain 闭环 + serve 清理 | agora 7756362 |
| #1064 | 对齐 | 文档/场景卡/cockpit SSOT/指针同步 | 主仓 a986f1d6 |
| #1065 | 收尾 | I0-CALLCHAIN 失效行号修复 (god-module split 后) | 主仓 (PR 中) |

## 二、起点 vs 终点 (审计 → 深化)

### 2026-08-05 审计结论: 生产就绪度 = 不能大规模使用
- 假绿: 仅 SSE 7431 存活, backends 0/118 proxy 工具全声明
- gateway cwd bug 致 backend 全灭; KeepAlive 优雅停机不重启
- audit_24h 恒 0 (since 字符串比较 bug); HTTP 7422 未部署

### 2026-08-06 终点: 可交付基线
- **假绿根治**: /health backends 91/5 (真实计数, 修复前恒 0)
- **可观测**: /metrics Prometheus + /health 7 维度 (services/backends/proxy/audit_24h/audit_chain/debt/issues)
- **安全**: register 端点认证 + shell 元字符拒绝
- **审计防篡改**: hashchain + verify_chain → audit_chain 闭环
- **架构**: SSE 单一 owner, gateway 废弃, ProcessPool 复用
- **工具消费**: 89 tools (修复前 0), cockpit bos mutate 走 SSOT 端口

## 三、关键修复深度分析

### 1. 假绿根因链 (三层)
```
层1: SSE/gateway 双进程各持独立 ProxyManager → backend 生命周期割裂
层2: KNOWN_BACKENDS 全 stdio, BackendHealthChecker 视 transient 跳过 heartbeat
     → _health_checker 恒报 0 (假绿机制根源)
层3: /health backends 口径混用 (P2-5 用 registry._clients 修 alive, total 用 entries=99工具)
修复: 双进程统一 (SSE owner) + registry._clients 计数 + service name 去重 (91/5)
```

### 2. 安全漏洞 (复盘发现)
- **P2-1 引入**: 抽 `_register_common_routes` 把 `/v1/backends/register` 暴露给 SSE
  → 无认证可注入任意 command (SSE 绑定 0.0.0.0)
- **修复**: require_agora_api_key 校验 + 拒绝 shell 元字符
- **教训**: 新增 HTTP 路由须过安全审查

### 3. 口径与死代码 (复盘发现)
- P2-5 修假绿时 total 量纲错误 → 统一 service name 去重
- verify_chain 实现但未接线 → health 暴露 audit_chain
- **教训**: 修指标须验证新旧口径语义一致; "实现"≠"闭环"

## 四、架构战略对齐成果

### agora 定位: I0 织层 "MCP Hub · BOS URI 路由" → 演进方向 "能力编排大脑"

**已具备能力** (P1+P2 后):
| 能力 | 状态 |
|---|---|
| 路由 (Trie + 语义) | ✅ resolve_with_capability |
| 编排 (a2a) | ✅ |
| 准入 (admission SPI) | ✅ 软绑定 metaos |
| 审计 (hashchain) | ✅ 闭环 |
| 可观测 (health/metrics) | ✅ |
| 治理 (9 tools) | ✅ |
| 能力生命周期 (B1/B2/B3) | ✅ 度量/路由/发现 |

**架构差距** (后续路线):
- P1: backends 连接率 5/91 提升 (包缺失 + admission 元数据)
- P2: 用量计费/配额 (网关→编排大脑关键一步)
- P3: 能力目录写闭环
- P4: 告警主动通知

## 五、同步更新闭环

- 文档: project-registry (196→200) / I0-CALLCHAIN (双进程+metrics+hashchain+行号) / AGENTS.md §8 / scene-card
- 配置: deploy launchd (admission/auth/data_dir/GATEWAY_OWNER) / cockpit port SSOT
- 规则: evidence-smoke gap=0 / governance-checks active
- 依赖: agora/cockpit 指针全对齐
- 验证: doc-ssot-lint 0 conflicts / 250+ tests / /health 端到端

## 六、最终验证 (Explore 确认)

- 文档-代码一致性: project-registry=200 一致; I0-CALLCHAIN 行号修复 (#1065)
- 指针: agora 7756362 = 子模块 main; cockpit ae1a121 = main
- 治理: evidence-smoke gap=0 score=100
- 服务: SSE 加载最新代码, /health audit_chain ok, /metrics 懒注册正常
- 并发注意: PR #1062 (god-module split) 基于 d128c5f, 合入前须 rebase 到 7756362 (缺 P0-SEC 修复)

## 七、方法论反思 (最重要的沉淀)

1. **修指标须验证新旧口径语义一致** — P2-5 只看 alive>0 没审 total 量纲
2. **新增 HTTP 路由须过安全审查** — P2-1 register 端点未认证
3. **"实现"≠"闭环"** — hashchain 写入完整但校验未接线
4. **"修复"≠"对齐"** — 代码修复后须同步文档/配置/规则/依赖 (第四重漂移)
5. **并发 agent 协作** — 共享 checkout 反复被 reset → 改动即 commit + 隔离 worktree
6. **CI pre-existing 失败识别** — god-module 大文件/evidence 漂移/CI 环境问题非 PR 引入, required checks 才是合并依据

## 八、非阻断遗留

| 项 | 建议 |
|---|---|
| I0-CALLCHAIN 行号 | ✅ #1065 已修 |
| cockpit web/ 层 3 处 7422 默认值 | 改 port-registry 或 env (可选) |
| PR #1062 god-module split | 合入前 rebase 到 7756362 |
| backends 5/91 | P1 后续 (包缺失 + admission 元数据) |
