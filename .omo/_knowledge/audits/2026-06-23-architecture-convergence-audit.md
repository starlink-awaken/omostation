# 架构整合与收敛审计报告

## 元信息
- **审计时间**: 2026-06-23
- **审计范围**: eCOS 全系统架构（5+4+1+1 分层）
- **审计方法**: 六步收敛分析（扫描→锚点→路径→审议→落地→验证）
- **触发原因**: 老王要求"全面的架构整合和收敛"
- **关联 BET**: BET-ARCH-CONVERGENCE

## 全景摘要

当前 eCOS 系统架构已完成大量收敛工作：
- 工作流编排 5 引擎→ecos/workflow（95/100 ✅）
- X1-X4 治理规则 26 条代码化 ✅
- CLI 入口收敛至 cockpit ✅
- 入口收敛 metaos MCP 已关 ✅
- 归档项目能力已迁移至 aetherforge ✅

## 发现断层（7 个域归并为 6 Phase）

### 🔴 Phase 1 (P0): AAMF 治理自动化管道未激活
**状态**: candidate | **依赖**: 无（独立）
**发现**: 9 个 arcnode-* cron job 全部未调度。governance.jsonl 停摆 28 天。
**exit gate**: 9 cron jobs 注册 + 首次运行正常 + governance.jsonl 新条目
**AC**:
- [ ] cronjob list 显示 11+ jobs
- [ ] drift-check 产生新条目
- [ ] evolve 产生 entropy 数据
- [ ] sync-constitution 26 约束 current

### 🔴 Phase 2 (P1): ecos workflow 缓存缺失
**状态**: candidate | **依赖**: Phase 1 done
**发现**: 对标 Temporal/Prefect/Argo，唯一缺失能力是缓存。架构评分 95→100 需补齐。
**exit gate**: 833 tests pass + 10+ 缓存测试 + 对标表缓存列 ✅
**AC**:
- [ ] cache_ttl 字段在 M1 YAML 中
- [ ] 缓存命中/过期/手动失效 工作
- [ ] 833 tests pass

### 🔴 Phase 3 (P1): Agora server/mcp.py 1,945L 上帝模块
**状态**: candidate | **依赖**: Phase 1 done
**发现**: 42+ MCP 工具全在一个文件，已影响可维护性。
**exit gate**: server/mcp.py ≤ 300L + 1200 tests pass + 42+ tools 可用
**AC**:
- [ ] 4-5 个域子模块
- [ ] server/mcp.py ≤ 300L
- [ ] 1200 tests pass

### 🟡 Phase 4 (P2): MetaOS BOS 治理化
**状态**: candidate | **依赖**: Phase 1 done
**发现**: metaos MCP 直启已关，但 BOS URI 3 条仍在子进程直通不过治理管道。
**exit gate**: metaos 3 条 BOS 调用均过 governance pipeline + audit 日志
**AC**:
- [ ] metaos/decide/immune/route 经过 X1 校验
- [ ] governance.jsonl 有 audit 条目

### 🟡 Phase 5 (P2): X3 成本/价值归因未激活
**状态**: candidate | **依赖**: Phase 2+4 done
**发现**: X3-C02/C03 定义 preferred，X3CostRecorder 是 stub，无运行时成本归因。
**exit gate**: cost ledger 有真实条目 + X3-C02/C03 type=required
**AC**:
- [ ] X3CostRecorder.record() 真实写入
- [ ] L0-constraints.yaml 约束提升
- [ ] workflow 执行产生 cost 记录

### 🟡 Phase 6 (P2): AAMF 治理节点重同步与校准
**状态**: candidate | **依赖**: Phase 1+4 done
**发现**: 28 个 ARCH_NODE 与 workspace 16 项目不一致，calibrate 从未运行。
**exit gate**: calibrate 基线 + 节点同步 + drift 率 < 10%
**AC**:
- [ ] baseline-latest.json + scorecard-latest.md
- [ ] 16 个活跃项目的 ARCH_NODE 齐全
- [ ] 已归档节点已标记

## 依赖图

```
P1-CRON（独立）
  ├─→ P2-CACHE
  ├─→ P3-AGORA-SPLIT
  └─→ P4-METAOS-GOV
        └─→ P6-CALIBRATE
              └─→ P5-COST（也需要 P2 完成后验证 cache 产生 cost）
```

## 退出总门禁（BET 关闭条件）
- [ ] 6 个 REMEDIATE 全 status=done
- [ ] P1: 9 cron jobs + governance.jsonl 最新
- [ ] P2: 833 tests + 缓存 ✅
- [ ] P3: 1200 tests + server/mcp.py ≤ 300L
- [ ] P4: metaos BOS 治理化
- [ ] P5: cost ledger + X3 required
- [ ] P6: calibrate baseline + 节点同步
- [ ] arcnode-calibrate 系统健康分 ≥ 90
