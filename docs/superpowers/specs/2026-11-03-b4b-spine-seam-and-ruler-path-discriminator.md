---
schema_version: specification/v1
spec_version: 1.0.0
title: B4b 最后一个写者残差——spine-daily-ingress 的 repo_root 缝不可达，并修验收尺的 PATH 假阳
bet_id: BET-Y2Q4-T10-282
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-03
---

# B4b 最后一个写者残差：spine-daily-ingress 缝不可达 + 验收尺 PATH 假阳

## 0. 事实（全部为 2026-11-03 在 `origin/main` 上的实测，不用推断）

### 0.1 写者侧缺陷（本 BET 的主件）

`scripts/tools/spine-daily-ingress.py`：

| 行 | 内容 | 后果 |
|---|---|---|
| `:29` | `_LIB_DIR = Path(__file__).resolve().parents[1] / "lib"` | 解析为 `scripts/lib`，实测检出与安装位**两侧都不存在** |
| `:33` | `from repo_root import code_root, state_root` | 缝不可达 ⇒ 必抛 `ImportError` |
| `:34` | `except ImportError:` | 静默兜底入口 |
| `:36` / `:38` | 两个函数都 `return Path("/Users/xiamingxing/Workspace")` | `code_root()` 与 `state_root()` 同时钉死某台机器的检出根 |

与 `BET-Y2Q4-T10-281`（已闭环，尺侧）是**同一个错误形状**，但那里是**量具**（看不见），这里是**写者**（正在写错地方）：声明 `OMOSTATION_STATE_ROOT` 之后，本应落到 state 根的 spine 写面仍落检出根，profile 在该脚本上按构造不生效。

### 0.2 验收尺侧缺陷（本 BET 的副产品，它挡住 B4b 判据的正确读数）

`scripts/tools/launchd-workspace-reality-check.py` 判 `pointing_to_workspace_count` 用的是**整份 plist 文本子串命中**。2026-11-03 实测读数：

```
schema=launchd-workspace-reality-check/v1  total_plists=85
pointing_to_workspace_count=2  pointing_to_install_count=40  other_count=43
```

逐份读原文后，这 2 条命中性质不同：

- `com.omostation.test-archive-purge-7d` —— **真在范围内**：argv 为 `cd /Users/xiamingxing/Workspace && /opt/homebrew/bin/python3.13 bin/ops/purge-test-archive-7d.py …`，另有工作目录与两份日志路径共 4 处检出根字面量。
- `ai.hermes.gateway` —— **尺的假阳**：`/Users/xiamingxing/Workspace/bin` 只出现在从用户 shell 继承的 `PATH` 环境变量串里，不是该服务自己的入口、工作目录或写落点。

⇒ 计划里「指向 Workspace 的 plist 由 43 → 0」这条判据的**真实剩余是 1 条**，但只要尺仍按整文本子串计数，这条判据**永远差一个假阳而无法读到 0**。修尺不是化妆：它是让判据可被满足的前提。

## 1. 目标态

1. `scripts/tools/spine-daily-ingress.py` 的三个 resolver 全部来自 `repo_root` 模块，缝不可达与安装位缺席都**显式失败**，不再有字面量兜底。
2. `scripts/tools/launchd-workspace-reality-check.py` 的 workspace 计数只认**该服务自己的码根/工作目录/写落点**，PATH 元素不计入；同时保留一条反证，证明放宽后仍能命中真字面量。

## 2. done_when（每条都可实测，且写明读数来自哪把尺）

1. spine 侧：`code_root` / `state_root` 的 `__module__` 均为 `repo_root`（正向落点断言），且脚本源码内无任何检出根字面量。
2. spine 侧合成违规自证：把缝改回 `parents[1] / "lib"` 后守卫当场 `SystemExit` 并点名「缝不可达」；摘掉守卫则该用例红。
3. spine 侧写落点判据：声明 `OMOSTATION_STATE_ROOT=<tmp>` 后实跑一次该脚本的写路径，产物落在 state 根而**不是** `<CWD>` 或检出根——这条是**正向落点**断言，不用「检出里没有」这种否定式。
4. 尺侧：对 `ai.hermes.gateway` 不计入 workspace 桶（读数 2 → 1），对 `com.omostation.test-archive-purge-7d` 仍计入；两条断言必须来自**同一次扫描**。
5. 尺侧反证：把 PATH 判别写成「整行丢弃」时，真字面量用例必须红（防第 4 条靠放宽蒙过）。

## 3. non_goals

- **不在本 BET 里迁移 `Workspace/.omo/state/spine-diff-buffer.jsonl`** —— 改缝会让该文件的新写入落到 state 根，历史数据的归属与 6 处读者（含 `projects/cockpit`、`projects/omlxc` 两子模块）是否同批改，属机器级数据面搬迁，需逐批授权（见 ADR-0456 B4b 批次 2+）。本 BET 只把「写落点由 profile 决定」这一件事变成真的，并在 receipt 里如实记录迁移仍未做。
- 不改任何 plist、crontab 或机器级配置。
- 不扩 `tests/unit/test_writeplane_root_pin.py` 的枚举面到 `scripts/**` —— 属「尺尺」改造，另案。

## 4. 中止判据

若 spine 写落点的改法会导致**已存在数据面被孤立**（新写 state 根、历史留检出根）而迁移未获授权，则**停止实现**，保留本 spec 与实测证据，把该 BET 停在 `in_progress`，不上 `done`。
