---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# Submodule Inclusion Policy

> 版本: 1.0
> 状态: Active
> 适用范围: OMO Workspace 根目录下的所有顶级项目目录

## 1. 核心原则

在 eCOS 架构下，工作区根目录（Workspace Root）是聚合了多个微内核、横切框架和治理体系的超级母舰。为了防止物理边界的坍塌与配置状态的幽灵漂移，对于 `projects/` 及横向平面的目录，必须遵循以下绝对统一的纳入标准。

## 2. 子模块 (Git Submodule) 的判定标准

任何满足以下**全部条件**的目录，**必须**通过 `git submodule add` 纳入管理，严禁直接将其代码 commit 到 Root 仓库：

1. **拥有独立生命周期**：项目的代码迭代、发版频率与 Root 工作区或其他模块不强耦合。
2. **逻辑可独立运行或分发**：是一个完整的服务、SDK、Library 或者独立的 Web App（如 `cockpit`, `agora`, `hermes-console`）。
3. **拥有独立的依赖清单**：包含独立的 `pyproject.toml`, `package.json` 或 `go.mod`。

## 3. 直接管理的目录（非子模块）

满足以下条件的目录，**禁止**设置为 Git 子模块，必须直接在 Root 仓库进行跟踪与版本控制：

1. **全局状态与配置 (State & Manifests)**：
   * 包含声明式配置、路由表、命名空间白名单的目录（如 `spaces/`）。
   * 此类目录是全局 SSOT (Single Source of Truth) 的延伸，一旦分离成子模块极易导致配置环境的“时间戳碎裂”。
2. **元治理面与证据链 (Governance)**：
   * `.omo/` 治理目录及其子目录（含 `tasks`, `state`, `debt`）。
3. **全局基建与脚手架**：
   * 统筹全局构建的脚本或宏环境配置（如根目录的 `Makefile`, `.github/`, `.hermes/`）。

## 4. 严格禁止的结构反模式 (Anti-Patterns)

1. **禁止在项目中创建指向外部或同级目录的软链接 (Symlinks)** 以绕过模块边界。如果是依赖，请通过本地 Path 依赖在构建工具 (如 `uv`) 中声明。
2. **禁止 `.gitignore` 的历史遗留幽灵**：一个目录如果不应该被纳入子模块，它必须被 Root Git 显式追踪。不应当通过在 `.gitignore` 中彻底 ignore 整个有效业务目录（如曾经的 `spaces/`）来规避治理。
3. **禁止“游离态代码库”**：包含 `.git` 的子文件夹必须存在于根目录的 `.gitmodules` 中。如果没有，要么将其删除其 `.git` 文件夹纳入 Root 控制，要么正式注册为 submodule。

## 5. 新项目/移除项目 Checklist

**新增项目作为子模块：**
- [ ] 确保目标目录存在独立的 `.git`。
- [ ] 在 Root 目录执行 `git submodule add <url> projects/<name>`。
- [ ] 更新 `AGENTS.md` (或等效的 Workspace Guide) 中的 Project Overview 列表。
- [ ] (可选) 生成新模块的 `ARCHITECTURE.md`。

**将子模块降级或移除：**
- [ ] `git submodule deinit -f <path>`
- [ ] `git rm -f <path>`
- [ ] 从 `.git/modules/<path>` 中彻底删除相关的 Git meta 信息。
- [ ] (如果是降级为纯目录) 重新添加代码，并提交至 Root 仓库。
