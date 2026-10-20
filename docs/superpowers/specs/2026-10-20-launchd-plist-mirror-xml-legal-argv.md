---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B3 附属债 — 仓内唯一不可解析的 launchd plist 镜像去非法化，确切命令行移到 `--` 合法的一侧而不是删掉
bet_id: BET-Y2Q4-T10-260
status: accepted
lifecycle: contract
last-reviewed: 2026-10-20
owner: governance-team
schema: md/v1
---

# 1 读数 — 缺陷是什么、由哪棵树产出

立项前实测（2026-10-20T02:52Z），注册表树 = `origin/main@0329ceeb3`，隔离检出
`~/ws-t10-260-plist-argv` HEAD 与该 SHA 逐字相同。

```
uv run --no-project --with pytest --with pytest-timeout --with pyyaml \
  python -m pytest tests/unit/test_launchd_plists_xml_safe.py -q -p no:randomly
→ 2 failed, 2 passed
   FAILED tests/unit/test_launchd_plists_xml_safe.py::test_every_launchd_plist_parses_with_plistlib
   FAILED tests/unit/test_launchd_plists_xml_safe.py::test_plist_comments_contain_no_double_hyphen
```

唯一 offender 一行，逐字：

```
com.omostation.panorama-refresh-guard.plist:26: python3 bin/gac/panorama-refresh-guard.py --json --dry-run
```

三点定性：

1. **不是风格问题，是可用性事实**。XML 规范禁止注释体内出现连续两个半角连字符，`plistlib` / expat
   因此整份拒绝：`ExpatError: line 26, column 48`。这份镜像按它自己注释里写的
   `cp` + `launchctl bootstrap` **根本无法安装** —— 与实测一致：
   `~/Library/LaunchAgents/com.omostation.panorama-refresh-guard.plist` 不存在（该目录共 77 份 plist）。
2. **检测器是对的，红是可见性缺陷**。`tests/unit/test_launchd_plists_xml_safe.py` 的断言命中正确；
   而 `.github/workflows/governance-check.yml:118-127` 是显式 pytest 文件白名单、不含 `tests/unit/**`
   （AGENTS.md §7 已记该盲区），所以 CI 恒绿、main 恒红。本 BET **不**扩白名单（见 §4）。
3. **argv 是真信息**。`--json` / `--dry-run` 由 `bin/gac/panorama-refresh-guard.py:74-76` 的
   argparse 提供，是这份 job 唯一的人工核验入口；删掉注释里的这行会让下一轮准入评审（task #124
   的 21 条清单）重新失去可核验性。

# 2 契约

- **C1（合法性）** 交付后 `bin/ops/launchd/com.omostation.panorama-refresh-guard.plist` 必须可被
  `plistlib.loads()` 解析（exit 0），且 `tests/unit/test_launchd_plists_xml_safe.py` 四条全绿。
- **C2（信息保全）** 确切命令行 `python3 bin/gac/panorama-refresh-guard.py --json --dry-run` 必须在仓内
  仍可 `git grep` 命中，且命中位于 `bin/gac/panorama-refresh-guard.py` 的模块文档（不是 plist 注释）。
  即修法是把 argv 移到 `--` 合法的一侧，**不是**把它从 plist 里抹掉。
- **C3（不得骗检测器）** 不得放宽 `tests/unit/test_launchd_plists_xml_safe.py` 的判据、不得给该文件加豁免、
  不得只把注释挪到 `<!DOCTYPE` 之后 —— 第三形只改检测器的提前 `break`，expat 仍整份拒绝，属
  「按构造就绿」（AGENTS.md §7③）。
- **C4（运行面零效应）** 不写 `~/Library/LaunchAgents`、不 `bootout` / `bootstrap` / `kickstart`、
  不改 crontab。验收必须含一条**运行面未变**的正向读数，而不是「我没执行写命令」的自我声明。
- **C5（不替人决定）** 本 BET 只消除 XML 非法性，不判定 `com.omostation.panorama-refresh-guard`
  该不该活、该不该装 —— 那是 task #124 的署名准入清单。
- **C6（判据用 python 计数）** 凡「某文件不存在 / 某目录份数」类验收一律用 python 遍历计数，
  不用 `ls | grep -c`（零匹配断链 + 本机 `ls`/`grep` 是别名，AGENTS.md §7⑤）。

# 3 修法

补丁形状已在临时副本上由**检测器自身**验算通过（不是人眼判断）：

```
plistlib parses OK; Label = com.omostation.panorama-refresh-guard
detector offenders = []
docstring carries the exact argv: True
script still parses OK          # ast.parse
```

两面各一处改动：

| 文件 | 改动 |
|---|---|
| `bin/ops/launchd/com.omostation.panorama-refresh-guard.plist` | 第 26 行注释体内的确切命令行换成指针句，注释内不再出现 `--` |
| `bin/gac/panorama-refresh-guard.py` | 模块文档增加一节 `Manual check`，逐字承载该 argv（`--json --dry-run` 合法，因为在 Python 侧） |

# 4 明确不做

- 不把 `tests/unit/**` 接进 CI 白名单。这是独立问题（受影响面远大于本文件），如实登记另行提出。
- 不把 plist 里的 `/Users/xiamingxing/Workspace` 字面量改成缝 —— 属 ADR-0456 B4b 改道，逐批授权。
- 不收口安装器（直写 launchd 而不产注册表条目的通道是另一条 BET）。
- 不宣布 ADR-0456 B1 / B3 / B4 / B5 或整个 plan 完成。
