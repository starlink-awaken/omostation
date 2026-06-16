# C2G 机制驱动的 omostation 全链路治理规划

> **代号**:c2g-enchanted-coral
> **日期**:2026-06-16
> **范围**:omostation 整体治理(战略 / 治理 / 任务 三维)
> **机制骨干**:c2g 五原语(brainstorm / draft / bet / radar / gc)
> **规划形态**:全链路规划 + P43 试点

---

## 0. Context — 为什么要做

### 0.1 老王的问题陈述(暴躁版)

omostation 当前**治理空转**:
- 🔴 **SSOT 失序**:`health_score` 在 system.yaml 写 77.5,CLAUDE.md 写 22.12,Kim 报告写 67。同一指标三个值
- 🔴 **任务淤积**:0 active / 61 planned / 61 done,planned 长期 0 流转
- 🔴 **债务空转**:8 个 seed debt 排队,无 owner 路由
- 🟡 **批量治理病**:18/18 项目最新 commit 都是"docs: add architecture, callchain, and boundary documentation"模板化
- 🟡 **空壳占位**:`observability/`(0 行)、`agora-dashboard/`(172 行)活着但没业务

### 0.2 关键洞察:c2g 已是"已就绪"的治理引擎

老王我深读 c2g 后发现一个被低估的事实:

| c2g 机制 | 当前能力 | 治理价值(被低估的) |
|---------|---------|------------------|
| **brainstorm** | 触发 MetaOS 发散 | 战略想法收口(可治 planned 淤积) |
| **draft** | 交互式向导生成 Pitch.md | 想法 → 结构化提案的桥 |
| **bet** | Pitch → OMO Task | 战略落地的唯一通道(已有 M2 防腐层) |
| **radar** | 真审计 .omo/tasks/ 4 类异常告警 | **替代 Phase 推进健康分聚合** |
| **gc** | 28 天阈值清理滞留 Pitch | **替代债务堆积治理** |

**核心论点**:c2g 已经实现了 omostation 治理需要的 5 个原子操作,但**只被用作"需求转任务"的窄工具**。本规划把它的覆盖面扩展到**整个治理循环**。

### 0.3 不重复造轮(DRY)

`.omo/standards/C2G-Decoupling-Audit.md` 已建议:
- 短期 (Phase 43):cockpit 实现 `workspace compass` 命令簇
- 中期 (Phase 44):抽离 omo_bridge + omo_strategy,新建 `projects/compass`
- 远期:通用化,对外开源

**本规划不冲突,而是补充**:Decoupling-Audit 关注 c2g 自身的形态(独立项目),本规划关注 c2g 的**应用面**(治理循环)。

---

## 1. 现状基线(Base Line)

### 1.1 治理运行数据(实读)

```
$ yq '.current_phase, .health_score, .completed_tasks, .active_tasks, .blocked_tasks' \
    .omo/state/system.yaml
42          # current_phase
77.5        # health_score
30          # completed_tasks
0           # active_tasks
0           # blocked_tasks

$ ls .omo/tasks/{drafts,planned,done}/*.yaml | wc -l
0 drafts + 61 planned + 61 done

$ ls .omo/debt/items/*.yaml | wc -l
8 seed debt items (DEBT-C2G-BRIDGE-M2, DEBT-L4-KERNEL-20260614, ...)
```

### 1.2 c2g 健康度(实读)

```
$ cd projects/c2g && uv run pytest tests/ -q
.....                                                            [100%]
5 passed in 0.20s   ✅ 健康

$ python -m py_compile src/c2g/*.py   # 全部通过,无 IndentationError
✅ (前 audit 报告的"Broken"已修复,Round 43 P1 修真)
```

### 1.3 治理基线差距(Gap)

| 维度 | 当前 | 目标 | Gap |
|------|------|------|-----|
| SSOT 一致性 | 3 份文档 3 个 health 值 | 1 源 1 值 | 🔴 高 |
| planned 流转率 | 0%(61 个全淤) | >30%/月 | 🔴 高 |
| debt owner 路由 | 0/8 已路由 | 100% | 🔴 高 |
| radar 调用频率 | ad-hoc | 每日 1 次 | 🟡 中 |
| gc 调用频率 | 0 次 | 每周 1 次 | 🟡 中 |
| 战略想法收口 | 散落各处 | 100% 走 brainstorm | 🟡 中 |

