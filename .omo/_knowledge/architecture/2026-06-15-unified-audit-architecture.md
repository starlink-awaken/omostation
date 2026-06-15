# 统一审计架构 (Round 43 P1 整合)

**日期**：2026-06-15
**目标**：整合分散在 omo/cockpit/agora/c2g/ecos 的审计能力，建立**统一审计入口**
**关联审计**：`.omo/_knowledge/audits/2026-06-15-c2g-deep-audit.md` (4.6/10 D+)

---

## 0. 现状 (现有审计能力分散)

| 工具 | 项目 | 角色 | 入口 |
|---|---|---|---|
| omo governance | omo | 治理巡检 6 项 | `omo governance` |
| omo lint yaml-bypass | omo | .omo/debt/items/ 越权 | `omo lint yaml-bypass` |
| omo-debt report | omo | 债务报告 cascade | `omo-debt report` |
| cockpit product-health | cockpit | 产品健康 | `cockpit product-health` |
| cockpit ssb / mof | cockpit | L0 协议 | `cockpit ssb / mof` |
| agora audit | agora | 操作日志 | `agora audit --since 7d` |
| c2g radar | c2g | **🟡 修真前 mock** | `c2g radar` |
| ecos MOF | ecos | L0 协议层 | (CLI 通过 cockpit) |

**问题**：
1. 入口分散（5+ 个 CLI 各自独立）
2. 报告格式不统一（omo governance 返 markdown，c2g radar 返 print，cockpit 返 JSON）
3. **c2g radar 是 mock**（硬编码 V1 60% / V2 40%，没真审计）

---

## 1. 架构设计：统一审计 CLI

### 1.1 入口设计

**新文件**：`/Users/xiamingxing/Workspace/bin/workspace-audit`

**调用方式**：
```bash
workspace-audit                          # 6 维度全跑
workspace-audit --dim governance         # 只跑 governance 维度
workspace-audit --dim radar              # 只跑 c2g radar (修真)
workspace-audit --dim ssot               # 只跑 SSOT 一致性
workspace-audit --format json           # JSON 输出
workspace-audit --output report.md       # 写报告到文件
```

### 1.2 6 维度系统化

| # | 维度 | 调用 | 输出 |
|---|---|---|---|
| 1 | **omo governance** | `omo governance` 抓总分 | 100 (A+) |
| 2 | **omo lint yaml-bypass** | `omo lint yaml-bypass` | 0 issue / N issue |
| 3 | **c2g radar**（修真） | `c2g radar` (修真后) | 真实指标分布 + 异常 |
| 4 | **治理 SSOT 一致性** | 自实现：读 CLAUDE.md/AGENTS.md/README.md/INDEX.md mtime + 关键关键字 | stale_files list |
| 5 | **子项目 gitlink 同步** | `git submodule foreach` + 远端对比 | ahead/behind per module |
| 6 | **agora 操作审计** | `agora audit --since 7d --stats` | 最近 N 条操作 |

### 1.3 输出格式

```markdown
# Omostation Workspace Audit Report
**日期**：2026-06-15 16:00
**总分**：98.5 / 100 (A+)

| 维度 | 分数 | 状态 |
|---|---|---|
| 1. omo governance | 100 | ✅ A+ |
| 2. omo lint yaml-bypass | 100 | ✅ 0 issue |
| 3. c2g radar (修真) | 95 | ✅ 6 active bet V2 + 异常告警 |
| 4. SSOT 一致性 | 90 | 🟡 2 stale file (DESIGN.md / ARCHITECTURE.md) |
| 5. 子项目 gitlink | 100 | ✅ 14 modules in sync |
| 6. agora 操作审计 | 95 | ✅ 127 ops in 7d, 0 error |

## 详细发现
- ...
## 建议
- ...
```

### 1.4 修真 c2g radar (P0)

**当前 mock 问题**：
- `strategy_audit` 硬编码 "V1 60% / V2 40%"
- 真调用 `get_active_bets()` 但 `.omo/tasks/done/*.yaml` **没 vector 字段** —— 永远返 0 0
- 修真 = 用真实指标（priority / risk_level / owner 分布）+ 异常告警

**修真后实现**（已 Round 43 P1 落地）：
- 读 `.omo/tasks/{done,planned}/*.yaml` 真数据（30+ done, 多个 planned）
- 统计 priority / risk_level / owner / phase / status 5 类 Counter
- 异常检查：P0 > 5、L3 > 0、owner 集中 > 50%、7d 内 0 done
- 输出真实指标 + 异常告警

---

## 2. 实现路径

### 2.1 Phase 1: 修真 c2g radar (P0) ✅
- Edit `projects/c2g/src/c2g/strategy.py:strategy_audit` 修真
- 跑 `python3 -m c2g.strategy audit` 验证真数据
- 根仓 commit `projects/c2g/src/c2g/strategy.py`

### 2.2 Phase 2: bin/workspace-audit (P1)
- 新建 `bin/workspace-audit` (Python 脚本)
- 6 维度系统化
- markdown + JSON 双输出
- 跑一次验证

### 2.3 Phase 3: 文档同步 (P2)
- 根仓 CLAUDE.md / AGENTS.md 加 workspace-audit 文档
- LAYER-INDEX.md 加审计层说明
- ARCHITECTURE.md 加统一审计架构图

---

## 3. 跟 X1-X4 治理轴的关系

| 维度 | 对应治理轴 |
|---|---|
| omo governance | X4 一致性（总分）|
| omo lint yaml-bypass | X1 审计链（status 字段越权）|
| c2g radar (修真) | X3 价值栈（战略 vector 分布）|
| SSOT 一致性 | X4 一致性（文档同步）|
| 子项目 gitlink | X4 一致性（submodule 同步）|
| agora audit | X1 审计链（操作日志）|

---

## 4. 风险 + 边界

- **执行时间**：6 维度串行跑约 5-10 秒（git submodule foreach 慢）
- **输出大小**：markdown 报告 ~50KB（含 30 个 done task 列表）
- **mock 残留**：修真前 strategy_gc 也是 mock（line 31-40 注释 "we'll just mock the GC scan output"）—— **修真后已修真**：strategy_gc 修真为读 sandbox/pitches/ 真 mtime
- **OMO 钩子持续 auto-loop**：6 维度跑出来时数据可能跟上次不一样（不是 bug，是 governance 期望）

---

## 5. 验收标准

- ✅ 修真 c2g radar 跑出真实指标（不是硬编码 60%/40%）
- ✅ workspace-audit 6 维度全跑
- ✅ 总分 ≥ 95 (A+)
- ✅ 输出 markdown 报告含具体建议
- ✅ 修真后 c2g 拆独立可带修真 commit
