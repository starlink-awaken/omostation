---
type: ssot
---

# Grill 5Q — 边界/反模式/容量/回滚/可观测

> SSOT: .omo/_truth/registry/harness-policy.yaml :: admission.require_grill
> 用于 appetite>=1d || risk_level>=L2 || human_gate==true 的 BET，Harness admission 强制校验

## Q1 边界
- 本次变更的写面是否收敛到 BET.write_surfaces？越权写是否 halt？
- 是否明确 non_goals，不引入新 registry/scheduler/broker 或第二 dispatch truth？

## Q2 反模式
- 是否避免用 PR/测试/Agent 自评/maturity 分数冒充个人价值？
- 能力调用是否 exact find-load，不用短名或子串模糊匹配？

## Q3 容量
- appetite 是否覆盖 5 天？回退/重跑成本是否在 1.5× 内？
- 16 个 write_surfaces 是否可并行 claim，无需串行锁？

## Q4 回滚
- 若 capability binding 失败，是否可 git checkout 回退 ledger/spec，无残留 receipt？
- 子模块指针是否可前向修复，无需 force-push？

## Q5 可观测
- harness trace <run-id> 是否一行回放 admission→grill→verify→audit→accept？
- panorama / cockpit harness trace 是否为唯一可观测入口？

> 填写时每 Q 至少 1 行具体回答，空模板视为 grill_section FAIL。
