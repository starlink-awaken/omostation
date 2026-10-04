---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-04
type: report
bet_id: BET-Y2Q4-T10-225
title: BET-Y2Q4-T10-225 closeout — 六类静默失效形状固化 + 台账 tail-append 重建配方
---

# BET-Y2Q4-T10-225 closeout — 固化的是「安全网不响了」这一类，不是六个新 bug

契约：`docs/superpowers/specs/2026-10-04-bet-225-agent-perception-six-new-pitfall-classes.md`
（`sha256:2b2ec6ae79f41eb75bf468d92a09f702f1f890148a1f405454b213a66063a94e`，台账绑定逐字节一致）
台账：`docs/plans/3y-bet-ledger.yaml` 条目 `BET-Y2Q4-T10-225`
run：`20261004T114355Z-project-doc-change-a1f42628`（六条 write_surface 全 claim，
affected receipt `runtime/affected/t10225.json`，`--changed-projects workspace-root`）
交付：PR #4629 squash-merged as `b0f9b497c`（基线 `origin/main@394d8b930`，合并时 main 已前进到 `7b64b81aa`）

## 1. 交付了什么

纯文档轮，211 added / 2 deleted，四个文件，零 `.py`、零 registry、零门禁代码：

| 文件 | numstat | 内容 |
|---|---|---|
| `AGENTS.md` | +8 / −1 | §7 新增「六类会让判定静默失效的形状」①–⑥；就地修正 ⑥ 点名的两条陈旧指针（改用符号名） |
| `docs/SOPs/ledger-closeout-sop.md` | +36 / −0 | §3.6 台账 tail-append 冲突**重建**配方 + Step 4.2 误用纠正 + §7 清单挂钩 |
| `docs/plans/3y-bet-ledger.yaml` | +87 / −1 | 新条目 `BET-Y2Q4-T10-225`（spec 绑定 + 5 条可执行 `verify`）；`meta.total_bets` 519→520 |
| `docs/superpowers/specs/…-bet-225-….md` | +80 / −0 | 契约：准入规则、六条内容、判据 V1–V6、写面、非目标 |

准入判据沿用 T10-221：**复发 ≥2 次，或当场让安全网/验收判据静默失效**，且**有不依赖本机状态的指认方式**。
六条全部命中「让安全网失效」这一支，没有一条是「又一个 bug」。

## 2. 六条的形状与指认方式（详述见 spec §2 与 AGENTS.md §7）

1. **E1 YAML 重复键静默 last-wins** — `yaml.safe_load` 不抛异常。实证：`.omo/cron/registry.yaml` 两条
   panorama 记录各带两个 `reality` 键（dup-aware 扫描 2 处 / 其余 68 条干净），文件同时印着「已装机」与
   「待装」而所有读者只看到一个值。判据形状：`tests/unit/test_cron_registry_reality_invariants.py` 的
   `test_duplicate_key_detector_is_not_a_no_op` + `test_safe_load_alone_would_have_missed_that_violation`。
2. **E2 时钟炸弹** — fixture 写绝对 `generated_at` × 断言用相对新鲜度窗口，跑得越晚越红，且与真回归用眼景区分不开。
   指认：`grep -rn "write_text.*generated_at:[ ]20" tests/unit --include="*.py"` 必须 CLEAN。
3. **E3 按构造就绿** — 断言前提由 fixture 自己 `write_text` 写出，绿本身不构成证据。
   判据：变异对照（T10-222 把 `legacy.write_text(` 换成 `pass` 得 `MUTATION_EXIT 1`）或合成违规自证；
   反面同族：被检对象的根不得由 `__file__` 反推。
4. **E4「no checks reported」第一因是 `CONFLICTING`/`DIRTY`** — 不是 `on.paths`。实证 PR #4623。
   判据：先 `gh pr view --json mergeable,mergeStateStatus`；并记住 `governance-check.yml` 的
   `on.pull_request.paths` 不含 `tests/unit/**` ⇒ 那批用例「CI 绿」不是它们的证据。
5. **E5 Bash 工具 = zsh + 别名，Python 子进程 = 真实二进制** — 实测 `grep→rg`、`find→fd`、`ls→eza`、
   `cp→cp -iv`；`subprocess(shell=True)` 不继承别名。踩坑读数：`grep -iE` → `rg: error parsing flag -E`、
   `find -name` → fd 用法错、`ls -lat` → 非法 `--time`、`cp` 对已存在文件 rc=1 而目标逐字节未变。
6. **E6 行号指针随上轮交付漂移** — 本轮实测：`test_projection_reader_resolution.py:42` 与
   `test_repo_root_profile.py:146` 写在 T10-221 基线上，T10-222 重写后分别变成 `registry = next(...)` 与
   TRUTH_DIR 注释，断言本体移到 `:61` / `:174`，而引用它们的文档逐字未变、读起来依然权威。
   纪律：优先符号名、行号只作辅助、引用前 `git show origin/main:<path>` 取该行核内容。

