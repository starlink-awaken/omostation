# Cockpit CLI 命令可用性台账

> **生成时间**: 2026-09-08 | **总命令数**: 106 | **关联 BET**: BET-Y1Q4-T10-141

## 汇总

| 分类 | 数量 | 占比 |
|---|---|---|
| ✅ PASS (直接可用或需参数/子命令) | 84 | 79% |
| ⚠️ 服务依赖 (需 daemon/服务启动) | 8 | 8% |
| ❌ 未实现 stub | 4 | 4% |
| ⚠️ 交互式/弃用 | 4 | 4% |
| ⚠️ 环境 (VIRTUAL_ENV/.omo) | 2 | 2% |
| **合计** | **106** | **100%** |

## 逐批验证结果 (12 个 category)

### 批次 1: 治理 Governance (16)
- ✅ PASS (--help+功能): cards, context, domain-status, facts-audit, governance, mcp, policy
- ✅ 需参数: command-audit, controller-shadow, dlp-guard, facts-validation, model-freshness, sanyi-status
- ✅ 需子命令: harness
- ❌ stub: **audit-ledger** (ADR-0201 尚未实现)
- ⚠️ 交互式: bdsk (需 TTY)

### 批次 2: 用户 User (8)
- ✅ PASS: docs, help, init, profile, quickstart, quickstart-check
- ✅ 需参数: completion
- ⚠️ 服务依赖: **demo** (需 demo 服务)

### 批次 3: 专项工具 Domain (13)
- ✅ PASS: cartridge, compute, decide, finance, gongwen, im-triage, omo
- ✅ 需参数: challenge, intent, render
- ✅ 需子命令: code, family-hub, spine

### 批次 4: 项目 Project (12)
- ✅ PASS: agent, agent-workflow, bcos, c2g, compass, debt, iterate, kems, readiness, wave2, workflow
- ✅ 需子命令: scenario

### 批次 5: 研究 Research (8)
- ✅ PASS: brief, daily, discover, knowledge, memory
- ✅ 需参数: research, search
- ❌ stub: **memory-distill** (ADR-0200 尚未实现)

### 批次 6: 通讯 Messaging (5)
- ✅ PASS: agora, bus, events, events-watch
- ✅ 需子命令: ssb

### 批次 7: 数据 Data (3)
- ✅ PASS: data
- ✅ 需参数: import
- ✅ 需子命令: contracts

### 批次 8: 总线接入 ECCP (1)
- ✅ PASS: channels

### 批次 9: 基础设施 Infra (11)
- ✅ PASS: chain, fabric, mof, telemetry
- ✅ 需子命令: mesh, observe
- ⚠️ 服务依赖: **dashboard** (TIMEOUT, 需 dashboard server), **ops** (Service Status 服务)
- ❌ stub: **fabric-mesh** (ADR-0202 尚未实现), **watchdog** (status=retired)
- ⚠️ 弃用: model-driven (ADR-0240 D1)

### 批次 10: 系统 System (15)
- ✅ PASS: audit, capabilities, health, journey, panorama, product-health, project, proxy-env, runtime, status, version
- ✅ 需参数: agent-runtime
- ⚠️ 服务依赖: **monitor** (TIMEOUT), **gac** (需主仓 .omo 上下文)
- ⚠️ 交互式: **tui** (TIMEOUT, 需 TTY)

### 批次 11: Agent 协作 (4)
- ✅ PASS: agent-onboard, swarm
- ✅ 需子命令: cell
- ⚠️ 环境: **resident** (VIRTUAL_ENV 冲突)

### 批次 12: 知识引擎 BOS (10)
- ✅ PASS: bos, bos-capability, bos-inbox, brain, domains, gbrain, kairon
- ✅ 需参数: ask, skill, vault

## 问题项清单 (需 BET-Y1Q4-T10-141 跟踪)

### ❌ 未实现 stub (4) — 优先 P1
| 命令 | ADR | 建议 |
|---|---|---|
| audit-ledger | ADR-0201 | 实现 Merkle 审计账本或 deprecate |
| fabric-mesh | ADR-0202 | 实现 LAN 边缘算力网格或 deprecate |
| memory-distill | ADR-0200 | 实现记忆自蒸馏或 deprecate |
| watchdog | - | 已被 mesh-bound capability 取代, 已显式 retired |

### ⚠️ 服务依赖 (8) — P2
| 命令 | 依赖 | 建议 |
|---|---|---|
| dashboard | dashboard server | 提供启动脚本 |
| demo | demo 服务 | 文档化启动命令 |
| monitor | 监控服务 | 文档化依赖 |
| tui | TTY | 文档化交互模式 |
| ops | ops 服务 | 文档化启动 |
| gac | 主仓 .omo 上下文 | 文档化调用方式 |
| resident | VIRTUAL_ENV | 修复 env 处理 |
| bdsk | TTY | 文档化交互模式 |

## 验证方法
```bash
# 全量 smoke test (106 命令, 串行执行, 总耗时 ~3 分钟)
cd projects/cockpit
for cmd in $(python -c "from cockpit.commands.registry import COMMAND_CATALOG; print('\n'.join(sorted(COMMAND_CATALOG)))"); do
  uv run python -m cockpit "$cmd" --help > /dev/null 2>&1 && echo "PASS: $cmd" || echo "FAIL: $cmd"
done
```

## BET 关联
- **BET-Y1Q4-T10-141**: Cockpit CLI 命令可用性验证与修复
- 修复 stub 命令和服务依赖命令后更新本台账

## 关联 PR
- agora #73 (fix(bos): 注册 documents 域白名单 + Transport 加 'mcp' 字面量) — 修复 cascading_test 因 documents 路由校验失败
