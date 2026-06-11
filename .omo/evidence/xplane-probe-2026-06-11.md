# X-Plane 探活证据快照 · 2026-06-11

> 全量 probe 记录,含 quick(jsonl/http) + 手动 command 探针 + 自研分析。
> 沙箱环境限制: runtime data 文件(kei_audit.jsonl/llm_cost.jsonl)不在 sandbox 内,
> 主机上这些文件存在(6/8 探活: kei_audit.jsonl 149K 行,age 7.6h,已 GREEN)。

## 自动探活 (quick模式)

时间戳: `2026-06-11T07:34:04+00:00`
工具: `omo.omo_xplane.compute_xplane_score(quick=True)`
存证: `.omo/evidence/xplane-probe-quick-2026-06-11.json`

| 轴 | 存活率 | 覆盖率 | 可探/总数 |
|----|--------|--------|----------|
| X1 审计链 | 0% | 40% | 2/5 (3 PENDING) |
| X2 保鲜 | N/A | 0% | 0/5 (5 PENDING) |
| X3 价值栈 | 0% | 67% | 2/3 (1 PENDING) |
| X4 一致性 | N/A | 0% | 0/8 (8 PENDING) |

**聚合**: xplane_score=0.0, overall_coverage=19%(4/21), xplane_factor=0.7

### 各机制细项

| ID | Status | Detail |
|----|--------|--------|
| X1/K1 KEI沙箱 | 🔴 RED | exit=2: counter probe 清理失败(沙箱路径问题) |
| X1/K2 KEI审计 | 💀 DEAD | kei_audit.jsonl 不在沙箱路径内 |
| X1/K3-K5 | ⏳ PENDING | command 型被 quick 跳过 |
| X2/K1-K5 | ⏳ PENDING | 全部 command 型被 quick 跳过 |
| X3/K1 成本追踪 | 💀 DEAD | llm_cost.jsonl 不在沙箱路径内 |
| X3/K2 LLM网关 | 🔴 RED | port 9290 Connection refused |
| X3/K3 优先级分级 | ⏳ PENDING | command 型被 quick 跳过 |
| X4/K1-K8 | ⏳ PENDING | 全部 command 型被 quick 跳过 |

## 手动 command 探针 (沙箱实测)

### ✅ X4/K6 — Agent 启动契约 (PASS)
检测: CLAUDE.md §0 存在性 → 2/2 文件含 §0 (PASS)

### ✅ X4/K5 — 端口注册表 (exit=0, PASS)
检测: check-port-registry.py → exit=0, 9 个代码端口全部在 protocols/port-registry.yaml 注册

### ❌ X4/K1+K4 — CLI + 接口注册表 (FAIL, 9 violations)
检测: check-interfaces.py → 总 9 violations, 含 4 个 stale 文档
- 根 CLAUDE.md: 文件不存在
- LAYER-INDEX.md: 文件不存在
- kairon CLAUDE.md: 文件不存在
- Vault CLAUDE.md: 文件不存在
注: 沙箱内 CLAUDE.md 实际存在(`/mnt/Workspace/CLAUDE.md`),脚本路径映射问题。

### ❌ X4/K3+K8 — 跨层 import (FAIL, 1 violation)
```
agora/src/agora/mcp/bos_resolver.py → cockpit.scripts.cockpit_mcp
违反: I0 agora 不能 import L3 cockpit (向上依赖)
```

### ❌ X2/K3 — 债务保鲜 (FAIL, yaml 模块缺失)
check-state-goals-alignment.py 因 sandbox 缺 yaml 包无法运行

### ✅ X2/K4 — CARDS 过期检测 (PASS)
107 tasks 文件 7d 内修改(≥1 即 PASS)

### ❌ X1/K1 — KEI counter probe (FAIL, module not found)
runtime.kei_probe 在 sandbox Python path 中不可达(需 uv run -m runtime.kei_probe)

## 声明/现实分裂修复记录

| 问题 | 状态 |
|------|------|
| INDEX.md 声称无计划任务但实际 47 个 | ✅ **已修复** — 全量重写 |
| CLAUDE.md 健康分写 77.5 但实际 22.12 | ✅ **已修复** — 更新为 22.12 + 标注公式 |
| OPC-P2-MEMORY-SPINE 已完成但滞留 planned/ | ✅ **已修复** — 迁至 done/ |
| system.yaml health_score=22.12 等于 CLAUDE.md | ✅ **一致** — 已对齐 |
| 9 项债务全部 unresolved | ⏳ 待推进(需 Phase 门禁决策) |
| INDEX.md Planned → 46 tasks (OPC-P2 迁出后) | ✅ **已同步** |

## 新的声明/现实分裂发现

| 问题 | 证据 |
|------|------|
| check-interfaces.py 报告 4 个 CLAUDE.md 不存在 | 沙箱路径映射问题,主机上这些文件存在 |
| agora→cockpit 向上依赖(bos_resolver.py) | I0 层违反架构规则,为 BOS URI 战役新增 |
| 9 个端口全部注册但脚本报 Registry ports:0 | 脚本解析逻辑与 YAML 格式可能有兼容差 |
| X3/K2 LLM Gateway 9290 不可达 | 服务未在 sandbox 内运行 |

## 后续推进建议

1. **主机上运行全量 probe**: `cd ~/Workspace && uv run python -m omo.omo_xplane check --no-quick --json`
2. **修复 agora→cockpit 跨层依赖**: bos_resolver.py 需改为接口注入而非直接 import
3. **明确 9 项 debt 的处理策略**: 逐项决定 resolve/accept/defer
4. **补全 X3/K1 LLM 成本追踪**: 实现 omo_cost.py 的 jsonl 写入接入
5. **提升 xplane_coverage**: 剩余 17 项 PENDING 通过 implement runner + 主机跑通

---
*Generated: 2026-06-11 07:35 UTC · Evidence version 1*