外加**台账 tail-append 冲突重建配方**（SOP §3.6）：`meta.total_bets` 是派生值，两侧都 +1 写成同一个数字时
git 静默合并成功、声明开始说谎而 diff 一片干净（先例 `BET-Y2Q3-T10-202.md:82-84`：双方都从 458 写成 459，
实际 460 条、零残留）。正确解法是**重建**而非选择某一边，配三条缺一不可断言。该配方同时纠正 Step 4.2
「冲突处理优先保留 main 版」在台账上的致命误用。

## 3. 合并后真树复跑（operational 证据）

在**新建 detached 检出** `/Users/xiamingxing/verify-t225` @ `b0f9b497c`（`git worktree add --detach`，
`SKIP_SUBMODULE_INIT=1`，本机 `.omo/state/**` 写面与 profile env 一律不参与）复跑：

```
$ python3 bin/plan/bet-ledger.py verify BET-Y2Q4-T10-225 --execute
  anchors=6                                    # ①–⑥ 锚点齐备
  symbol=True stale=False                      # 陈旧行号指针已换符号名
  missing=[]                                   # §3.6 配方 + 三条断言齐备
  OK -- 520 bets, 16 tracks, no errors         # lint：含本 BET spec 绑定 digest 校验
  9 passed in 0.23s                            # tests/unit/test_cron_registry_reality_invariants.py
  零 FAIL 行

$ python3 bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked
  doc-governance-check: PASS (4554 files, 147 warnings)
```

指针解析审计（E6 的自我要求，逐条在合并树里量，不引用记忆）：新段落内 13 个 backtick 引用，
**missing files = 0**；两条内容断言实测成立 ——
`tests/unit/test_projection_reader_resolution.py:42` = `registry = next(doc["projections"] for doc in registry_docs …`，
`tests/unit/test_repo_root_profile.py:146` = `TRUTH_DIR 下那份), 映射一旦漂移, 手写期望路径只会把漂移…`。
即 ⑥ 里写的「`:42` 变成一行 `registry = next(...)`、`:146` 变成一段 TRUTH_DIR 注释」在 main 上是**当下为真**的陈述。

squash-merge 完整性：`git show --stat b0f9b497c` = 4 文件 211/2；对**新 base** `7b64b81aa` 的 AGENTS.md delta
恰为 +8/−1 且 8 个自有标记全在；main 侧同期并发内容逐条存活（`memory 索引…硬容量`、
`判据报警先 print 原始行再定性`、`Bash 工具跑的是 zsh` 三条均 OK）；三个未并发改动的文件 blob 逐字节相同
（`3608851ad9` / `5015507ba5` / `88fb8f13bd`）。

## 4. 台账 tail-append 三条断言（插入后实测）

```
meta.total_bets 520 == len(bets) 520
重复 id 0
main 侧 status: done 转换 515 → 515 逐条存活
```

合并树复算（§3 同一检出）读数一致：`total 520 len 520 dupes 0 done 515 has225 True`。

## 5. 回滚

单提交回滚：`git revert b0f9b497c`（四文件一次撤销，无代码、无状态迁移、无子模块 gitlink）。
台账侧注意：`total_bets` 随 revert 回到 519，条目 `BET-Y2Q4-T10-225` 一并消失，不会留下 `META_TOTAL_BETS_DRIFT`。
不需要数据面动作。

## 6. 边界与未做

- **CI 可见性缺口未收**（E4 的直接后果）：`governance-check.yml` 的 pytest 白名单不含 `tests/unit/**`，
  所以 E1 的判据形状只在本地/本 receipt 里成立。把它提升到 CI 可见面是独立后续项，不在本 BET 非目标之外硬塞。
- **不改门禁代码**：spec §5 明确 non_goal；本轮只动感知面（AGENTS/SOP）+ 台账。
- **`docs/architecture/ops-services-health.md` 未动**：它是 `type: ephemeral`，真值在 `.omo/cron/registry.yaml`；
  往 ephemeral 文档写基建感知会让下一个 agent 找不到权威。
- **B4b 批次 2+（43 个 plist 改道）仍需逐批授权**，本轮只是它的前置感知轮。

## 7. 收尾

- PR-1 `#4629` → `b0f9b497c`（22/22 checks 绿，`mergeable=MERGEABLE`、`mergeStateStatus=CLEAN`）。
- PR-2 = 本 receipt + retro + 台账 `done` 转换（`bet-closeout-chain` 步 7）。
- L3 深度安全审查：commit set `bf4bd9479` → findings 0。
- 清理：`ws-t10-225-perception` 与 `verify-t225` 两个 worktree 在交付后移除；`runtime/affected/` scratch 不进 commit。