---

## 2. 治理目标(三维)

### 2.1 战略维度(Strategy)
**目标**:把 c2g brainstorm/draft 升级为 omostation 战略想法的**唯一入口**
- 任何"想做一个新东西"必须先走 `workspace compass brainstorm` 或 `compass draft`
- 产出物统一落在 `runtime/sandbox/pitches/`
- 模板遵循 `.omo/standards/PITCH-TEMPLATE-C2G.md`(已存在)
- **不要让想法散落 CLAUDE.md / WPS / 微信** —— 治理最痛的就是收不上来

### 2.2 治理维度(Governance)
**目标**:把 c2g radar/gc 升级为 omostation 治理循环的**自动心跳**
- radar 每日 cron 调用,自动生成治理日报
- gc 每周 cron 调用,自动清理 28 天以上滞留 Pitch
- 异常告警(P0 堆积 / L3 风险 / Owner 集中 / 7d 停滞)实时推送
- **替代当前的"人肉 phase 推进"模式** —— 用机器审计代替文档刷数

### 2.3 任务维度(Tasks)
**目标**:把 c2g bet 标准化为 omostation 任务沉淀的**唯一通道**
- planned 淤积 61 个 → 走 radar 分类 → gc 清理僵尸 → bet 重新下注活跃
- 每条 bet 必须有 upstream 锚点(CR-STRATEGY-01 拦截)
- 每条 bet 必须有 deliverables 文件路径(`.omo/standards/task-yaml-rules.md` 规则 1)
- **关闭 0 active 的"伪稳态"** —— 流转起来才是真稳态

---

## 3. c2g 五机制 × 治理环节映射(核心)

| 治理环节 | 现状(无 c2g) | 目标(用 c2g) | 接入点 |
|---------|-------------|-------------|--------|
| **想法来源** | 散落(微信/WPS/CLAUDE.md) | `compass brainstorm` | L3 cockpit |
| **提案结构化** | 无模板 | `compass draft` → Pitch.md | L3 cockpit |
| **战略下注** | 手动写 YAML 任务 | `compass bet` → OMO Task | L2 omo |
| **周期审计** | 文档刷 phase | `compass radar` (每日 cron) | L2 c2g.strategy |
| **熵减清理** | 无 | `compass gc` (每周 cron) | L2 c2g.strategy |
| **债务治理** | registry 静态 | radar 异常 → 路由 owner → gc 归档 | L2 omo-debt |
| **健康分聚合** | 文档多源 | radar 唯一指标源 | L2 c2g.strategy |
| **Phase 推进** | 人肉刷 | radar 全绿 + 0 异常 → 自动推进 | L2 omo |

### 3.1 关键:radar 替代 health_score

**现状问题**:`health_score` 在 3 处不同值,谁都不权威。

**改造方案**:
```bash
# 单一权威:c2g radar 的输出 → .omo/state/health.yaml
compass radar --output .omo/state/health.yaml

# system.yaml 只引用,不计算
health_score_ref: ".omo/state/health.yaml"

# pre-commit hook:任何 commit 校验 .omo/state/health.yaml < 24h
```

### 3.2 关键:gc 替代 debt 堆积

**现状问题**:8 个 debt 排队,无 owner。

**改造方案**:
```bash
# 每日:radar 异常 → 自动转 debt
compass radar --anomalies-to-debt

# 每周:gc 清理 28d 滞留 debt
compass gc --debt-threshold 28d
```

---

## 4. 实施路线(3 阶段)

### Phase A:P43 W0 试点(2 周,本周可启动)

**目标**:跑通 c2g 全链路,产出实证 evidence

| 任务 | 命令 | 验收 |
|------|------|------|
| 修 c2g CLI 在 L3 cockpit 的别名 | `cd projects/cockpit && uv add c2g` | `workspace compass --help` 可用 |
| 把 radar 接入每日 cron | `crontab -e: 0 8 * * * compass radar >> .omo/state/health.log` | 日报生成 |
| 把 gc 接入每周 cron | `0 9 * * 1 compass gc --debt` | 滞留 Pitch 归档 |
| 试点 1 个 Pitch 走完整链路 | brainstorm → draft → bet → radar → gc | 任务落 .omo/tasks/done/ |
| 修复 SSOT 失序 | `health_score_ref` 指向 radar 输出 | pre-commit 阻断 |

