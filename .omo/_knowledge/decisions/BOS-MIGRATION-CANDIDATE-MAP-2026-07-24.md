---
id: BOS-MIGRATION-CANDIDATE-MAP
title: bos_stdio 真实迁移候选服务图谱（P81 S0.4 evidence）
owner: governance-team
status: candidate
created_at: 2026-07-24T08:55:00Z
stage: S0
strat: STRAT-P81
decisions: STRAT-P81-MASTER-DECISION-INBOX-2026-07-24.md
supersedes: 2026-07-24-p81-s0-phase45-residuals.md (audit 的 117/169=0.692 数字已 outdated)
source: projects/agora/etc/bos-services.yaml
warning: |
  Stage 0 evidence 包。仅在 P81 S0.4 (bos_stdio 真实迁移) 立项后启用。
  Agent 不得在立项前自行修改 bos-services.yaml 的 transport 字段。
---

# BOS 迁移候选图谱 (P81 S0.4 evidence)

## 0. 数字更正

| 来源 | 数字 | 备注 |
|------|------|------|
| `2026-07-24-p81-s0-phase45-residuals.md` | 117/169 ≈ 0.692 | 过期 |
| **本文件 (实时 SSOT)** | **108/169 = 0.6391** | SSOT 更正 |
| 目标 (phase45-plan) | < 0.65 | — |

**当前 ratio 0.6391 已经 < 0.65**,但仍需真实迁移而非声明保留。

## 1. 真实 transport 直方图

| transport | count | ratio |
|-----------|-------|-------|
| stdio | 75 | 0.4438 |
| mcp_stdio | 33 | 0.1953 |
| internal | 31 | 0.1834 |
| inline | 27 | 0.1598 |
| mcp_proxy | 2 | 0.0118 |
| http | 1 | 0.0059 |
| **总计** | **169** | **1.0** |

## 2. 迁移候选分组

### Group A: internal `module_path`/`func_name` 候选 (89)
- **特征**: stdio + `python -m <module>` 启动
- **迁移路径**: 移除 subprocess,改 `module_path: "pkg.module"` + `func_name: "main"` + `internal` transport
- **风险**: 跨包接口签名需校验;若模块依赖 `__main__` 副作用,需先抽出函数
- **抽样**: eidos/mcp-server, ontoderive/mcp-server, minerva/mcp-server, kronos/mcp-server, iris/mcp-server

### Group B: script-style stdio (19)
- **特征**: 启动 script 而非 python module(如 `python3 bin/gac/mcp-server-kos.py`)
- **迁移路径**: 需把 entrypoint 改成 `python -m` 形式,才进 Group A
- **风险**: 改 entrypoint 需创建包内 `__main__.py` 或包装 script
- **抽样**: kos/mcp-server, agent-workflow/{bootstrap,verify-plan,observe,compliance, doctor}

### Group C: mcp_proxy 真实接通 (2)
- **当前**: 2 个 mcp_proxy,1 个有 `mcp_tool=knowledge_ask`
- **风险**: 需 ProxyManager dispatch 验证脚本(adr-0228 已记录禁止纸面声明)
- **抽样**: memory/kos/graphrag, memory/kos/mcp-v2

## 3. 迁移到目标 < 0.50 的 projection

| 方案 | stdio/mcp_stdio 目标 | 总比例 | 备注 |
|------|---------------------|--------|------|
| 现状 | 108 | 0.6391 | — |
| 30% Group A → internal | 82 | 0.4852 | stage 1 目标 |
| 60% Group A → internal | 56 | 0.3314 | 极限 |
| Group A 全部 → internal | 19 | 0.1124 | 终极 |

注: 这是**理论** projection,真实迁移需立项后逐个验证 module_path/func_name 与 cross_references。

## 4. 立项前必须的 4 件事

(从 audit 黑名单提炼,任何迁移工程必须满足)

1. **真有 module_path/func_name** — 不止 transport label
2. **跨包调用签名校验** — 不能有 side effect 假设
3. **集成测试覆盖** — proxy 路由实测(有 dispatch proof)
4. **CI 跑通** — phase45 收尾 7 endpoint 仍全绿

## 5. 禁止剧场化

(`2026-07-24-p81-s0-phase45-residuals.md` 已记录)

- ❌ 改 `transport: mcp_proxy` label 但保留 `command[]` 且无 `mcp_tool`
- ❌ 改 gitignore 隐藏 archived
- ❌ 假装物理机在线
- ❌ 手填 `reachable_physical_hosts ≥ 4`

## 6. 立项条件

需 STRAT-P81-MASTER-DECISION-INBOX-2026-07-24.md #4 拍板 A/B/C 选项任一。

未拍板前,本文件作为 evidence-only 输出,不动 bos-services.yaml。
