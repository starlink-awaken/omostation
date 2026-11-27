---
schema: md/v1
type: report
status: completed
lifecycle: evidence
owner: governance-agent
last-reviewed: 2026-11-27
bet_id: BET-Y2Q4-T10-366
---

# BET-Y2Q4-T10-366 收口回执 —— 宿主发布运行期一致性

> 事实以实测读数为准, 不填占位。宿主面未变更 (本 BET 只改发布器, **本轮未执行任何一次真实发布**)。

## 0. 交付坐标

| 项 | 值 |
|----|----|
| PR | [#5656](https://github.com/starlink-awaken/omostation/pull/5656) (squash merged) |
| merge SHA | `91344029db133d496c21118eaf6204b629a713b2` (`git://origin/main@91344029db133d496c21118eaf6204b629a713b2`) |
| 规格 | `docs/superpowers/specs/2026-11-27-host-publish-runtime-convergence.md` (`spec_version 1.0.0`, digest `sha256:bac7dc3e1981c1849cff18af7149e86a35d085cab0384a963ae34b3a636865eb`) |
| CI | PR #5656 全部 job 绿 (含 `gac-gate` / `governance-verify` / `interface-check` / `integration (3.13)` / `evidence-gate` / `bet-done-transition`) |

## 1. 变更面

| 路径 | 变更 | lane |
|------|------|------|
| `bin/gac/zhixing-host-sync.py` | 新增运行期身份面 (`runtime_binding_snapshot` / `release_identity_of` / `check_runtime_binding` / `coordinate_runtime` 等), `publish()` 在切换 `current` 之前取运行期快照并判定, 绑定将破坏时协调重绑定并验收收敛, 不收敛即回滚, 协调不可用即拒绝发布; `restore()` 走同一收敛路径 | governance_code |
| `tests/unit/test_zhixing_publish_runtime_convergence.py` | 新增 8 条判据用例 (绑定保持不协调 / 绑定将破坏→协调并收敛 / 不收敛→回滚 / 不可观测跳过 / pid 不可验证跳过 / 协调不可用拒绝 / 候选身份读取 / `restore()` 收敛) | code |
| `docs/superpowers/specs/2026-11-27-host-publish-runtime-convergence.md` | 规格 (spec_version 1.0.0, digest `sha256:bac7dc3e1981c1849cff18af7149e86a35d085cab0384a963ae34b3a636865eb`) | docs |
| `docs/plans/3y-bet-ledger.yaml` | 台账条目 + done-transition (本 BET 插入一条) | docs_data |
| `.omo/_knowledge/retros/BET-Y2Q4-T10-366.md` | 复盘 | governance_state |

## 2. 事实链

live server 的 `CODE_ROOT` 在 import 时解析 (`runtime_paths.py.asset:17` 的
`Path(__file__).resolve().parent`) ⇒ 进程钉死在启动那一刻的 release; 投影 revision 的
绑定来自采集器当时看到的 `current` 软链 ⇒ 每次发布换一个 `commit_oid`, 两侧必然不等
⇒ `CODE_DRIFT` ⇒ 静态资源 503。而 `publish()` 只做「切指针 + SHA 校验」, 从不读运行态
⇒ 返回 `ok: true` 而驾驶舱整站只读, 恢复只靠人工重启 (T10-364 回执 §5 实测)。

契约缺口不在检查层, 在**事务边界**: 检查做完了, 事务没做完。

## 3. 实测读数

### 3.1 只读 canary (线上运行实例; 本轮未执行任何一次真实发布)

| 项 | 读数 |
|----|------|
| live server 进程 | pid 70152, label `com.omostation.zhixing-dashboard`, `current/live_server.py --port 43191` |
| `/health` `dashboard_code_oid` | `8f43efedc4e04e80e7612a68c6be046f4950c6cb` |
| `/health` `dashboard_tree_sha256` | `941dc14aff8723a9266daf7466d2e9c2fee0d8930da8d506bf7e6e9bb723e4b8` |
| `/health` `dashboard_code_sha256` | `f82f24ee2394cd35bdac8e84258336bc7dfb729a940148cd46fc80aa6bb2aa58` |
| `/health` `code_drift` / `projection_status` | `false` / `BOUND_FRESH` |
| `current` → | `releases/8f43efed…` (与运行中 oid 同一) |
| `check_runtime_binding(current, snapshot)` | `ok=true, checked=true, reason=runtime_identity_preserved` |
| `_runtime_coordination_available()` | `true` (采集器刷新作业已加载, 可 kickstart) |

读法: 运行实例与 `current` 指向同一 release ⇒ 新判据在「重复发布同一批字节」上判为
`runtime_identity_preserved` ⇒ 不协调、不 kickstart, 零扰动。
「绑定将被破坏」那条分支须在宿主上真实发布才能复现 —— 属 principal 的机器级窗口, 本轮未执行。

### 3.2 三态判定

| 情形 | 判定 | 动作 |
|------|------|------|
| 两侧身份三元组相同 | `runtime_identity_preserved` | 放行, 不协调 (零扰动) |
| 两侧不同 | `runtime_identity_will_break` | 协调重绑定 (kick 采集器刷新 → 重启 live server) 并验收收敛; 不收敛即回滚 |
| 协调通道不可用 (采集器刷新作业未加载) | `runtime_coordination_unavailable` | **拒绝发布**, `current` 未被切换 |
| 不可观测 (探不到 / pid 不可验证 / 身份三元组不完整) | `runtime_unreachable` / `runtime_pid_unverified` / `runtime_pid_mismatch` / `runtime_identity_incomplete` / `candidate_identity_incomplete` | 跳过判定, 不阻断发布 |

### 3.3 收敛验收判据

`coordinate_runtime()` 轮询 `/health` 直到 `code_drift == false` 且
`dashboard_code_oid == 期望 oid`; 超时 (默认 180s) 判不收敛 ⇒ 回滚:
`current` 切回上一版, 并把运行期重新收敛回原 oid (`rollback_runtime`)。

## 4. 验证

| 检查 | 读数 |
|------|------|
| `pytest tests/unit/test_zhixing_publish_runtime_convergence.py` | 8 passed |
| `pytest` (发布面 4 suite: 新增 + release_identity + producer_binding + host_sync) | **69 passed** |
| `python3 bin/plan/bet-ledger.py lint` | `OK -- 612 bets, 17 tracks, no errors` |

## 5. 门禁实况 (预存红, 与本 diff 无关)

本机 `make gac-local-gate` 红在 `check-governance-ratio`:

```
[FAIL] check-governance-ratio :: bin/gac/check-governance-ratio.py --json
{
  "ok": false, "measured": true, "level": "blocking",
  "reason": "ratio 47.5% > ceiling 40%",
  "window_days": 30, "ratio": 0.4747, "total_runs": 158,
  "buckets": {"flex": 83, "governance": 75}
}
```

判据命令: `python3 bin/gac/check-governance-ratio.py --json`。

**为何与本 diff 无关** (逐条实测):

1. 该 check 读的是 `.omo/_delivery/agent-workflows/events.jsonl` —— `.gitignore:12`
   的 `.omo/_delivery/*` 面, **未被 git 跟踪** (`git ls-files` 无命中), 且在 worktree 与
   canonical 共享同一 inode ⇒ 读数是**本机运行账本**, 与任何 commit 的内容无关。
2. 该读数**先于本轮存在**: 剔除本轮 run `20261127T103557Z-bet-execution-2e6df02b` 后
   比值为 **47.77%** (flex 82 / governance 75 / total 157); 本轮 run 按 `bet-execution`
   命中 `FLEX_OVERRIDE_WORKFLOWS` 判为 `flex`, 反而把比值**拉低**到 47.47% ⇒ 本轮交付
   是该比值的**稀释项**, 不是成因。
3. CI 侧不受影响: 干净检出里没有这份账本 ⇒ check 自报 `measured=false, reason=no_ledger`
   并 exit 0 (缺输入不是仓库缺陷) ⇒ PR #5656 的 `gac-gate` 全绿。

⇒ 结论: 预存红, 归入「治理占比」这条**已知未收口**的主线 (继续用产品侧 flex 轮次稀释,
不动 `GOVERNANCE_CEILING` / `_classify` 判据面)。

## 6. 边界与残留

- **本轮不在本机执行任何一次真实发布** (机器级运行时变更, 属 principal 窗口)。
- **上宿主仍需两步**: 先 `bash bin/ssot/anchor-install-root.sh origin/main`
  (机器级: 运行时安装位 + code-main + 子模块 + omo venv), 再
  `zhixing-host-sync.py publish --file workbench_ui.js --file panorama-collect-main.py`。
  本 PR 把第二步变成**自带收敛验收的事务**, 第一步仍是 principal 的运行时窗口。
- **跨仓残留 (留给宿主仓裁决)**: 看门狗探针 `curl -s -o /dev/null --max-time 5` 缺
  `--fail` ⇒ HTTP 503 退出码仍是 0 ⇒ 只读态被判为「活着」⇒ 分级恢复链从不触发。
  ⇒ 503 形态的故障不会自愈, 只能由发布事务自己闭环。
- **同族残留**: `migrate()` 同样切 `current` 但不收敛运行期 (一次性迁移路径)。
