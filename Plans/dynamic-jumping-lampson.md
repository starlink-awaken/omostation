# ADR-0443 v2 迭代 — 观测质量闭环 + 风暴拆弹

> Grilling 两场 8 决策全定案。v1 骨架（#2744）验证"观测先于治理"；v2 让观测数据
> 变干净变自动，并完成第一次真实减法。

## Context

v1 首跑抓到三问题：escape 台账 33/70 条 `unspecified`（查明=CI_LOCAL_SKIP 预检全绿
时的占位写入，全 shadow/would_block=false，纯噪声非真豁免）；gate-roi 判 PRUNE×2
未执行（查明=omo_daemon 评分项而非 PR CI 门禁——事实修正：删它们是评分面减法，
不降 CI 时长）；pitfall 库 13 条无一达阈值（管道通了没车跑）。另有 80 规则
review_before 同日 2026-11-26 到期风暴（Q4 硬 deadline）。

## 8 项决策记录（principal 全确认）

| Q | 决策 |
|---|------|
| 1 | 四项范围：①unspecified 修复 ②PRUNE 执行 ③风暴拆弹 ④pitfall 喂食；⑤返工阈值**不做**（未满月——遵守 v1 承诺即纪律）|
| 2 | 真实减法哲学：物理删，不做"标记 dormant"式假减法 |
| 3 | 数据级验收写进 done_when（四条见下）|
| 4 | unspecified：修源头 + 采集器降级 `unattributed` 桶；**不回填老数据**（历史诚实）|
| 5 | 两批：观测质量三件（①②④）一个 PR；风暴拆弹独立 PR（80 行 yaml 审查隔离）|
| 6 | 源头堵法 = 归因标记 `preflight-clean\|skip\|none`（保留"SKIP 且干净"语义 = SKIP 滥用监控一手数据，0391 教训宁可记全）|
| 7 | PRUNE = 物理删 omo_daemon 评分项 -2 + gate-roi 配置 -2；**验收修正**：评分面负增长（非 CI check 数）|
| 8 | 喂食 = 周期驱动（convergence-pulse-weekly 链上对 Top≥3 指纹聚合 record，fuzzy 去重天然工作——同一指纹 N 次→一条 times=N，首周直达阈值）|

## 批次 1：观测质量三件（一个 PR）

### 1a. unspecified 源头归因
- 定位写入方：rg 写 `.omo/_delivery/swarm-escape/` 的代码（候选：`.githooks/pre-push`
  的 escape 段 / bin/gac/escape*.py / swarm-git 路径；写入特征 `fingerprint_key`
  构造处 surface/check_id 默认 "unspecified"）
- 改：`fingerprints 为空 && would_block=false` 时 fingerprint_key =
  `preflight-clean|skip|none`（不动其他路径）
- 采集器 `bin/gac/convergence-pulse.py` v2：fingerprint_key 前缀
  `preflight-clean` → 独立 `preflight_clean` 计数；现存 unspecified 键 →
  `unattributed` 桶（兼容老数据）

### 1b. PRUNE 物理执行
- omo_daemon 评分 checks 定义删 `task consistency` + `doc lifecycle`（位置：
  projects/omo/src/omo/ 下 checks 名表——impl 时 rg 定位，与 gate-roi 配置
  `bin/gac/gate-roi-report.py:48,50` 的两键同步删）
- `.github/workflows/omostation-governance.yml:83` grep 注释段清理
- 回归：rules-lifecycle / gac-validate / 相关 omo tests

### 1c. pitfall 周期喂食
- `bin/gac/error-knowledge.py` 加 `feed_from_escapes(escape_dir) -> int`：
  对台账聚合 Top 指纹（≥3 次、非 preflight-clean/unattributed）调既有 record
  语义（symptom=excerpt 关键行、category=按 surface 映射到 CATEGORIES、
  title=`auto: <check_id> 反复豁免`、agent=`auto:escape-digest`）
- `.omo/_truth/registry/agent-workflows/workflows/convergence-pulse-weekly.yaml`
  execute 链在 escape-digest 步后加 `pitfall-feed` 步
- 幂等：靠 record 既有 fuzzy 去重（同指纹周周喂 → times 持续增长，正合语义）

### 批次 1 测试
- escape 写入方：unspecified 路径改后产出 preflight-clean（fixture 驱动）
- convergence-pulse v2：三桶聚类（normal/preflight_clean/unattributed）单测
- feed_from_escapes：fixture 台账 → 生成 record 条目 times≥3、来源标记正确
- 全链：convergence-pulse-weekly 再跑一轮，四验收数据落 JSON

## 批次 2：风暴拆弹（独立 PR）

- `lib/yaml_ssot_edit.py` 编辑 `governance-checks.yaml` gac.rules：
  review_before = added_at + (90 + hash(id)%61) 天 → 80 条分散至约 60 天窗口
  （≥8 个不同日期，11-26 风暴解除）
- 顺手不改 justification（Q4 减法评审时回填——443 已声明）
- 验证：rules-lifecycle 报告三桶分布不再同日、`adr-number-check` 不涉及、
  `gac-validate --gate` 绿

## 验收（四条硬标准，修正版）

1. escape 新记录 unspecified 占比 0%（preflight-clean 归因）；unattributed 老桶只减不增
2. 评分 check 面 -2（task consistency / doc lifecycle 物理删除，gate-roi 配置同步）
3. pitfall 库出现首条自动喂食记录（times_encountered ≥2 且来源 auto:escape-digest）
4. 80 条规则 review_before 分散至 ≥8 个不同日期（rules-lifecycle 复核）

## 实施顺序

1. 批次 1：1a 源头 → 1b PRUNE → 1c 喂食 → 测试 → PR → 轮询合并 → workflow 再跑一轮验收
2. 批次 2：roundtrip 拆弹 → rules-lifecycle 复核 → PR → 合并
3. 双批合并后对照四条验收出 v2 复盘（含数字）

## 复用清单（不新建）

- roundtrip 工具 `lib/yaml_ssot_edit.py`（拆弹与所有 registry 编辑）
- record 既有 fuzzy 去重与 CATEGORIES（喂食不另造分类）
- convergence-pulse 既有聚类骨架（只加桶不改架构）
- workflow execute 链模式（加步不新建 workflow）
