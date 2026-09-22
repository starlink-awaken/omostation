---
schema_version: governance-waiver/v1
created: '2026-09-22'
bet_id: unbound
run_id: 20260922T074023Z-governance-state-mutation-5eff1f99
scope: a4-cron-registry-orphan-classification
---

# A4 孤儿分类 unbound-start waiver

A4 门禁（调度声明与安装态一致，`bin/scheduler-compile.py check_drift`）
FAIL：crontab 中 `*/30 * * * * ~/.local/bin/mimo-models-sync.sh` 未在
`.omo/cron/registry.yaml` 登记且不在 `known_orphans` 豁免列表，
`orphan_count=1`。该脚本是用户本机 MiMo 模型配置同步工具（外部工具，
非工作区治理作业），与 2026-09-20 已豁免的 `clash-probe.sh` 同类。

处置 = 分类而非登记：追加 `known_orphans` 一行（子串匹配豁免），
不将个人工具扩张为治理调度 SSOT 的 active job，也不触碰用户 crontab。

该修复不对应任何台账 BET，按仓内先例（#4176 / #4189）使用一次性
`AGCP_REQUIREMENT_ITERATION_GATE=0` 前缀完成 unbound workflow start
`20260922T074023Z-governance-state-mutation-5eff1f99`；closeout 走
G8 豁免 lane（governance-state-mutation，PITFALL-GAT-009）。

Write surface 严格限定为两个路径：

- `.omo/cron/registry.yaml` — 仅 `known_orphans` 列表追加一行
- `.omo/_truth/governance-evidence/waiver-2026-09-22-a4-mimo-orphan-classification.md`（本文件）

本 waiver 不授权：registry 任何 job 条目改动、crontab 安装态变更、
其他 known_orphans 修改、strict mode、runtime mutation。

验证：`scheduler-compile.py --check` ok=true exit 0（drift=0, orphan=0,
known_orphan=2）；`yaml.safe_load` 复验。
