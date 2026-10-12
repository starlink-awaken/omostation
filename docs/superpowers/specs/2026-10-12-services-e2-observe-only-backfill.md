---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B4b 前置 — 2 条占用 com.omostation 命名空间的异主服务登记为 observe-only（E2 归零）
bet_id: BET-Y2Q4-T10-246
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-12
---

# ADR-0456 B4b 前置 — 异主 label 的 observe-only 登记，使 E2 = 0 成立

## 0 为什么是这一轮

B4b 的验收条款里有一条**中止判据**（`docs/plans/3y-bet-ledger.yaml` 与
`.qoder-cn/plans/nimble-bay-asp.md` §B4b 同文）：

> 每批切完 `--reality-check` E2 仍为 0。**中止判据：任一批后 E2 ≠ 0 即停。**

2026-10-12 实测（只读）：**E2 今天就已经不是 0** —— 批次 2 尚未开工，它自己的前置条件已经破了。
这一轮只做这一件事：把 E2 带回 0，并且**不碰本机 launchd**。
plist 改道本身是机器级动作，需要逐批授权，不属于本 BET。

## 1 实测底数（`--reality-check --json`，不声明 profile ⇒ 与所读检出同根）

| 读数（registry = `origin/main` @ `b884e2919`） | 值 |
|------|-----|
| installed_total（`~/Library/LaunchAgents` 枚举） | 66 |
| owned_installed | 43 |
| owned_declared | 40 |
| workspace_scoped（plist 字面引用本 Workspace） | **33** |
| E1 drift | 1（`com.omostation.zhixing-projection-fullrefresh`） |
| **E2 undeclared** | **3** |
| E3 lint debt | 0 |
| E4 prefix | False（12 条 `com.local.*` + `com.valvesoftware.steamclean` 未分区） |
| E5 enabled-missing | 1（`com.l4.omo.sync` 声明 enabled 但本机未装） |
| E5 disabled-residual | 1（`com.cockpit.dashboard` 声明 disabled 但本机仍装） |

E2 三条：`com.omostation.eg2-embeddings`、`com.omostation.zhixing-brief-watchdog`、
`com.omostation.panorama-compact-observation`。**本 BET 只登记前两条**，第三条见 §1b。

## 1b E2 的读数依赖「哪棵树」—— 这是 B4b 中止判据自己的陷阱

同一条命令、同一台机器、相隔 20 分钟，读数从 2 变成 3。先疑基线，不是先疑现实：

| 执行处 | registry | E2 |
|--------|----------|-----|
| `/Users/xiamingxing/Workspace` @ `d06571798` | 含 **11 条未 push 的本地 commit** | **2** |
| `origin/main` @ `b884e2919`（本 worktree base） | 权威交付树 | **3** |

差额恰是一条：`com.omostation.panorama-compact-observation` 由未 push 的
`ccecdd571 wip: 工作树快照兜底(...)` 在本地登记（plist mtime 2026-10-07T18:53:40），
而 `origin/main` 上 `panorama-compact-observation` **零命中**。

⇒ 三条纪律：① 本 BET **不登记它** —— 已有别的工作线在持有，我登记就会在那条线落地时
造出重复条目；② B4b 的「每批 E2 = 0」必须在**指明哪棵 registry** 的前提下读，
否则同机不同检出会给出不同判定；③ 主工作区有 11 条未 push commit 这件事本身只报告不处置
（并发会话的在制工作，禁动）。

本轮范围因此由「零命中」谓词界定，而不是由「E2 列表」界定：
只登记在 `origin/main` **与本工作区两侧都零引用**的 label。

⚠️ 顺带修正一处 plan 措辞：done_when 写的标尺是「指向 Workspace 的 plist 由 **43** → 0」，
本机实测该字面量口径是 **33**（43 是 B3 那次「owned_installed」的数，两个口径被混用过）。
本轮不改 plist，所以这条只是把 authorized 批次的真实标尺先量出来，不在这里处置。

## 2 这两条是谁的东西（决定登记的措辞，不是决定登记与否）

| label | plist mtime | 实际执行体 | 归属 |
|-------|-------------|-----------|------|
| `com.omostation.eg2-embeddings` | 2026-10-10T16:13:45 | `~/.local/share/eg2-runtime/venv/bin/python ~/.local/share/eg2-runtime/eg2_server.py`（KeepAlive + RunAtLoad） | `~/.local/share/eg2-runtime`，**本仓零引用**（origin/main 上 `eg2-embeddings` / `eg2-runtime` / `eg2_server` 命中 0 文件） |
| `com.omostation.zhixing-brief-watchdog` | 2026-10-12T10:00:34 | `/bin bash ~/dotfiles/bin/zhixing-brief-watchdog.sh`（RunAtLoad + StartInterval 120） | 另一个仓 `~/dotfiles`（commit `a63eb64`），**本仓零引用** |

⇒ **把它们的 `generate` 声明成 true、或写成本仓生成，就是造假记录。**
本仓对它们的真实关系只有一种：命名空间被占用 + 本机装着。

## 3 为什么只能登记，不能豁免

E2 的桶是按 `launchd_namespace.workspace_prefixes` 的**前缀**分类的（不是按 plist 里有没有
Workspace 路径）。`com.omostation` 在那 11 个前缀里 ⇒ 这两条必然落进 workspace 桶。
要让它落进「不要求声明」的那一侧，唯一的键是 `exempt_labels` —— 而
`bin/mof/gen-service-configs.py:478-480` 明确把「exempt 项被 workspace 前缀遮蔽」判成
E4 死数据：

