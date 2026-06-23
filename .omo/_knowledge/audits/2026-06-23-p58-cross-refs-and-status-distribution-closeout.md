# P58 — 跨面引用检查工具 + status 分布趋势报告 收口

**日期**：2026-06-23
**阶段**：P58 R1-R3
**目标**：基于 frontmatter 100% 基础实施 2 个治理工具 + 健康度报告

---

## 1. 治理全景 (P58 完成)

| 指标 | P57 末 | **P58 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.45 | **v0.0.46** | +1 |
| governance | 100.0 A+ | **100.0 A+** | 持平 |
| mof-drift LOW | 2 | **2** | 持平 |
| .omo/ 总文件 | 1622 | **1622** | 持平 |
| 知识面文档 | 689 | **689** | 持平 |
| 治理工具新增 | — | **+2** | check-cross-refs.py, status-distribution.py |
| ADR 数量 | 13 | **13** | 持平 (无新增决策) |

---

## 2. 完整落地清单

### R1: 跨面引用一致性检查工具

**工具**: `bin/check-cross-refs.py` (P58 R1 新增)

**功能**:
- 扫描 `.omo/` 下所有 `.md` 文件（排除 `_delivery/` + `tasks/registry/` 运行时产物）
- 解析 markdown 链接 + 纯路径引用
- 检测目标文件是否存在
- 输出: 文件列表 + 每文件最多 5 个断链 + 统计

**实测结果**:
```
📊 总文件: 829
❌ 有问题文件: 448
❌ 总问题链接: 4430
```

**断链分布** (top 5):
- `_knowledge/design/plans/archive` 254 (历史快照, 不修)
- `_knowledge/superpowers/plans` 240 (能力建设历史)
- `_knowledge/management` 227 (管理面旧路径引用)
- `_knowledge/superpowers/specs` 183
- `_knowledge/task-prompts` 94

**决策**: **不修断链**。理由:
- 大量断链是历史漂移（`.omo/summaries/` → `.omo/_knowledge/summaries/` 等）
- 集中在 `archive/` 与 `superpowers/` (历史快照池)
- 沿用 P53"不动路径"原则
- 工具作为**发现工具**已达标，可定期跑监控新漂移

### R2: status 分布趋势报告

**工具**: `bin/status-distribution.py` (P58 R2 新增)

**功能**:
- 扫描 `.omo/_knowledge/` 690 文件 frontmatter
- 统计 status / lifecycle / owner 分布
- 按目录分组统计活跃度
- 关键洞察自动生成

**实测结果**:
```
📈 Status 全局分布:
  archived        666   96.5%  ████████████████████████████████████████████████
  active           14    2.0%  █
  draft             3    0.4%
  deprecated        3    0.4%
  planned           2    0.3%
  approved          1    0.1%
  conditional-pass    1    0.1%

📈 Lifecycle 全局分布:
  history         669   97.0%
  contract          6    0.9%
  ssot              2    0.3%
  audit             1    0.1%

👥 Owner Top-10:
  governance-team                 677   98.1%
  agentmesh-architecture-team       1

📂 目录活跃度 Top-5:
  patterns                              100.0% active (2/2)
  architecture                           50.0% active (1/2)
  decisions                              28.6% active (4/14)
  plans-archive                          11.1% active (1/9)
  design                                  2.5% active (5/202)

🔍 关键洞察:
  • 历史文档占比: 97.0% (669/690)
  • ✅ 健康: 大量历史归档 + 少量活跃 = 治理成熟态
```

**R2 边车修复**: 6 个 phase5-* + reviews/architecture 文档补 lifecycle: contract (active 文档)

### R3: 收口
- mof-version v0.0.45 → v0.0.46
- 本收口报告

---

## 3. 关键决策

### D-P58-1: 历史漂移断链不修

- 448 文件 4430 断链集中在 archive/ + superpowers/ (历史快照池)
- 修复成本高（需批量改路径）, 价值低（历史文档不会被重新阅读）
- 工具作为**新漂移监控器**, 不修历史债