**试点候选**:`observability/` 0 行空壳 → 走 c2g brainstorm"是不是该保留?不该就走 gc 归档"。

### Phase B:P43-P44 扩展(4 周)

| 任务 | 范围 |
|------|------|
| `workspace compass` 命名空间落地 cockpit | L3 统一入口 |
| radar 输出写为 SSOT | 替代 system.yaml 静态 health |
| 异常告警推送 cockpit dashboard | 实时可视化 |
| planned 淤积清理(61 → 30) | radar 分类 + gc 归档 |
| debt owner 路由 100% | registry 全路由 |
| 空壳项目清理 | observability / spaces / agora-dashboard 处置 |

### Phase C:P45+ 常态化(2 个月)

| 任务 | 范围 |
|------|------|
| compass 项目独立化 | 沿 C2G-Decoupling-Audit 中期方案 |
| c2g 通用化 | 走 venv 即可用,无 eCOS 依赖 |
| 治理自动化 | radar + gc 完全 cron 化,人肉治理 0 |
| 战略雷达 → 业务雷达 | radar 数据反哺 roadmap |

---

## 5. P43 W0 试点详细设计

### 5.1 试点对象:`observability/` 0 行空壳治理

**为什么选它**:
- 症状最典型(0 行代码还活着)
- 走 c2g 全链路风险低
- 产出可观察(归档前后对比)

**步骤**:

```bash
# 1. brainstorm:是否保留 observability?
workspace compass brainstorm "observability 0 行空壳,是否保留?"

# 2. draft:生成 Pitch.md
workspace compass draft
# → 输出:runtime/sandbox/pitches/Idea-observability-废弃.md
# 内容:Upstream=治理清洁, Appetite=2h, NoGos=不允许补代码

# 3. bet:战略下注
workspace compass bet runtime/sandbox/pitches/Idea-observability-废弃.md
# → 拦截:upstream 已声明,放行
# → 落 OMO Task:归档 observability + 更新 .gitignore

# 4. 执行(走 OMO 任务流)
# → .omo/tasks/planned/IMPORTED-xxxxx.yaml 自动创建
# → done 后迁到 .omo/tasks/done/

# 5. radar:审计
workspace compass radar
# → 异常告警:之前 L3 risk 任务 -1 (空壳治理任务本身 L0)

# 6. gc:下次自动清理
workspace compass gc --dry-run
# → 显示 28d 后归档的旧 Pitch(本次新增不在范围)
```

### 5.2 试点验收(必须 evidence)

- [ ] `.omo/tasks/done/IMPORTED-{hash}.yaml` 存在
- [ ] `projects/observability/` 已删(或 .gitignore 永久忽略)
- [ ] `.omo/state/health.yaml` 由 radar 生成,system.yaml 引用
- [ ] pre-commit hook 已配置
- [ ] 1 篇复盘文档写入 `.omo/_knowledge/retrospectives/2026-06-XX-p43-c2g-pilot.md`

### 5.3 试点失败定义(熔断)

如果以下任一发生,立即停手:
- 🔴 radar 跑不通 / 报错
- 🔴 bet 落 OMO 任务后,任务走不到 done
- 🔴 SSOT 修复引入新失序源

---

## 6. 战略文档草案(附录 — 落 .omo/_truth/goals/)

> **本节是 plan mode 期间的草案**,实施时由 pilot lead 写入
> `.omo/_truth/goals/strategic-governance-p42.md`(SSOT)

