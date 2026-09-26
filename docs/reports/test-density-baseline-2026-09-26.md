---
schema: md/v1
status: active
lifecycle: plan
owner: engineering-agent
last-reviewed: 2026-09-26
type: ephemeral
title: "测试密度基线（2026-09-26）— fix 必带回归测试规则 (BET-Y2Q4-T10-02)"
---

# 测试密度基线（2026-09-26）

## 规则（观察期，非强制门禁）

**fix 类交付必须带回归测试，或在 PR 模板的「回归测试声明」节留痕豁免。**
豁免口径：纯文档 / 生成态 / 子模块指针（gitlink）类 fix 不需要测试，理由一句话即可。
观察期 30 天（至 2026-10-26），期满由后续 BET 决定是否升级为 CI 强制检查。

## 可复算基线（D1：命令原样执行，禁止人工报数）

```bash
git log --format="%s" --since="$(date -v-30d +%Y-%m-%d)" \
  | grep -oE '^[a-z]+' | sort | uniq -c | sort -rn
```

2026-09-26 实测（滚动 30 天窗口）：

| 类型 | 数量 |
|---|---|
| feat | 499 |
| chore | 444 |
| fix | 420 |
| docs | 341 |
| **test** | **34** |

- **test : feat ≈ 1 : 14.7**
- **test : fix ≈ 1 : 12.4**（回归覆盖最相关的口径）

## 目标

30 天后（2026-10-26 复算同命令）：**test : fix ≥ 1 : 5**。
达成路径：不做一次性大补测，靠「fix 必带回归测试」的规则随交付自然积累；
高危面优先——omo broker/state 层、kairon pipeline、gbrain 实体抽取。

## 复发风险依据

#3282 回退 #3277（同 BET 并行交付 5 处修复被静默覆盖）、#4377/#4381 的
probe/proxy 类缺陷——均为"修了但无测试防复发"的形态。

## 度量局限（如实声明）

1. subject 前缀是约定信号，可能误分类（如 feat 内含测试、test 提交改 fixture）；
2. 只度量提交数，不度量断言质量——防"为指标而写无断言测试"（D6）；
3. 复算时若口径变化（如新增 commit 类型），需在本文件追加版本注记而非静默改。
