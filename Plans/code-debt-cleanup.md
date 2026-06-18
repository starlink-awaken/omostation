# CI 代码债清单 + 修复方向

> **2026-06-18** · 配置类 CI 修复完成后的剩余代码债专项入口
> **背景**: 12 CI 绿(5 enforce + 7 项目), 剩红全是子模块代码/依赖/测试债

---

## 现状

### ✅ 已绿 — 12 CI(配置类全修完)

| 类别 | CI |
|------|----|
| 5 enforce | port-registry / state-goals / interfaces / cross-deps / task-schema |
| 7 项目 | hermes-console / observability / family-hub / bus-foundation / omo-debt / model-driven / cockpit |

配置类修复: `CROSS_REPO_TOKEN`(private 子模块认证) + `submodules`/`init` + `pip pyyaml` + `uv sync`。

### ❌ 代码债 — 各子模块活(非 CI 配置层)

| 子模块 | 债 | 根因 | 修复方向 |
|--------|----|----|---------|
| **ecos** | `minerva-deep-research` 工作流测试找不到(15 失败) | catalog 有定义(31 处)但 `mof-workflow.py` 加载逻辑不识别; ecos 本地 `f9e967a` vs 远程 `302ee8da` **分叉** | 查 mof-workflow.py 加载逻辑; 合并 ecos 分叉 + bump 主仓 gitlink |
| **agora** | `No module 'forge'`(test_forge_loader) | agora 依赖 forge 未声明/未装; agora 本地/远程曾分叉(已 merge 一次) | agora pyproject 声明 forge 依赖 or 确认 forge 来源(子目录/extra) |
| **aetherforge** | 测试失败 | agent 改 `packages/gateway/pyproject.toml`(进行中) | 等 agent 完成 + 看测试 |
| **c2g** | 测试失败 | agent 改 adapters/bridge/llm/strategy/test_smoke(8 处, 进行中) | 等 agent 完成 + 看测试 |
| **kairon** | `ontoderive/test_formalize::test_extract_rule_only` 失败 | 代码债 | **不修(用户锁定)** |

---

## 根因: agent 治理混乱(非单纯代码 bug)

1. **agent 多处同时操作同一子模块** — 本地 commit + 远程 push + 工作区改, 互相分叉
   - ecos: 本地 `f9e967a`(=主仓 gitlink) vs 远程 `302ee8da`
   - agora: 本地/远程曾分叉(2026-06-18 手动 merge 修过一次)
2. **工作区大量未 commit** — ecos 66 / agora 62 / c2g 8 / aetherforge 1 改动(agent 进行中)
3. **CI 拉 gitlink 版本 ≠ agent 工作区** → 测试找不到 agent 新加的(minerva/forge)

---

## 治理机制(已落地, 防悬空复发)

- ✅ `bin/sync-submodules-push.sh` — 检测本地领先远程的子模块并 push
- ✅ `.git/hooks/pre-push` — 主仓 push 前自动 sync 子模块(2026-06-18 增强: **sync 结果显示**, 不再静默漏网)
- ✅ `make install-hooks` — 持久化(新 clone 跑一次即装钩子)
- ✅ `CROSS_REPO_TOKEN` — private 子模块 CI 认证(OAuth; fine-grained PAT 坑, 别用)
- ✅ memory: `scripts-submodule-bump-trap` / `ci-private-submodule-token`

---

## 修复优先级(子模块稳定后, 按序)

1. **协调 agent** — 别多处操作同一子模块(分叉根因); 让 agent 把 ecos/agora/c2g 工作区改动 commit + push(CI 拉最新, 部分测试可能自动过)
2. **ecos 分叉合并** — `f9e967a`(本地/gitlink) vs `302ee8da`(远程) → 合并 + 主仓 bump gitlink
3. **ecos minerva** — 查 `mof-workflow.py` 为什么 catalog 有 minerva(31 处)但 `mof workflow show minerva-deep-research` 找不到
4. **agora forge** — pyproject 声明 forge 依赖, 或确认 forge 是子目录/extra
5. **aetherforge / c2g** — agent 完成后看测试失败具体原因
6. **kairon** — 不动(用户锁定)

---

## 老王备注

这些债**不该在 agent 进行中时硬修** — 会和 agent 冲突 + 不知 agent 意图(minerva 是 agent 加的、c2g test_smoke 是 agent 改的)。**替 agent commit 它的活 = 越权**。

等 agent 稳定(commit + push 完 ecos/agora/c2g)后, 按优先级专项清。pre-push 钩子已增强(sync 失败告警可见), 悬空不再静默漏网。
