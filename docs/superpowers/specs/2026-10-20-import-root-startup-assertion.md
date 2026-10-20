---
schema_version: specification/v1
spec_version: 1.0.0
title: 跨安装位 import 错包的启动断言与检出钉面可观测化
bet_id: BET-Y2Q4-T10-261
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-20
---

# 跨安装位 import 错包的启动断言与检出钉面可观测化

> 契约对象：`bin/lib/repo_root.py` 新增 `assert_import_root()` / `import_root_report()`；
> `roots_report()` 的 `--json` 面新增一条可观测字段。
> 上游：ADR-0456 §Consequences 第 246—247 行（「跨安装位 import 错包 →
> 启动断言 `omo.__file__` 落在期望 code_root 下」），本 spec 是那条缓解的交付面。

## §0 前提 —— 本轮实测，不是引用

四条读数全部在 `origin/main@f13ef01c3` 上取，装置与被检对象同源：

| # | 观测 | 实测值 |
|---|---|---|
| M1 | `projects/*/.venv/**/site-packages/*.pth` 里把导入根指向 `/Users/xiamingxing/Workspace/…` 的条数 | **39 条 / 14 个 venv**（含 `projects/omo/.venv/…/omo.pth → /Users/xiamingxing/Workspace/projects/omo/src`，以及 agora / aetherforge / l4-kernel / metaos 的交叉钉） |
| M2 | 从 `/tmp` 用 canonical venv 跑 `uv run --no-sync --project projects/omo python -c "import omo"` | `omo.__file__ = /Users/xiamingxing/Workspace/projects/omo/src/omo/__init__.py`，`WORKSPACE_ROOT = /Users/xiamingxing/Workspace`，`TRUTH_DIR = …/.omo/_truth` |
| M3 | 同一条命令但声明 `OMOSTATION_STATE_ROOT=/tmp/fake-state-root` | `STATE_ROOT = /tmp/fake-state-root`、`STATE_DIR = /tmp/fake-state-root/.omo/state` —— **写面跟 profile，读面（M2）不跟** |
| M4 | 新 claim 的 worktree（`ws-t10-261-import-root-assert`）里 `projects/omo/.venv` | **不存在**；`uv run --no-sync` 当场 `ModuleNotFoundError: No module named 'omo'` |

M3 修正了 ADR-0456 §7 第二条的一种过度读法：内核侧的分叉是**码根/读面**的分叉，
不是写面的分叉 —— 写面（`STATE_ROOT`/`STATE_DIR`）今天已经跟 profile。
M4 界定了危险的实际形状：worktree 自带 venv 时解析到**自己**（`uv run` 会现建），
所以危险面不是「在 worktree 里跑」，而是**解释器在检出之外、venv 由 canonical 供给**
的那类调用 —— 也就是 launchd/cron 起的常驻进程与任何 `python3 -c` 直连。
这正是 ADR-0456 :246 记的那次事故（「venv `.pth` 装的 workspace 副本会赢过 worktree」）。

## §1 为什么不在本轮把硬断言接常驻入口

把 `assert_import_root()` 无条件塞进 `omo` 的导入路径，今天在 canonical 上是**恒等式**
（M2：两者逐字节相同），所以它现在不会咬到任何在跑的东西。它第一次真正有机会咬人，
是 B4b 批次 2 把 plist 改到安装位之后：那时 `code_root()` 指向 `~/.local/opt/omostation`，
而 M1 那 39 条 `.pth` 仍指向 Workspace —— 断言**应当**红，但红的方式是让常驻进程
启动即崩、launchd 进 crash-loop。

那个时刻的正确性属于改道动作本身，不属于这一轮：B4b 批次 2+ 是逐批授权面
（plist / crontab / `~/Library/LaunchAgents` 全在署名裁定域内），本轮既不动 plist 也不动 cron。
所以本 spec 把这条缓解切成两段，各自可验、各自可回滚：

- **本轮（C1—C4）**：把判定做成**可调用的缝 + 门禁 + 可观测面**，并让「哪个检出的码在跑」
  第一次变成一个能被读出来的量。语义完整，咬合点未接线。
- **接线轮（显式后继，不在本 spec 交付）**：B4b 批次 2 的第一个 plist 改动**必须同时**在
  常驻入口调 `assert_import_root()`，否则那批改动把系统换成「改道了但没人知道自己换了码」的状态。
  这条前后顺序由本 spec §5 登记，不靠记忆。

把「接线」推迟不是把判据改窄：判据（落在期望 code_root 下，否则失败）在本轮就完整存在且被测试钉住，
被推迟的只是一个调用点的落地时机，而那个时机的正确性依赖一个未授权的动作。

## §2 契约条款

**C1 —— `assert_import_root(module_file, *, root=None) -> Path`**
落在 `bin/lib/repo_root.py`，进 `__all__`。语义：