```
shadowed = [i for i in exempt_items if match_workspace_prefix(i, prefixes)]
if shadowed: findings.append(f"E4 exempt 项被 workspace 前缀遮蔽 (死数据): {shadowed}")
```

⇒ 对 `com.omostation.*` 走 exempt 这条路**结构上不通**（加了会当场新增一条 E4）。
剩下的唯一诚实手段就是既有的 observe-only 机制。

## 4 机制：`generate: false` 的 observe-only 登记（BET-Y2Q4-T10-206 先例）

先例的 notes 逐字为：「plist 由本机手写/外部工具安装, 本仓不生成 (generate: false);
登记是为了让「已装 label == 注册表」可证。」同批 25 条同形态条目在案。

选它而不引入新风险，由三处实现决定：

- `--check`（E1 的来源）在 `bin/mof/gen-service-configs.py:645-652` 对 `generate: false`
  **直接 continue**，不做字节比较 ⇒ 新增这两条**不可能制造新的 E1 drift**。
- `validate_service_declaration()`（`:142-165`）在 `not svc.get("generate", True)` 时提前返回
  ⇒ 不要求 label/program 必填字段；`--validate` 里 `resolve_interpreter` 也被
  `if scheduler=="launchd" and not generate: continue`（`:627-629`）跳过 ⇒ CI 侧自洽检查不受影响。
- E5 判据（`:503-505`）：`enabled: true` ⇒ 必须已装。两条**都已装**，所以登记为 enabled 不会
  制造 E5；登记为 `enabled: false` 反而会撞上「disabled 却已装」，故不采用。

措辞纪律：`notes` 必须写清**异主 + 外部路径 + 本仓不生成 + 登记日期与状态**，让下一位读者
不会把它读成「本仓拥有这个 daemon」。`config_source` 沿用邻居的 `~/Library/LaunchAgents/<label>.plist`
写法；`program` / `outputs` 按 plist 实测值逐字节誊写（邻居同样写绝对路径，本文件是 host 快照面）。

## 5 ISC（每条自带反证）

1. **我拥有的两条从 E2 消失**。判据：`--reality-check --json --registry <候选 services.yaml>`
   ⇒ `e2_undeclared_labels == ["com.omostation.panorama-compact-observation"]`（恰剩那条
   由并发工作线持有、本 BET 明确不碰的）。反证：若两条里任一条还在列表里 ⇒ 它没进 workspace 桶的 declared 集合。
1b. **合上并发线后 E2 归零**（B4b 前置的完整形态）。判据：在 `/tmp` 把候选的两条 entry 叠加到
   主工作区那份 services.yaml（= 那条线落地后的状态）上再跑 `--reality-check --registry`
   ⇒ `e2_undeclared == 0`。该投影件不落仓、不提交，只作为本条读数的凭据。
   反证：若叠加后仍 ≥1 ⇒ 有我未识别的第 4 条占用。
2. **E1 drift 仍恰为 1，且仍是 `zhixing-projection-fullrefresh` 那一条**（不许新增、不许消失）。
   反证：若 drift 变 2 或条目换人，说明 `generate: false` 没被 continue 走到。
3. **E4 / E5 读数逐字未变**（不得为了 E2 制造新分类问题）。
   反证：新增任何一条 exempt ⇒ 必出「死数据」。
4. **`--validate` 绿**（CI 可验面，无本机 plist 依赖）。
5. **本机 launchd 零改动**：两条 plist 的 mtime 与 digest 在交付前后逐字节一致，
   `launchctl print` 状态不变。反证：任一 mtime 前进 ⇒ 我动了不该动的一侧。
6. **登记内容与 plist 一致**：`program.interpreter/entrypoint/args`、`outputs.*`、
   `run_at_load`、`interval_sec` 逐项对得上 plutil 转出的 JSON；`content_digest` =
   安装 plist 的 sha256。
7. **D0 铁律**：声明的每条 write_surface 都被 git 跟踪（`bet-ledger.py complete` 会拒）。

## 6 不在本 BET 边界内（只登记，不顺手修）

- E1 那 1 条 drift 的真实修复 = `gen-service-configs.py --write` + LaunchAgent 重载，
  属机器级动作，需授权。
- **`com.omostation.panorama-compact-observation`**：E2 的第三条，已由主工作区未 push 的
  `ccecdd571` 登记 —— 属另一条在制工作线，本 BET 不重复登记（§1b）。
- 主工作区 `/Users/xiamingxing/Workspace` 领先 `origin/main` **11 条未 push commit**：
  只报告不处置（并发会话的在制工作，禁动；这也是 E2 读数随检出变化的根因）。
- **BET-Y2Q4-T10-237**（G8 镜像面）碰的是同一个 `service-config-drift` 门禁与同一个
  `zhixing-projection-fullrefresh` 驱动 —— 那是别人的 BET，本轮不碰，只在交付说明里点出相邻性。
- **BET-Y2Q4-T16-01**（pending，同 T16 轨）做的是 `bin/scheduler-compile.py::check_drift()`
  的 launchd 分支 —— 那是**另一个装置**（crontab-only 的漂移门），装置与写面都不重合，
  本 BET 不声称对它有任何推进。
- E4 的 12 条 `com.local.*` + `com.valvesoftware.steamclean` 未分区、E5 的
  `com.l4.omo.sync`（声明 enabled 未装）与 `com.cockpit.dashboard`（声明 disabled 仍装）——
  各自独立，另案。
- 让异主工具改出自己的命名空间（改名 label）需跨仓协作，不在仓库单侧可做。
