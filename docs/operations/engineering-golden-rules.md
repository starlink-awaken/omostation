# Engineering Golden Rules — 工程铁律 (防复发模板)

> 差距治理 S4 (UX-NOISE / 模板固化) 产出。
> 背景: PR #2058 修复的 2 个预存 flaky 问题, 固化为工程模板防止复发。
> 每个规则都有实证根因 (来自真实事故), 不是理论建议。

## TP-RELATIVE: 测试时序相对断言铁律

**触发**: 任何时序敏感测试 / CI 冷启动 / 跨机器运行。

**根因实证** (PR #2058): `tests/test_lifecycle.py` 曾用绝对时间断言
`manager._last_used[...] > 100.0`。`_last_used` 由 `time.monotonic()` 设置,
CI 冷启动 runner 的 monotonic 时钟 <100s (实测 83.75/86.51) → 必然 flaky fail。

**规则**:
```markdown
## 测试时序铁律
- 禁用绝对时间断言 (`> 100.0`、`>= now-100`、`>= time.time()-X`)
- 必须用相对断言: `before = f()` → `assert f() > before`
- 允许的绝对参考: `time.monotonic() - 100.0` (相对当前, 非硬编码绝对阈值)
- 触发: CI 冷启动 / 跨机器 / 时序敏感测试
```

**验收**: 测试可在冷启动 runner + 长跑机器上均稳定通过。

## PATH-ANCHOR: 脚本路径代码位置锚定铁律

**触发**: 任何脚本访问 workspace 外路径 / 解析配置文件 / 定位资源。

**根因实证** (PR #2058): `mof-enforce.py` 曾硬编码 `HOME/Workspace`,
且 `main()` 直接 `BOUNDARY_FILE.exists()` 绕过 fallback → cascading 独立 temp HOME
下 exit 2 "边界规则不存在"。

**规则**:
```markdown
## 脚本路径铁律
- 路径解析必须以代码位置为锚: `Path(__file__).resolve().parents[N]`
- 禁止硬编码 `HOME/Workspace`、绝对用户路径等环境假设
- 必须能在隔离环境 (cascading / temp HOME / CI sandbox) 独立运行
- 提供 fallback 链: 硬编码路径 → script-relative → 项目相对
- 触发: 任何脚本访问 workspace 外路径 / 解析配置文件 / 定位资源
```

**验收**: 脚本在 temp HOME / 独立 clone / CI sandbox 均可运行。

## CAP-OWN: 能力删除防腐铁律 (S1)

**触发**: 删除/重命名任何注册在 mof-capabilities.yaml 或 capability-registry 的能力。

**规则**:
```markdown
## 能力删除铁律
- 删除能力前, 注册表 (mof-capabilities.yaml) 必须同步移除或标注 deprecated
- 删除必须证明消费方引用归零 (bos:// 注册、CLI 命令、agora tools)
- `check-capability-ownership.py` 的 IMPL-EXISTS error → 禁止提交
- 类比: submodule-guard 保护 gitlink, CAP-OWN 保护能力
```

**验收**: `python3 bin/gac/check-capability-ownership.py` exit 0。

## PROJ-FORCE: SSOT-投影同步铁律 (S1)

**触发**: 修改任何 SSOT 源 (agent-workflows/profiles、mof-capabilities.yaml 等)。

**规则**:
```markdown
## SSOT-投影同步铁律
- 改 SSOT 源后, 必须同步对应投影 (projection-sync / capability-registry 生成)
- post-commit hook 已自动触发 (bin/ssot/post-commit-sync-check.py)
- 若投影漂移 (CI check-docs-drift fail), 说明 SSOT 改后没提交派生文档
- 生成物残缺 (totals=0) → 自动 revert, 勿提交 (CI 完整环境会重新生成)
```

**验收**: 改 SSOT 后 commit, 派生文档随 commit 同步 (无 check-docs-drift fail)。