```markdown
# 战略治理规划:从 Phase 42 到 45

## 北极星(North Star)
让 omostation 治理从"文档刷数"转向"机器审计 + 收口想法"。

## 战略 Bets(P0-P3)

| ID | Bet | 价值向量 | Appetite | Upstream |
|----|-----|---------|---------|----------|
| BET-COMPASS-01 | cockpit `compass` 命名空间落地 | V1 效率 | 1 周 | 本规划 |
| BET-RADAR-CRON | radar 每日 cron + 健康分 SSOT | V1 效率 | 3 天 | BET-COMPASS-01 |
| BET-GC-CRON | gc 每周 cron + 债务路由 | V2 自治 | 3 天 | BET-RADAR-CRON |
| BET-PLANNED-CLEANUP | 61 planned → 30 | V1 效率 | 2 周 | BET-GC-CRON |
| BET-COMPASS-STANDALONE | c2g 独立化为 projects/compass | V2 自治 | 1 月 | 全部前置 |

## 关键决策(不可逆)
1. SSOT 唯一源 = radar 输出(.omo/state/health.yaml)
2. 任何想法必须走 compass brainstorm/draft
3. 任何任务必须走 compass bet
4. Phase 推进 = radar 全绿 + 0 异常(自动)

## 风险
- 试点失败 → 退回 Phase 42 现状,损失 2 周
- radar cron 资源消耗 → 控制在 1 min/日
- 治理反噬 → 设置熔断:异常告警 > 10/日 暂停 cron
```

---

## 7. 关键文件清单(实施时改动)

### 7.1 新建
| 路径 | 作用 |
|------|------|
| `projects/cockpit/src/cockpit/commands/compass.py` | L3 `workspace compass` 命令簇 |
| `.omo/state/health.yaml` | radar 输出 SSOT |
| `.github/workflows/c2g-radar-daily.yml` | radar cron workflow |
| `.github/workflows/c2g-gc-weekly.yml` | gc cron workflow |
| `.omo/_knowledge/retrospectives/2026-06-XX-p43-c2g-pilot.md` | 试点复盘 |
| `.omo/_truth/goals/strategic-governance-p42.md` | 战略 SSOT |

### 7.2 修改
| 路径 | 改动 |
|------|------|
| `projects/cockpit/pyproject.toml` | `uv add c2g` |
| `.omo/state/system.yaml` | `health_score` 字段改为 `health_score_ref: ".omo/state/health.yaml"` |
| `.omo/standards/C2G-Decoupling-Audit.md` | 引用本规划,标注"应用面"补全 |
| `.pre-commit-config.yaml`(根) | 新增 c2g radar SSOT 一致性检查 |

### 7.3 删除(试点阶段)
| 路径 | 原因 |
|------|------|
| `projects/observability/` | 0 行空壳,试点目标 |
| `projects/spaces` 符号链接 | 治理反模式(若试点通过) |

### 7.4 复用(DRY)
| 路径 | 复用方式 |
|------|---------|
| `projects/c2g/src/c2g/strategy.py` | radar / gc 直接调用,不重写 |
| `projects/c2g/src/c2g/bridge_import.py:_import_pitch` | bet 流程 |
| `.omo/standards/PITCH-TEMPLATE-C2G.md` | 战略 Pitch 模板(已存在) |
| `.omo/standards/task-yaml-rules.md` 规则 1-7 | 任务 YAML 硬规则(已存在) |
| `.omo/_knowledge/management/governance-charter-v1.md` §3 | X1/X2/X3 债务分类 |
| `projects/omo-debt/src/omo_debt/` | debt owner 路由复用 |

---

## 8. 验证方案(End-to-End)

### 8.1 自动化验证(每日 cron 跑)

```bash
# 1. 编译验证(c2g 健康)
cd projects/c2g && python -m py_compile src/c2g/*.py

# 2. 单元测试
cd projects/c2g && uv run pytest tests/ -q

# 3. radar 输出验证
compass radar --output .omo/state/health.yaml
yq '.health_score' .omo/state/health.yaml  # 数字格式
yq '.anomalies | length' .omo/state/health.yaml  # ≤ 5

# 4. SSOT 一致性
diff <(yq '.health_score' .omo/state/system.yaml) \
     <(yq '.health_score' .omo/state/health.yaml)
# 期望:无输出(一致)

# 5. gc 干跑
compass gc --dry-run
# 期望:扫描数 ≥ 0
```

### 8.2 端到端验证(每周人肉跑)

```bash
# 1. 跑通 c2g 全链路(以 observability 治理为试点)
compass brainstorm "..."
compass draft
compass bet runtime/sandbox/pitches/Idea-*.md
# → 检查 .omo/tasks/done/ 有新条目

# 2. cockpit 入口验证
workspace compass --help
workspace compass radar
# → 与直接调 c2g 等价

# 3. cron 触发验证
gh workflow run c2g-radar-daily.yml
gh workflow run c2g-gc-weekly.yml
# → 检查 .omo/state/health.log 有新条目
```

