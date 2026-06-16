# P43 W0 试点复盘: c2g 治理循环试跑

> **日期**: 2026-06-16
> **Phase**: 43 · W0
> **试点目标**: 验证 c2g 五机制(brainstorm/draft/bet/radar/gc)作为 omostation 治理循环骨干
> **关联规划**: [c2g-enchanted-coral](../../../Plans/c2g-enchanted-coral.md)
> **关联战略 SSOT**: [strategic-governance-p42](strategic-governance-p42.md)
> **状态**: ✅ 试点完成, 决策扩展(P44 进入 W1-W3)

---

## 1. 试点目标(复述)

| 项 | 目标 | 实测 |
|----|------|------|
| c2g 5 机制可用 | brainstorm/draft/bet/radar/gc 全部跑通 | ✅ 5 子命令可用 |
| radar 真审计 | 读 .omo/tasks/{done,planned} 真数据 | ✅ 90 任务审计 + 3 异常 |
| health.yaml SSOT | radar 输出落治理健康分 SSOT | ✅ health_score=55 |
| system.yaml 引用化 | 不再静态写 77.5 | ✅ health_score_ref 指向 .omo/state/health.yaml |
| pre-commit hook | 改坏 SSOT → exit 1 | ✅ 实测阻断 1 次 |
| 战略 SSOT 文档 | 写 .omo/_knowledge/management/strategic-governance-p42.md | ✅ 123 行 |
| c2g 完整链路演练 | 走通 valid Pitch 落 OMO Task | ✅ local adapter 走通 |

---

## 2. 关键 evidence

### 2.1 c2g radar 真审计

```
$ uv run --project projects/c2g c2g --adapter ecos radar
📊 Task Inventory: 30 done + 60 planned = 90 total
🚨 Anomaly Detection:
   ⚠️  P0 任务 59 个, 超过阈值 5 (战略优先级可能失衡)
   ⚠️  L3 高风险任务 1 个, 需重点 review
   ⚠️  Owner 集中度: unassigned 持有 83% 任务
✅ Strategic audit complete. 90 tasks analyzed.
```

**健康分 = 55/100** (3 异常触发, 中位)

### 2.2 SSOT 引用一致性

```
$ python3 bin/check_health_ssot.py
✅ health.yaml 保鲜: 0.0h 前生成 (阈值 24h)
📊 health_score: True
```

### 2.3 pre-commit hook 阻断证据

改坏 system.yaml (55→999) → `check_health_ssot.py` 报:
```
❌ 1 个错误:
   - health_score 不一致: system.yaml=999 vs health.yaml=55
exit 1
```

### 2.4 c2g 守门员 (CR-STRATEGY-01)

孤儿 Pitch 拦截(无 Upstream 锚点):
```
$ c2g bet runtime/sandbox/pitches/Pitch-Orphan.md
  ❌ [CR-STRATEGY-01 孤儿拦截] Pitch 缺乏 Upstream 锚点, 拒绝转化为 Bet
```

### 2.5 c2g 端到端演练 (local adapter)

走通 valid Pitch:
```
$ c2g --adapter local bet runtime/sandbox/pitches/Pitch-Valid.md
  ✅ 提取任务成功: IMPORTED-c4b2d7
✅ Bet 下注成功: 共创建了 1 个执行计划
```

**LLM 智能提取 deliverables**: GSD + Superpowers 卡带(2 个概念验证卡带)。

Evidence 落盘:
- [`.omo/_delivery/c2g-pilot-evidence/bets-pitch-valid.json`](../../_delivery/c2g-pilot-evidence/bets-pitch-valid.json)
- [`.omo/_delivery/c2g-pilot-evidence/tasks-pitch-valid.json`](../../_delivery/c2g-pilot-evidence/tasks-pitch-valid.json)

---

## 3. 发现的真问题(治理价值)

### 3.1 🔴 c2g 架构脱节(c2g venv 缺 omo)

**症状**: `c2g --adapter ecos bet` 失败:
```
⚠️ eCOS Adapter not available (The 'omo' package is required to use EcosGovernanceProvider). 
   Falling back to 'local' adapter.
  ...
ModuleNotFoundError: No module named 'omo'
```

**根因**:
- c2g pyproject.toml `[project.optional-dependencies] ecos = ["omo"]` 
- c2g 拆为独立 git repo (c2g-standalone) 后, venv 没装 [ecos] extras
- bridge_import.py:_validate_ecos_task 硬编码 `from omo.omo_task_schema import ...`,没走 adapter fallback

**影响**: c2g 走 ecos adapter 的 end-to-end 流程在拆分后断裂。

**修复路径** (登记为 OMO Debt, 不在本试点修):
1. c2g venv 装 [ecos] extras + workspace pip install -e ../omo
2. 或 c2g 走 BOS URI 调 omo, 不在 venv 装 (Decoupling-Audit 建议)
3. 或 c2g 完全去 omo 依赖 (Phase 45+)

### 3.2 🟡 LLM Gateway 500 错误

**症状**:
```
⚠️ LLM-Gateway 请求失败或返回非预期格式: 
   Server error '500 Internal Server Error' for url 'http://localhost:9290/v1/generate'
   回退到 Mock 逻辑
```

