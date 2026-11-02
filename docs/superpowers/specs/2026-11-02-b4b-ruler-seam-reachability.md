---
schema_version: specification/v1
spec_version: 1.0.0
title: B4b 验收尺的 repo_root 缝可达性修复
bet_id: BET-Y2Q4-T10-281
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-02
---

# B4b 验收尺的 repo_root 缝可达性修复

## 问题与范围

`bin/lib/repo_root.py` 的契约是：根是**参数不是事实**，`canonical_root()` 优先
`$OMOSTATION_ROOT`、其次按 MARKER 探测 `~/Workspace`、都定位不到即**抛错**；
`install_root()` 是定位器，在没有安装位的机器上返回 `None`，而 ADR-0456 B4b 一轮
（BET-Y2Q4-T10-265）明文规定「`install_root()` 返回 `None` 时抛错，绝不静默退回检出根」。

`scripts/tools/launchd-workspace-reality-check.py` 是 BET-Y2Q4-T10-272 交付的
**B4b 验收尺** —— 三年规划里「指向 Workspace 的 plist 由 43 → 0」这条判据的实际量具。
它 `:19` 把缝算成 `Path(__file__).resolve().parents[1] / "lib"`，即 `scripts/lib`。
2026-11-02 实测：该目录在检出根与安装位**两侧都不存在**（`exists=False`），
真正的 `repo_root.py` 在 `parents[2] / "bin" / "lib"`。于是 `:23` 的
`from repo_root import ...` **按构造恒失败**，每一次运行走的都是 `:25-31` 的
`except ImportError` 兜底，而兜底与契约三处背离：

1. `canonical_root()` / `code_root()` 硬编码某台机器的检出路径，**不读 `$OMOSTATION_ROOT`**；
2. `install_root()` 兜底返回 `~/.local/opt/omostation` 且**永不返回 `None`** ——
   尺在此处凭空造出一个 pin，正是 B4b 要消灭的那个谎；
3. 兜底把「缝不可达」折叠成「解析成功」，与 `repo_root.py:92-104` 的 fail-closed
   语义相反，所以尺永远不会因为自己瞎了而报错。

后果不是读数错乱，而是**读数失去承重**：本机字面量当前与真实根恰好等值，所以历史
receipt 里的「40 → 39」「install 位 0 → 1」（`docs/reports/2026-10-27-b4b-managed-cutover-pilot-batch1-closeout.md:26-27`）
值是对的，但对在巧合不在构造；一旦 profile 声明或 plist 改道到位，这把尺仍按字面量
判「指向 Workspace」，即**在目标达成时报目标未达成**。

本 BET 只修这一把尺（读侧，无写落点变更）。同形缺陷的第二例
`scripts/tools/spine-daily-ingress.py` 是**写者**，修它会移动 spine 数据面落点，
需与 6 处读者（其中两处在 cockpit / omlxc 子模块）同批迁移，不在本范围。

## 判据

- 缝按 `parents[2] / "bin" / "lib"` 计算；目录不可达时 `raise SystemExit`，不降级。
- 删除 `except ImportError` 兜底，`canonical_root` / `code_root` / `install_root`
  一律来自 `repo_root` 模块本体。
- `install_root()` 返回 `None` 时尺显式失败，不得用字面量补一个假 pin。
- 尺的源码内不得再出现机检出字面路径。

## done_when

1. `tests/unit/test_b4b_ruler_seam_reachability.py` 四条用例全绿：正向落点（三个
   resolver 的 `__module__ == "repo_root"`）、尺内无字面量、合成违规自证（把缝改回
   `parents[1]` 后守卫必须当场 `SystemExit`）、安装位缺席 fail-closed。
2. 尺在当前机器上的读数与修复前逐字段对比，差异**只有**分类根的来源变化，
   且对比结果写进 closeout receipt。

## 明确不做

- 不改 `scripts/tools/spine-daily-ingress.py` 的写落点（见 BET 候选 #174，需署名裁定）。
- 不扩 `tests/unit/test_writeplane_root_pin.py` 的枚举面到 `scripts/**`；那是尺尺的
  改造，需按 AGENTS.md §7④「匹配 resolver 而非变量名」单独设计，另案登记。
- 不动 `profile_base` 的 `Path.home()` 派生（它是机器级 profile 基址，不属于检出根
  语义，本 BET 的判据不覆盖它）。
