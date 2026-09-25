---
schema: md/v1
status: active
lifecycle: history
owner: auto-fix-loop
last-reviewed: 2026-09-25
type: ephemeral
---

# TASK-B3229A65 完成证据 — A4 调度真相收敛收尾

## 现场核实：原3处矛盾里，2处已在此前修复，本次补齐最后1处

1. **两处死引用**（`bin/gac/log-rotate.sh`、`bin/gac/gac-worktree-prune.sh`）——
   现场确认这两个路径真实不存在；`.omo/cron/registry.yaml` 与真实 crontab
   已改指向存在的 `bin/ssot/log-rotate.py`、`bin/gac/gac-branch-prune.sh`
   （通过 `Makefile:worktree-prune` target 确认）。此前已修复。

2. **zhixing-dashboard 面板刷新的 Codex-token 依赖**——registry.yaml 里已有
   `zhixing-dashboard-refresh` 条目，注释明确记录 2026-09-11 已迁到 launchd
   （`com.omostation.zhixing-dashboard-refresh.plist`），脱离 Codex LLM
   automation 的 token 依赖，此前已解决，不是本次新发现。真正遗漏未登记的
   是另一个独立的、同样跑在这个面板目录下的 `panorama_cache.py` cron job
   （纯本地缓存刷新，走普通 crontab 而非 launchd，本来就不含 LLM/Codex 调用，
   跟 refresh.py 是两个并存的不同脚本，不是互相替代关系）。

3. **3源矛盾收敛为0 drift**——`python3 bin/scheduler-compile.py --check`
   在动手前已是 `drift_count=0`（此前 lane 已收敛），但 `orphan_count=1`——
   `zhixing-dashboard-panorama-cache-5min` 这个 `*/5 * * * *` 的 cron job
   真实已安装（真实 crontab -l 可见），但从未登记进 registry.yaml。
   本次补登（`.omo/cron/registry.yaml` 新增一条 job，只补声明面，未改变
   任何真实调度/命令/运行行为）。

## 验证命令与结果（2026-09-16 现场执行）

```
$ python3 bin/scheduler-compile.py --check
{"ok": true, "drift_count": 0, "orphan_count": 0}
```

修复前（补登前）：`{"ok": false, "drift_count": 0, "orphan_count": 1}`

## crontab 真实内容未变

本次只改了 `.omo/cron/registry.yaml`（声明面），没有执行 `crontab -e` 或任何
修改真实 crontab 的操作——`crontab -l` 修复前后逐行一致。