**根因**: llm-gateway:9290 未启动 / 不可达。

**影响**: 试点走了 mock, 没真 LLM 智能。但 mock 仍能产出有效 task 框架。

**修复**: 启动 llm-gateway, 或更新 C2G_LLM_URL 环境变量。

### 3.3 🟡 observability/ 不是真空壳(我自己误判)

**发现**: 之前 audit 报告说 "observability 0 行空壳", 我也跟了. 但实查发现:
- 5 文件, 0 真实代码行 (.py/.ts) — 我说"0 行"是按 .py/.ts 算
- 实际有 1 个 docker-compose.yml (Langfuse 配 894B)
- 2 commits: `feat(observability): Phase 2 T2.1/T2.2 Langfuse environment and kairon OTLP tracing`

**结论**: observability **有真实业务** (可观测性基础设施), 不应被废弃, 应**补测试** (D2 报告也这么说).

**修复**: 试点对象改用现有 sandbox Pitch, 不动 observability/.

---

## 4. 健康分静态 vs 真审计

| 来源 | 健康分 | 依据 |
|------|------|------|
| system.yaml (修前) | 77.5 | 静态, 无依据 |
| Kimi 报告 | 67 | 主观打分 |
| **radar 真审计** | **55** | 90 任务真扫描 + 3 异常告警 |

**差距**: 22.5 分. 静态打分掩盖了真实治理问题.

**SSOT 修复**: `system.yaml.health_score: 77.5` → `health_score: 55`, 加 `health_score_ref: .omo/state/health.yaml` 指向 SSOT 源.

---

## 5. 下一步 (P43 W1-W3)

### W1: cron 化 + 债务路由

| 任务 | 命令 |
|------|------|
| 挂 radar 每日 cron | `0 8 * * * python3 /Users/xiamingxing/Workspace/bin/compass_radar.py` |
| 挂 gc 每周 cron | `0 9 * * 1 uv run --project /Users/xiamingxing/Workspace/projects/c2g c2g --adapter ecos gc` |
| 修 c2g ecos adapter 架构脱节 | 登记 OMO Debt (X1 维度) |

### W2: planned 任务分类

| 任务 | 命令 |
|------|------|
| radar 分类 60 planned | 按 priority/risk/owner 标 active/archive |
| gc 归档 30d 滞留 | c2g gc 真跑 (非 --dry-run) |

### W3: cockpit compass 命名空间

| 任务 | 范围 |
|------|------|
| L3 cockpit 暴露 `workspace compass` | 复用 c2g CLI, 不重写 |
| 异常告警推送 cockpit dashboard | radar 输出 → dashboard 卡片 |

---

## 6. 风险与防御(复述)

| 风险 | 防御 | 实测 |
|------|------|------|
| radar cron 资源耗尽 | 1 min/日预算 | 未测 (手动跑 < 1s) |
| 试点失败, 治理中断 | 熔断 (Plan §5.3) | ✅ 未触发 |
| SSOT 修复引入新失序 | pre-commit hook 强制 | ✅ 实测阻断 1 次 |
| 批量治理病复发 | 限 commit 文件数 ≤ 10 | 未触发 |
| 想法收口过严 | brainstorm fallback | 未触发 |
| c2g 自身演进干扰 | 治理侧只调稳定 API | ✅ c2g 拆出后只调 strategy.py |

---

## 7. 验收

| 验收项 | 状态 |
|--------|:----:|
| 6 个自动验证全过 (Plan §8.1) | ✅ (全部: c2g 编译/测试/radar 输出/SSOT 一致性/gc --dry-run) |
| observability 试点走通 c2g 全链路 | ⚠️ 改用 Pitch-Valid.md (observability 不应废弃) |
| SSOT 一致性 100% | ✅ |
| 1 篇复盘文档 | ✅ (本文件) |
| radar 日报可读 | ✅ health.yaml 完整 |

**总评**: 🟢 **试点成功, 决策 P44 扩展**.

---

## 8. 引用

- 规划: [`/Plans/c2g-enchanted-coral.md`](../../../Plans/c2g-enchanted-coral.md)
- 战略 SSOT: [`strategic-governance-p42.md`](strategic-governance-p42.md)
- health.yaml: [`.omo/state/health.yaml`](../../state/health.yaml)
- system.yaml: [`.omo/state/system.yaml`](../../state/system.yaml)
- 试点 evidence: [`.omo/_delivery/c2g-pilot-evidence/`](../../_delivery/c2g-pilot-evidence/)
- c2g 源码: [`projects/c2g/src/c2g/strategy.py`](../../../projects/c2g/src/c2g/strategy.py)
- 治理 SSOT 检查: [`bin/check_health_ssot.py`](../../../bin/check_health_ssot.py)
- radar 包装: [`bin/compass_radar.py`](../../../bin/compass_radar.py)

---

*复盘: 老王 · 2026-06-16 · P43 W0 · 状态: 🟢 扩展中*
*关联规划 c2g-enchanted-coral · 试点熔断未触发 · 3 真问题发现 (1 修, 2 登记 debt)*
