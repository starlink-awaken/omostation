---
schema_version: specification/v1
spec_version: 1.0.0
title: 门禁迭代 — Gatekeeper baseline/grace + hook-runner 处方化报错
bet_id: BET-Y1Q4-T10-134
status: accepted
lifecycle: contract
last-reviewed: 2026-09-06
type: plan
owner: governance-team
last_updated: 2026-09-06
---

# 门禁基线与处方化规格 (BET-Y1Q4-T10-134)

## 动机 (三日会战实测)

- 全量 Gatekeeper 无存量概念: cockpit voice_memo 存量直写让全舰队 PR CI "谁撞谁倒霉" (#3241/#3322/#3325 三连)
- hook-runner 失败只报 id 不报修法: agent 试错靠考古 (script-registry 漏登记等)

## 变更

1. **contract_gatekeeper.py** (omo 子模块): 新增 `--baseline <yaml>` —
   grace 清单内文件的违规打印 `[grace]` 前缀但不算 FAIL (shrink_only: 只许移除);
   主仓 grace 清单 `.omo/_truth/registry/gatekeeper-grace.yaml`
   (初始: cockpit voice_memo.py 存量直写)
2. **verify-omo.sh** (主仓调用侧): 传 --baseline
3. **hook-runner.sh**: run_check 失败时从 hook-manifest.yaml 读该 check 的
   `fix:` 字段打印处方
4. **hook-manifest.yaml**: 易错 check 补 fix 字段
   (script-registry/remote-hygiene/gitlink-ancestry/branch-naming/mass-deletion)

## 验收

- 人为存量违规 + baseline 命中 → gatekeeper exit 0 (打印 [grace])
- baseline 外新违规 → 仍 FAIL
- script-registry 漏登记 → hook-runner 打印 register 处方
