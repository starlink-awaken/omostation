---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: 子模块指针自动化 PR 运维与标准化指南
type: doc
---
# 子模块指针自动化 PR 运维与标准化指南

本指南记录了 `omostation` 全量子模块自动化更新机制的架构设计与配置说明。

---

## 1. 架构概览 (Architecture)

```
[各子模块 (projects/*)] ──(Release / workflow_dispatch)──>
    └── .github/workflows/bump-main-pr.yml (薄调用)
            │
            ▼ (uses)
[主仓 omostation]
    └── .github/workflows/reusable-submodule-bump-pr.yml (Reusable Workflow)
            │
            ├── 1. 检出主仓 (使用 OMOSTATION_BOT_TOKEN)
            ├── 2. 执行 bump-fast (git cacheinfo 秒级更新)
            ├── 3. 同步 docs/project-registry.yaml 版本
            ├── 4. 自动创建 branch 并开启 PR (带 submodule-bump 标签)
            └── 5. 触发主仓 CI 门禁体系 (phase-gate / gac-gate 等)
```

---

## 2. 权限凭证配置 (Secret Configuration)

每个子仓库向主仓开启 PR 时，需要具备主仓写权限的 Token。

### 推荐方式：Organization 级别 Secret (一劳永逸)
1. 访问 GitHub Organization 设置：`https://github.com/organizations/starlink-awaken/settings/secrets/actions`
2. 新建 Organization Secret：
   - **Name**: `OMOSTATION_BOT_TOKEN`
   - **Value**: 具备 `starlink-awaken/omostation` 仓库 `Contents: write` 和 `Pull requests: write` 权限的 Fine-grained PAT。
   - **Repository access**: `Selected repositories`（勾选全部子模块仓库）或 `All repositories`。

### 备选方式：单仓库 Secret 配置
如果未配置 Org Secret，也可单独进入子仓库设置：
- **Settings** > **Secrets and variables** > **Actions** > **New repository secret**
- **Name**: `OMOSTATION_BOT_TOKEN`

---

## 3. 子仓库薄工作流配置规范

各子仓库只需在 `.github/workflows/bump-main-pr.yml` 中保留以下标准内容：

```yaml
name: Submodule Bump Main PR

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      target_sha:
        description: 'Target commit SHA (leave empty for latest main)'
        required: false
        default: ''

jobs:
  trigger-bump:
    uses: starlink-awaken/omostation/.github/workflows/reusable-submodule-bump-pr.yml@main
    with:
      submodule_path: <SUBMODULE_PATH> # 例如 projects/omlxc 或 projects/cockpit
      target_sha: ${{ github.event.inputs.target_sha }}
      release_tag: ${{ github.event.release.tag_name }}
    secrets:
      bot_token: ${{ secrets.OMOSTATION_BOT_TOKEN }}
```

---

## 4. 维护与批量同步工具

如需对全量子模块的工作流进行批量更新或增加新子模块，可在主仓执行：
```bash
bash bin/_archive/2026-08-t6-05/distribute-submodule-workflows.sh
```
