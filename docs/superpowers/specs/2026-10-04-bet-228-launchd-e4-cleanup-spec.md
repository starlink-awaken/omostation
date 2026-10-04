---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-228 launchd 登记 E4 存量 findings 清理
bet_id: BET-Y2Q4-T10-228
status: accepted
lifecycle: contract
owner: governance-agent
last-reviewed: 2026-10-04
---


# BET-Y2Q4-T10-228 Spec — launchd 登记 E4 存量 findings 清理

- bet: BET-Y2Q4-T10-228
- date: 2026-10-04
- owner: governance-agent
- workflow: governance-state-mutation

## 背景

`docs/reports/2026-09-27-service-registry-reality-closeout.md` 遗留三类 finding,
2026-10-04 实测现状如下（与 9-27 登记时已有漂移）:

1. **com.yetone.magpie** — 实测 plist **已安装且加载**（launchctl PID 1980）,
   是第三方划词翻译应用 Magpie.app 的自注册启动项。判: external 域,
   补登 exempt_labels + reason（归属主体 = Magpie.app, 非本仓可管理面）。
2. **com.amazon.codewhisperer.launcher** — 2026-09-30 plist 批量覆写事故后
   按其残留 ProgramArguments 重建为合法 XML、当时未 load。2026-10-04 实测
   LaunchAgents **已无此 plist**（launchctl 仅剩 codewhisperer 输入法应用实例,
   label 不同）→ 豁免记录移除。
3. **4 个 unclassified** — com.learningevolution.concept-weave.monthly /
   com.lifeos.pulse / com.local.decision-svc / com.opencode.quota-monitor,
   全部已安装（lifeos.pulse 运行中, PID 94325）。2026-09-27 原则「只记证据,
   不替 principal 签归属判语」。本轮获 principal 全局授权
   （「后续决策你来决定, 按最优解来做」）, 裁定四者均为 **owned**
   （principal 个人工具/本地服务域）, 写入 launchd_namespace 归属 + reason,
   unclassified 清零。

## 方案

- services.yaml `launchd_namespace` 面: magpie 补登 exempt_labels + reason
  （Magpie.app 第三方自注册）; codewhisperer.launcher 豁免记录移除;
  4 个 plist 写入归属（owned, principal 个人工具/本地服务域）与 reason;
- closeout 报告增补「2026-10-04 裁决」段落, 附实测证据（launchctl/ls 输出）;
- 跑 `bin/mof/gen-service-configs.py --reality-check` 确认 E1-E4 全绿。

## 非目标

不 load/unload 任何任务; 不改 generate 面; 不增删 plist 文件。

## 验收

见台账 done_when。裁决后 unclassified=0, E1/E2/E3/E4 全绿。
