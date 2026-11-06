---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-06
type: report
bet_id: BET-Y2Q4-T10-285
title: BET-Y2Q4-T10-285 收口收据 —— agora daemon /health、7433 注册与健康扫描接线
---

# BET-Y2Q4-T10-285 收口收据

## 1. 交付面（两个仓，三个 commit）

| 面 | 载体 | SHA | 时间 |
|----|------|-----|------|
| 主仓：spec + 台账 + `protocols/port-registry.yaml` 7433 注册 | PR #5048（接手 #5044） | `7c21629eca3e8e3740dae63f20e47851f6be5069` | `2026-11-05T04:27:24Z` |
| 子仓 omostation-agora：`src/agora/daemon.py` + `tests/unit/test_daemon_health.py` | PR #126 squash（本轮合并） | `17028faa35301898fdb17fe29b1c3a873a60038c` | `2026-11-06T07:10:18Z` |
| 机器态：`~/runtime/matrix.yaml` agora-daemon 条目（非仓内文件） | 直接写入 | 文件 mtime `2026-11-04T19:57`（本地） | — |

收口腿基线 = 起手时 `origin/main = 07d53ba0c62e0b54bb4f5eb057f8ae25fa1f1640`；本次 3 个路径
（retro、收据、台账）上游零漂移：
`git diff --name-only $(git merge-base HEAD origin/main) origin/main -- docs/plans/3y-bet-ledger.yaml` 为空。

PR #126 的 head 原为 `bf9a70fcc3a7d2f1a383ca20a9a42e300a853683`（`agent/claude-lead/siri51-daemon-health`，
2026-11-04T11:58:31Z 开）。合并前两仓状态核对：`mergeable=MERGEABLE`、`mergeStateStatus=CLEAN`、
`gh pr checks` 零输出。零输出在这里不是冲突也不是 `on.paths` 过滤 ——
`git ls-tree -r --name-only origin/main .github/workflows`（omostation-agora）为空，该仓**没有任何 workflow**，
CI 结构性不评审这个 PR。所以本条的工程证据只有本地复算，逐项见 §2.5。

## 2. done_when 五条复算

### 2.1 `curl -fsS http://127.0.0.1:7433/health` → 200 + 三键

```
{"status":"ok","uptime_s":92760,"udp_port":7455}     # 2026-11-06T07:04:20Z，rc=0
{"status":"ok","uptime_s":93155,"udp_port":7455}     # 2026-11-06T07:10:55Z（安装根换 commit 之后）
```
7432 侧对照：`curl -fsS http://127.0.0.1:7432/health` → `rc=7 Couldn't connect`，旧端口确无监听者。
`udp_port=7455` 与 `protocols/port-registry.yaml` 的 `AGORA_SWARM_UDP_PORT` 一致，daemon 不开 UDP socket。

`uptime_s` 两次相差 395s 与真实墙钟一致 ⇒ 进程未重启，安装根换 commit 对运行面无影响。

### 2.2 daemon 不 crash-loop

`launchctl print gui/501/com.agora.daemon`：`job state = running`、`runs = 1`、
`last exit code = (never exited)`、`pid = 3161`；argv 为
`/bin/bash /Users/xiamingxing/.local/opt/omostation/lib/agora-daemon.sh`（ADR-0435 安装根 wrapper）；
监听 7433 的是其子进程（`lsof -nP -iTCP:7433 -sTCP:LISTEN` → python，pid 3280）。
`runs=1` 而不是 N 才是「起跑成功且常驻」的读数（§7 T10-265 判据）。

### 2.3 健康扫描落盘

`.omo/state/system_health.yaml`（检出与安装根两份同构）中 agora-daemon：

```
agora-daemon:
  health_check: healthy
  port_listening: true
  runtime: {port: 7433, status: running, freshness_seconds: 0}
```

`health_check` 键的存在即说明扫描走的是 `health_url` 真 HTTP 探活，而不是「查 PID」。cron-service 侧
`health_url` 机制零代码改动（非目标 4 成立）。

### 2.4 matrix-consistency-lint：agora-daemon 0 ERROR

尺随 base 变，所以两把都记：

| 装置 | 读数 |
|------|------|
| 落后的主检出（本地 `protocols/port-registry.yaml` 无 7433） | `1 ERROR`（R5 cron-service）+ `2 WARN`，其中 **`R2 WARN: 'agora-daemon' port 7433 not found in port-registry.yaml`** |
| `origin/main` 基线树（`bin/ssot/matrix-consistency-lint.py` + `protocols/port-registry.yaml` 取 `git show origin/main:`） | `1 ERROR`（R5 cron-service）+ `1 WARN`（R5 gbrain-index），**agora-daemon 零 ERROR 零 WARN** |

第二行才是 done_when[1] 要求的读数；第一行的 R2 是装置落后于基线的伪报（`matrix-consistency-lint.py:28-30`
把 `PORT_REGISTRY_PATH` 绑在脚本自己的检出上）。唯一的 ERROR `R5 cron-service`（`com.user.cron-service`
不在 launchctl）是预存项，与 spec §6 反指标里「预存 lint 问题不在本 bet 修复范围」同源。

### 2.5 agora 子仓测试与 lint

