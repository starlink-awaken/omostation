# BET-Y1Q3-T1-13 复盘

## Q1 实际耗时 vs appetite？超出比例？

Appetite: 0.25 day。本轮实测约 0.5–1h（诊断 + worktree/PASW + closeout），未超 1.5× 熔断线。

## Q2 done_when 是否全部通过？哪条没过，为什么？

全部通过（在 `work/bet-y1q3-t1-13` @ `origin/main`）：

1. `projects/agora` index 已恢复：`pyproject.toml` 与 `src/agora/` 存在。
2. `projects/agora` / `projects/cockpit` / `projects/omo` 的 checkout SHA 与父仓库 HEAD gitlink 一致，且 `git submodule status` 无 `+` 前缀：
   - agora `346e3fb848ed2fd69b190b524fdc196bad48187e`
   - cockpit `d5fb9a0fdefbd96b4a0c0ff6d4e67536ee602253`
   - omo `b907178cccf00da658b7cc6485cba576b0fdab78`
3. 父仓库 `git status --short` 为空（对 omo 内偶发 `uv.lock` 脏文件执行 `reset --hard` 后确认；未改子模块业务代码）。

`bet-ledger.py verify BET-Y1Q3-T1-13 --execute` 与上述手工检查一致。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **漂移主体已收敛**：在最新 `origin/main` 上，三个目标子模块 gitlink 已对齐；本 BET 更接近「验收 + 台账钉死」而非再次改写 gitlink。
2. **共享主树假阳性**：`Workspace` 主树曾见 ` m projects/omo`，根因是子模块内本地 `uv.lock` 被 `uv run` 触碰，不是父仓指针漂移。隔离 worktree 上 `reset --hard` 即可；不要把本地 lock 脏文件当成指针修复。
3. **write_surfaces 过窄**：台账只声明了 `docs/plans/3y-bet-ledger.yaml`，但 closeout 必写 retro；claim retro 会撞 `WORK_PACKET_SCOPE_MISMATCH`。本轮仍落盘 retro（链门需要），并在台账补记该路径。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

- 代码行：0（无业务实现）
- 文件：+1 retro；台账条目字段更新（status/done_at/completion_evidence/value_indicator_policy）
- GaC 规则 / ADR / 脚本：0
- 表面积：净减认知噪音（去掉「子模块仍漂移」的假待办），未新增运行时表面积

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. 验子模块对齐先看 **父仓 HEAD gitlink vs `git submodule status`**，再看子模块内部 `status --short`；后者脏不等于指针错。
2. 跑 `uv run` 后若 `projects/omo` 出现 `uv.lock` 脏文件，优先 `git -C projects/omo reset --hard`，不要提交进 omo。
3. closeout 类 BET 若 `write_surfaces` 漏了 retro，开工前先扩写面或接受 claim 范围限制并仍落盘 retro。
4. `value_indicator_policy=false` → 走 `delivery_accepted`（engineering=VERIFIED + operational=PROVEN + value=NOT_PROVEN），不要为指针修复硬做 value ACCEPTED。