### 8.3 验收标准(Definition of Done)

**P43 W0 试点验收**:
- ✅ 6 个自动验证全过
- ✅ observability 试点走通 c2g 全链路
- ✅ SSOT 一致性 100%
- ✅ 1 篇复盘文档
- ✅ radar 日报可读(可在 cockpit dashboard 看到)

**P44 扩展验收**:
- ✅ planned 任务数 < 30
- ✅ debt owner 路由 100%
- ✅ cockpit `compass` 命名空间上线
- ✅ 异常告警自动推送

**P45 常态化验收**:
- ✅ compass 项目独立(沿 Decoupling-Audit 中期方案)
- ✅ 人肉治理操作 0 次/周
- ✅ Phase 推进 = radar 自动化
- ✅ 治理效率指标:想法到 done < 14 天

---

## 9. 风险与防御

| 风险 | 概率 | 影响 | 防御 |
|------|:---:|:---:|------|
| radar cron 资源耗尽 | 中 | 中 | 控制在 1 min/日,超阈值熔断 |
| 试点失败,治理中断 | 中 | 高 | 熔断机制(§5.3),失败退回 |
| SSOT 修复引入新失序 | 高 | 中 | pre-commit hook 强制 |
| 批量治理病复发 | 中 | 中 | 限制一次性 commit 文件数 ≤ 10 |
| 想法收口过严,创新窒息 | 中 | 中 | brainstorm 失败可 fallback 自由写 |
| c2g 自身演进干扰治理 | 低 | 高 | c2g 走独立版本,治理侧只调稳定 API |
| Phase 推进自动化误判 | 低 | 高 | 异常告警 > 5 时暂停自动推进 |

---

## 10. 老王总评(暴躁版)

**这份规划做了什么**:
- 把 c2g 5 机制从"窄工具"升级为"治理循环骨干"
- 给当前 3 份 SSOT 失序 / 61 planned 淤积 / 8 debt 空转开了药方
- P43 2 周可启动,失败有熔断
- 复用 7 个已有资产(0 重复造轮)

**这份规划没做什么**:
- 没让 c2g 独立化(那属于 Decoupling-Audit 范围,本规划是应用面)
- 没立即让 compass 项目独立(P45 之后)
- 没动 gbrain 32 万行 TS 代码(超出范围)

**老王暴躁总结**:
> 别再写元文档了,别再刷 phase 了。c2g 已经写好了,把 radar 跑起来,gc 跑起来,planned 流转起来 —— 这就完事了。

---

## 11. 后续路径(规划批准后)

1. **Day 0**:用户批准本规划
2. **Day 1**:P43 W0 启动,挂 radar/gc cron(试点准备)
3. **Day 2-3**:observability 试点走 c2g 全链路
4. **Day 4-7**:SSOT 修复 + pre-commit hook
5. **Day 8-10**:复盘 + P43 W1 决策(扩展 or 退回)
6. **Day 14**:P43 W0 验收,产出 1 篇复盘 + 1 份 SSOT 战略文档

---

## 附录 A:关键参考文件

- `.omo/_knowledge/management/governance-charter-v1.md` — 5+3+1 宪章
- `.omo/standards/PITCH-TEMPLATE-C2G.md` — Pitch 模板
- `.omo/standards/task-yaml-rules.md` — 任务 YAML 7 规则
- `.omo/standards/C2G-Decoupling-Audit.md` — c2g 独立化方案(本规划互补)
- `projects/c2g/src/c2g/strategy.py` — radar/gc 真实实现
- `projects/c2g/src/c2g/bridge_import.py` — bet 流程
- `projects/c2g/src/c2g/ports.py` — 适配器接口
- `docs/ARCHITECTURE-ANALYSIS-REPORT.md` — Kimi 报告(批判参考)

---

*规划者:老王(老王暴躁技术流) · 2026-06-16 · 状态:DRAFT*
*基于 c2g 5 机制 · 试点 P43 W0 · 失败熔断 · 复用 0 造轮*