装置：`uv run --no-project --with pytest …` 因缺 `fastmcp`/`pytest-asyncio` 在 collection 阶段就
`ModuleNotFoundError`（不是回归），改用已解析依赖的 agora venv 并把被测源码显式置于 `PYTHONPATH` 首位：

```
PY=/Users/xiamingxing/Workspace/projects/agora/.venv/bin/python
cd /tmp/agora-p126-verify                                  # git worktree add --detach @ bf9a70f（PR head）
PYTHONPATH=/tmp/agora-p126-verify/src $PY -c "import agora; print(agora.__file__)"
  → /tmp/agora-p126-verify/src/agora/__init__.py           # 证被测源码是 PR 的那一份，不是 venv 里的 editable
PYTHONPATH=/tmp/agora-p126-verify/src $PY -m pytest tests/unit/test_daemon_health.py -q -p no:randomly
  → 4 passed in 1.65s
```

ruff 用同一把尺在**改动前后两棵树**上各量一次（`ruff` = `/opt/homebrew/bin/ruff`）：

| 树 | `ruff check src/` |
|----|-------------------|
| PR head `bf9a70f` | Found 5 errors（5 fixable） |
| base `e1cc383` | Found 5 errors（5 fixable） |

⇒ 零新增违规，5 条为存量，与 spec §6 反指标一致。

## 3. 安装根对齐

收口前：`~/.local/opt/omostation/projects/agora` HEAD = `bf9a70f`（detached，其远端分支已随 squash 删除的
同一 PR 生命周期消失）。收口后：

```
git -C ~/.local/opt/omostation/projects/agora fetch origin
git -C ~/.local/opt/omostation/projects/agora checkout 17028faa35301898fdb17fe29b1c3a873a60038c
  → HEAD = 17028fa…
src/agora/daemon.py sha256 = 6bcb1a8bf3ea38c058d68b57f7430f4971ea3efb64ac165e0cb9cd001c8ef810
```

tree 等价性在换 commit 之前已核：`git rev-parse bf9a70f^{tree}` 与 `17028fa^{tree}` 同为
`07a8fb6b5cd1a9c533fcc7904014d941d4b91fb2` ⇒ 运行内容与仓内容一致，无需重启。
换 commit 后 §2.1 的 `/health` 复测通过（uptime 连续）。

## 4. 回滚面

| 面 | 回滚命令 | 前置 |
|----|----------|------|
| 子仓代码 | revert `17028fa`（agora main），或 `git -C projects/agora checkout e1cc383` | 端口回 7432 会与 ecos-event-listener 注册冲突，回滚后须同时撤 port-registry 的 7433 条目 |
| 安装根 | `git -C ~/.local/opt/omostation/projects/agora checkout e1cc383` + `launchctl kickstart -k gui/501/com.agora.daemon` | spec §5 记的历史回退点是 `4ae1a58`，本轮已不适用（现值 = `17028fa`） |
| 主仓注册 | revert `7c21629ec` 中 `protocols/port-registry.yaml` 的 7433 三处 | 该 PR 同时含 spec 与台账，整 PR revert 会带走别的条目 ⇒ 只能按路径 revert |
| matrix.yaml | 删除 agora-daemon 条目（14 行） | 声明即预期存在，删条目会退回「只查 PID」的盲区 |

## 5. 清理与残留

- 临时 worktree `/tmp/agora-p126-verify`、`/tmp/agora-base-verify` 与 `mktemp -d` 基线树均为本轮自建，
  用完即删，不进任何仓。`runtime/affected/t285-closeout.json`（claim 用的 affected-graph receipt）
  不落 commit。
- **未承接项 1 —— 主仓 gitlink 漂移**：`git ls-tree origin/main projects/agora` = `e1cc383`，
  而 agora `origin/main` = `17028fa`，差 1 个 commit；pin 是 main 的祖先（可达性 OK）。
  本条非目标 3 明确「不 bump 主仓 submodule 指针」，所以本轮不 bump。
  `bin/ssot/submodule-pointer-transaction.sh` 在「子仓 commit 已在 origin/main」形态下按构造 no-op
  （增量模式找的是子仓**未推送**的 commit），因此这条 drift 不会自愈，预期由
  `submodule-freshness-gatekeeper` 报警后另起一次 `chore(submodule)` 交付承接。
- **未承接项 2 —— A2A 谓词缺陷**：`claim --path docs/plans/3y-bet-ledger.yaml` 报
  `A2A Path Lock Collision … in run 20261104T115230Z-project-code-change-d825f60f`；该 run
  `status: active` 而 `last_heartbeat = 2026-11-04T11:59:54Z`（约 43h 前）、三条锁
  `expires_at = 2026-11-05T11:54:48Z`（约 20h 前过期）、其 BET 无 open PR。
  按 PITFALL-COO-008（`054c52eec`，PR #5073）的处置执行：**不跑 `prune-locks`、不清他人锁**，
  改为未 claim 交付并把原因写进 workflow close 的 evidence。谓词正解（status 活跃**且**锁未过期才算冲突）
  仍无承接 BET —— 本轮台账里没有这条，需要另铸。
- **未承接项 3 —— agora 仓零 CI**：`omostation-agora` 无 `.github/workflows/`，其 main 上任何 PR 都不会被
  CI 评审。本轮靠本地复算兜住，但这是一个仓级结构性失明，不属于本 BET 范围。
