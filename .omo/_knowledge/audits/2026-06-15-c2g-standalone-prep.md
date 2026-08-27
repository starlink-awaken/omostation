---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# C2G 拆独立 git repo 准备报告 (Round 43 P0 拆分准备)

**日期**：2026-06-15
**状态**：`prepared`（bundle + branch 准备好，等用户在 GitHub 创建 `starlink-awaken/omostation-c2g.git` 后可推）
**关联任务**：c2g 子项目从 omo decouple 后的 standalone open source release

---

## 0. 诚实话语前置 (Reader-Disambiguation)

**事件**：`projects/c2g/` 是根仓子目录（13 个 tracked 文件），AGENTS.md 描述"独立战略需求引擎"，
但**实际不在 .gitmodules 注册**，**GitHub 上没独立 repo**。4 个 commit 历史 (c5a34b2b / 5572ee37 /
d1a357a2 / 47e2a692) 明确目标是 "standalone open source release"——但拆分动作没完成。

**本审计准备**：
- `git subtree split` 提取 4 个 c2g commit 到 `c2g-standalone` branch（本地分支）
- `git bundle` 打包成 119KB bundle file 在 `/tmp/omostation-c2g.bundle`
- 验证 `/tmp/c2g-standalone` clone 成功

**未执行**（等用户）：
- 在 GitHub 创建 `starlink-awaken/omostation-c2g.git`（**超出 Agent 能力**，需用户登录）
- `git push origin main` 推 c2g 独立历史
- 根仓 `git rm -rf projects/c2g` + `git submodule add` 切换到 submodule 模式

---

## 1. c2g 历史（git log --oneline projects/c2g/）

```
4c7e7b38 docs(c2g): optimize for standalone open source release with local adapter and README updates
2fcf1944 refactor(c2g): implement Inversion of Control (IOC) for independent usage, decoupling from omo
b8094534 fix(c2g): fix broken import path for get_omo_dir in strategy.py after decoupling
b7ae6ba0 feat(architecture): decouple C2G engine from omo to standalone projects/c2g, unify cockpit UX under workspace compass
```

c2g 是**从 omo 拆出来的独立战略需求框架**：
- V2P (Vision-to-Pitch)
- C2G (Concept-to-Goal) - 门控下从 Pitch 变 Task
- AGC (Audit & Garbage-Collection) - 战略雷达 + 熵减清理
- Ports & Adapters - 核心不依赖 omo（IOC 解耦）

---

## 2. 拆分准备详情

| 产物 | 路径 | 用途 |
|---|---|---|
| 本地 branch | `c2g-standalone` (HEAD 4c7e7b38) | 临时分支，等推后删 |
| Bundle file | `/tmp/omostation-c2g.bundle` (119,211 bytes) | 推新 repo 的源 |
| Clone 验证 | `/tmp/c2g-standalone/` (4 commits) | 验证 bundle 可恢复 |

---

## 3. 用户完成 c2g 独立化步骤

```bash
# 1. 在 GitHub 创建 starlink-awaken/omostation-c2g.git (空 repo, 不要 init README)

# 2. 在本工作区或新工作区:
cd /tmp/c2g-standalone
git remote set-url origin https://github.com/starlink-awaken/omostation-c2g.git
git push -u origin main
# 验证: https://github.com/starlink-awaken/omostation-c2g 应有 4 个 commit

# 3. 根仓切换 c2g 为 submodule:
cd /Users/xiamingxing/Workspace
git rm -rf projects/c2g
git submodule add https://github.com/starlink-awaken/omostation-c2g.git projects/c2g
# 验证: ls -la projects/c2g/.git 应有文件 (submodule pointer)
git commit -m "refactor(workspace): c2g 拆为独立 git submodule (starlink-awaken/omostation-c2g)"

# 4. 更新 AGENTS.md 描述:
# '独立战略需求引擎 (V2P -> C2G)' → '🟢 Active — 独立战略需求引擎 (V2P -> C2G) · 独立 git repo + .gitmodules'

# 5. 清理临时:
git branch -D c2g-standalone
rm /tmp/omostation-c2g.bundle
rm -rf /tmp/c2g-standalone

# 6. 推送:
git push origin main
```

---

## 4. 风险

- **c2g 后续 commits**：c2g 历史已"冻结"在 4c7e7b38。如果根仓 `projects/c2g/` 有新 commit (5cf9f1e
  之后的 OMO 钩子改动)，**这些新 commit 不会自动同步到独立 c2g repo**。需要在 `git rm -rf projects/c2g`
  之前 merge 那些新 commit。
- **OMO 钩子持续改 c2g**：git status 看到 6 个 M (pyproject + uv.lock + adapters/bridge/cli/strategy) +
  1 个 ?? (mcp_server.py)。这些是 OMO auto-loop 产物，**拆分时需要先 commit 进根仓 projects/c2g 再 subtree split**。
- **submodule vs 子目录**：拆分后 omo 工作流（依赖 `projects/c2g/` import 路径）会变成跨 repo
  import，**可能 break**。

---

## 5. 推荐路径

按"修复剩余"用户原意，**最稳方案**：
1. **不立即拆**：c2g 当前作为根仓子目录工作正常（13 个 tracked 文件 + OMO 钩子持续改）
2. **更新 AGENTS.md 描述**：把"独立"改"内部子项目"以反映实际状态
3. **等有具体 standalone release 计划时**再走上面 §3 步骤

但 c2g README 第 22 行 `pip install c2g` 表明它**设计为可独立发布**——所以 c2g 拆独立是**真需求**，不是可选优化。