- `module_file` 是被检对象的 `__file__`（或任何包内文件路径）；`root` 缺省取 `code_root()`。
- 两侧各做 `resolve()` 后判「`module_file` 是否在 `root` 之下」（含等于 `root` 本身）。
- 在之下 ⇒ 返回解析后的 `root`；不在之下 ⇒ 抛 `ImportRootMismatch(ValueError)`，
  消息**同时**给出两侧绝对路径与「哪一条 `.pth` 造成的」提示（不猜，只把两个根打出来）。
- 空 / `None` / 相对路径输入 ⇒ 同样抛，不得静默通过（「读不出来」与「读出来没问题」必须可分）。

**C2 —— `import_root_report(module_file=None, *, root=None) -> dict`**
非抛出版，供诊断面用。键固定为 `{expected_root, module_file, under, ok}`；
`module_file=None` 时探的是 `repo_root` 自己所在检出的码根，`under` 为 `null` 表示无从判定
（不得把「判不了」折叠成 `true`，AGENTS.md §7⑨ 同族）。

**C3 —— `roots_report()` 增一条可观测字段**
`--json` 输出增加 `import_root`（由 C2 在 `OMOSTATION_IMPORT_PROBE_MODULE` 指定时产出；
未指定 ⇒ 该字段为 `{"probed": false, ...}`，**不是** `ok: true`）。
目的：让 `make runtime-install-root` / `python3 bin/lib/repo_root.py --json`
第一次能把「码根与导入根不一致」打在屏幕上，且**不影响任何退出码**。

**C4 —— 退出码语义不变**
`repo_root.py main()` 的退出码判据逐字不改。本契约只加观测面与一个可调用断言，
不加「探到不一致就非零」—— 那是接线轮的语义（§1）。

## §3 门禁（可执行，非叙述）

G1 `tests/unit/test_repo_root_import_root_assertion.py`：
  ① 正向 —— canonical 形状（`root=<d>/x`，`module_file=<d>/x/pkg/m.py`）返回 root 且不抛；
  ② 反向 —— `<d>/other/pkg/m.py` 必须抛，且异常消息含两侧绝对路径；
  ③ 边界 —— `module_file` 为空 / 相对 / `None` 三种输入一律抛；
  ④ 变异对照 —— 把 `under` 判定改成恒 `True` 后 ②③ 必须当场红（防「按构造就绿」）。

G2 同一文件里钉真实面：以 M2 的形状构造一个「码根 = worktree、导入根 = canonical」的
合成对，断言 `import_root_report()` 报 `ok=false` 且 `under=false`；
再以 M4 的形状（同根）断言 `ok=true`。两侧由同一次扫描产出，只断言一侧即红。

G3 `repo_root.__all__` 与解析器名单的既有不变式不被破坏：新函数**不得**被
`test_writeplane_root_pin.py` 一类按零参 callable 探测 profile 根的判据误认成根解析器
（`assert_import_root` 有必填参数，按构造不命中；须有一条用例钉住这点，不能靠推断）。

## §4 完成判据（每条都是实测命令）

1. `python3 -c` 在最小 venv 下跑 G1/G2 ⇒ 全绿；注入 G1-④ 的变异 ⇒ 当场红。
2. `python3 bin/lib/repo_root.py --json` 输出含 `import_root` 键，且未设探针 env 时
   `probed=false`；设 `OMOSTATION_IMPORT_PROBE_MODULE=…` 后 `ok` 为布尔。
3. `git diff --name-only origin/main..HEAD` 不含 `.omo/state/**`、`BRIEF.md`、子模块 gitlink。
4. `crontab -l` 与 `~/Library/LaunchAgents` 的计数/哈希在交付前后逐字节相同（运行面零效应，
   用 python 计数并同打绝对量，不走 `| grep -c`）。
5. M1—M4 四条读数在合并后的 `origin/main` 上可逐条重放。

## §5 明确不做（与理由）

- **不**在 `omo` / 常驻守护进程的任何入口调用硬断言（§1：那会让 B4b 批次 2 的改道变成
  crash-loop 保险丝，而改道本身是逐批授权面）。
- **不**动 launchd / plist / crontab / `~/Library/LaunchAgents`；**不**动 `services.yaml`。
- **不**修 M1 那 39 条 `.pth` —— 那是各 venv 的 editable 安装产物，重建 venv 是运维动作，
  且「谁该指向哪棵树」取决于 B4b 的最终拓扑，现在改就是把未定的裁定固化。
- **不**宣布 ADR-0456 B1/B3/B4/B5 或整个 plan 完成。
- **不**引入 `OMO_ALLOW_GIT_WRITE`（属决策 3 / B4b 批次 2，已有 4 份 spec 一致记为逐批授权）。
- **不**把 `tests/unit/**` 扩进 CI 白名单之外的新面：本 spec 的新测试文件按既有
  `governance-check.yml` 的显式清单接线方式处理，接不接线由那条清单自己的判据说。