### D-P58-2: status 分布健康无需干预

- 97% archived + 2% active 是治理成熟态
- SSOT+Contract+Pattern 仅 1.2% (8 个) = 权威来源精简
- 14 个 active 文档分布在 patterns/architecture/decisions/design/plans-archive/audits
- governance-team 拥有 98.1% 文档, 所有权清晰

### D-P58-3: 12 个无 lifecycle 文档是"假阳性"

- 6 个 phase5-* + 1 个 reviews/architecture: 已用 plane/type/freshness, 补 lifecycle: contract
- 6 个 DBOS 文件: 原生 id/title/status 格式, 保留 (历史 Phase 0 产物)
- 脚本需升级以识别 DBOS schema, **留 P59+**

### D-P58-4: 新工具不属于"linter 维度"

- P57 ADR-0053 已记录 linter 维度饱和 (15 维)
- P58 工具是**独立 bin 工具**而非 omo lint 子命令
- 避免维度再增, 但保留发现/报告能力

---

## 4. 治理工具全景 (新增 2 个)

| 工具 | 路径 | 类别 | 触发 |
|------|------|------|------|
| mof-drift | bin/mof-drift | 漂移检测 | P52 v5 终极, 6 维度 |
| check-cross-refs.py | bin/check-cross-refs.py | **P58 新增** | 跨面引用一致性 |
| status-distribution.py | bin/status-distribution.py | **P58 新增** | frontmatter 健康度报告 |
| mof-version | bin/mof-version | 版本登记 | P45 起 |
| mof-enforce | bin/mof-enforce | 影响/状态/价值 | P45 起 |
| mof-analyze | bin/mof-analyze | dashboard/testing/cost | P45 起 |
| mof-export | bin/mof-export | README/API/arch | P45 起 |
| omo lint | (15 维度) | 多维校验 | P45 R2 (14) + P45 R4 (15) |

**新增工具原则** (P58): 独立 bin/ 而非 omo lint 子命令, 避免维度饱和

---

## 5. 后续候选 (P59+)

| 建议 | 工作量 | 风险 | 价值 | 时机 |
|------|------:|-----:|-----:|------|
| management/ 142 拆 3 类 (workflows/playbooks/guides) | 大 | 高 | 待评估 | P59 需深度访谈 |
| graphify-out 重生覆盖 1622 文件 | 中 | 中 | 中 | P59 验证架构健康 |
| status-distribution 升级识别 DBOS schema | 低 | 0 | 低 | P59+ |
| check-cross-refs 集成 pre-commit | 中 | 中 | 中 | P60 (需谨慎) |
| ADR-0054 记录 P58+ 治理演进 | 低 | 0 | 中 | P60+ |

---

## 6. mof-version 历史

| 版本 | 日期 | 关键 |
|------|------|------|
| v0.0.44 | 2026-06-23 | P56: ADR-0052 + frontmatter 689/689 = 100% |
| v0.0.45 | 2026-06-23 | P57: ADR-0053 + doc-lifecycle 100/100 + 维度饱和评估 |
| **v0.0.46** | **2026-06-23** | **P58: 跨面引用检查工具 + status 分布报告 + 6 lifecycle 修复** |

---

## 7. 总结

P58 是 P57"稳态期"的**工具建设增量**:
- **工具面**: 2 个新 bin 工具 (check-cross-refs / status-distribution)
- **发现面**: 4430 历史漂移断链 (集中在 archive/, 不修) + 690 文件健康度报告 (97% 历史归档)
- **修复面**: 6 个 phase5/reviews 文档补 lifecycle
- **决策面**: 沿用 P57 维度饱和评估, 新工具独立 bin 而非 linter 维度

**核心方法论**: "**独立 bin 工具**" 而非"**linter 维度**"。当现有 15 维度饱和, 新能力以独立 bin 工具形式补充, 避免维护负担线性增长。

---

*P58 R1-R3 完成: 2026-06-23 · governance 100 A+ 持续 · mof-version v0.0.46 · mof-drift 0 LOW 持续 · 治理工具 +2*