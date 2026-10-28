---
schema_version: specification/v1
spec_version: 1.0.0
title: lib/ 常驻 wrapper 的仓根必须由脚本自身位置推出 —— 码面跟随入口，不跟机器
bet_id: BET-Y2Q4-T10-275
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-10-28
---

# BET-Y2Q4-T10-275 — lib/ wrapper 根自解析（ADR-0456 B4b 码面残差）

> 范围：三个 launchd wrapper 脚本的根解析。不改 `services.yaml` 的注册表内容
> （是否给这三条声明 `runtime_root: install` 属 B4b 批次 2+，principal 授权面）。

## 1. 问题（实测，基线 `9de3ba966`）

ADR-0456 B4b 把常驻族的**入口**改到了安装位 `~/.local/opt/omostation/lib/*.sh`，
而 T10-266 记录的判据是：入口在 A 树、执行的**码面**在 B 树，就是没改道。
`lib/resident-role-tick.sh:27-29` 已按 `BASH_SOURCE` 自推根，因此
`--reality-check` 的 `e6_non_ok = 0`；同一口径下另有三条**未声明 `runtime_root`**，
因而不在 E6/E7 覆盖面内，且逐字面把检出的绝对路径烤进了脚本：

| 文件 | 行 | 字面量 |
|------|----|--------|
| `lib/agora-daemon.sh` | `:7` | `cd /Users/xiamingxing/Workspace/projects/agora` |
| `lib/agora-sse.sh` | `:6` | `--project /Users/xiamingxing/Workspace/projects/agora` |
| `lib/bet-claim-gc.sh` | `:9` | `python /Users/xiamingxing/Workspace/bin/plan/bet-ledger.py` |

后果不是「难看」而是可测的：安装位那份 `lib/agora-daemon.sh` 与检出的那份
**逐字节相同**，所以从安装位启动的 daemon 实际 `cd` 进检出树并跑检出的码面 ——
这正是 B4b 要消灭的那个谎，而 E1（只比 plist 文本与注册表渲染）对它结构性失明。

## 2. 契约

**C-1（根自解析）**：`lib/*.sh` 中指向本仓内部的任何路径，一律由
`_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` +
`_REPO_ROOT="$(cd "$_SELF_DIR/.." && pwd)"` 派生。安装位与检出根各自自推，互不引用。

**C-2（禁止主机字面量）**：`lib/` 下的受跟踪 shell 包装脚本中不得出现
`/Users/<name>/` 形态的绝对路径字面量。外部工具路径不在禁止之列
（`/opt/homebrew/bin/uv` 是宿主二进制，不是仓根，按 ADR-0435 的 uv-run 形态保留）。

**C-3（语义不变）**：自解析只替换路径的**来源**，不改变每条命令的语义 ——
`agora-daemon.sh` 仍先 `cd` 进 agora 项目再 `uv run python src/agora/daemon.py`，
`agora-sse.sh` 仍是 `uv run --project <agora> agora-mcp --sse`，
`bet-claim-gc.sh` 仍是 `uv run --with pyyaml python <repo>/bin/plan/bet-ledger.py claim-gc`。

**C-4（判据须正向落点）**：C-2 不得只用「改后计数为 0」证明。
同一次扫描必须同时产出「改前为 N」的反基线读数，且检测器要能对自己的
合成违规样本命中（AGENTS.md §7⑤「改后为 0 必须与改前为 N 由同一次扫描产出」）。

## 3. done_when（逐条可判）

1. 三个文件不再含 `/Users/` 字面量；`git grep -c "/Users/" -- 'lib/*.sh'` 读数为空。
2. 每条 wrapper 的 `bash -n` 语法检查通过。
3. 新增用例 `tests/unit/test_lib_wrapper_root_self_resolution.py`：
   - 反基线：对 `origin/main` 那一份（或本 BET 分支的改前副本）断言检测器命中 **3** 处；
   - 改后：断言命中 **0** 处；
   - 自证：向一份合成 wrapper 注入 `/Users/someone/Workspace/projects/x` 断言被点名；
   - 反面：对 `/opt/homebrew/bin/uv` 断言**不**被点名（否则尺过宽，会把合法形态也判死）。
4. 用例在 `HOME=<空目录>` + `env -u OMOSTATION_ROOT` 的最小 venv 下可跑（hermetic 纪律）。

## 4. 不在本轮范围

- 不给这三条服务声明 `runtime_root: install`（注册表内容 = principal 授权面，#91）。
- 不改 launchd plist、不 `bootout`/`bootstrap`（机器侧半是 principal 决定）。
- 不碰 `lib/` 之外的绝对路径残留（另有面，另开 BET）。
- 不改 `bin/gac/check-services-runtime-root.py` 的 E6 准入条件（把它扩到未声明
  `runtime_root` 的条目是独立工程腿；本轮的 C-2 判据先由测试钉住，不新增门禁 flag）。

## 5. 回路断路条件

- 若为了让用例变绿需要把检测器写成「只匹配 Workspace」这种按构造就绿的形式 → 停止。
- 若「正向落点」只能靠人工读数支撑而无用例 → 停止，那正是 AGENTS.md §7 记过的塌缩形状。
