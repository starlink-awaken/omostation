---
status: active
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
related:
  - 0179-runtime-probe-false-positive-treatment.md
  - 0195-architecture-convergence-isc2.md
  - ../patterns/p73-truth-driven-engineering-pattern.md
supersedes: []
---

# ADR-0202: 假绿灯防线三件套 — 非空守卫 / 迁移保内容 / 并发验证纪律

> **背景事件链 (2026-07-14~15)**:
> ① `a615ace16` "bin/ rationalization" 迁移只建骨架未搬内容, **123 个治理工具变 0 字节**,
>    Python 跑空文件 exit 0 → CI/gate/foundry 全线假绿 ~4.5h (从 a615ace16^ 全量找回, +22993 行)。
>    最讽刺: 负责查 0 字节的 ssot-guardian 自己是 0 字节 — 自指验证盲区。
> ② foundry cron plist 指向已删除 worktree `ws-p76-phase7`, 静默失败 5 天, 健康分僵尸化。
> ③ 分叉调和中, 本地 commit `ab74b0e08...` 被并发流重写为 `ab74b0e23...` — **短 SHA 前 7 位相同**,
>    肉眼比对被骗, 靠 API 全 SHA + tree hash 才识破。
> ④ ADR 编号双头竞争: 本 ADR 前身 30 分钟内被抢号两次 (0200→0193 被 #362 抢→0195)。

## 决策

### D1 · CI 内联非空守卫 (不依赖仓库自身工具)
任何"用仓库里的工具检查仓库"的体系都有自指盲区。在 CI workflow 中加**内联** shell 步骤
(纯 find, 不调用 bin/ 任何脚本), bin/ 下出现 0 字节 `*.py` 即红:
见 `.github/workflows/workspace.yml` `inline zero-byte guard` step。

### D2 · pre-commit 迁移保内容守卫
`bin/gac/check-move-integrity.py` 进 `.pre-commit-config.yaml`:
- 暂存区新增 (A) 的 `*.py` 为 0 字节 → 拦截 (骨架占位必须显式 `# placeholder` 声明)
- 暂存区出现 "删 >0 字节文件 + 同名新增 0 字节文件" 的迁移对 → 拦截 (a615ace16 模式)

### D3 · 分叉检测入 foundry 常态化
`bin/gac/git-divergence-check.py` 作为 foundry deck (7:00) 每 6h 跑:
root main vs origin/main 的 ahead+behind 超阈值 (默认 12) → deck fail → BRIEF 可见。
分叉在 1-2 commit 时调和是零成本, 攒到 20+ 是小时级工程 (2026-07-15 上午实测)。

### D4 · 并发环境验证纪律 (规范, 非工具)
- 并发多写手环境下, commit 同一性验证**必须用完整 SHA**; 内容等价性用 `tree hash` 比对。
  短 SHA 在同 message/同内容重写场景会前缀撞脸 (实测 7 位相同)。
- ADR 编号 = 共享可变资源: 占号即推送 (via PR 快落地), 或接受重号成本。
  INDEX 规则"编号冲突由人类审批"在多 Agent 高频下不够, 后续可升级为编号申请制。

## 后果
- pre-commit 多 <1s (git diff --cached 纯本地)。
- CI 多一个 <5s step。
- foundry deck +1 (仅 root fetch, ~2s; 子模块不逐一 fetch 避免拖慢)。
- GaC 173 条冻结不受影响 — 本 ADR 不新增 GaC 规则, 守卫落在 hook/ci executor 层
  (按 ADR-0171 哲学: 教训必须成为 red 执行点, 文档化的教训是墓志铭)。
