---
type: ephemeral
created: 2026-09-03
---

# 2026-08-15 bin 工具治理收敛复盘

## 一、背景与目标
- 目标：对 `bin/` 脚本做可持续盘点与依赖分析能力，补齐 Makefile 运行入口，支持验证闭环。
- 上下文：对 PR #1533 进行合并后，持续补足治理基础工具与迭代机制。

## 二、已完成实施
1. PR #1533 已合并（`1533`，commit: `cb3f8e798e2176574f3d115fff64225c57a736be`）。
2. 新增 `bin/tool-registry-audit.py`：
   - 输出 bin 脚本统计（总量、类型、缺失 shebang、非 snake_case、重复名称）。
   - 抽取脚本间调用边（`--snapshot` JSON）。
   - 计算出度/入度 TopN 并输出收敛候选。
   - 支持 `--strict`（当前会报重复/循环作为 fail）。
3. Makefile 适配：新增/声明目标
   - `bin-tool-registry-audit`
   - `bin-tool-registry-audit-emit`
   - `bin-tool-registry-audit-strict`
   - `bin-tool-registry-convergence`
4. `make help` 增加上述目标说明。

## 三、依赖分析结论（初版）
- 扫描范围：`bin/` 下可执行文件 + `.py/.sh/.bash/.zsh`（共 510 个文件）。
- 依赖图性质：存在多重重复命名映射、循环引用。
- 关键重复命名（示例）：
  - `submodule_reachability_gate`: `bin/submodule-reachability-gate.py` 与 `bin/ssot/submodule-reachability-gate.py`
  - `sync_submodules_push`: `bin/sync-submodules-push.sh` 与 `bin/ssot/sync-submodules-push.sh`
  - `git_health_hook`: `bin/git-health-hook.py` 与 `bin/ssot/git-health-hook.py`
- 主要循环示例（抽取自第一次快照）：
  - `bin/compass_radar.py -> bin/compass_radar.py`
  - `bin/delegation-preflight.py -> bin/delegation-preflight.py`
  - `bin/submodule-gitlink-check.py -> bin/submodule-gitlink-check.py`

## 四、验证与证据
- GitHub PR Checks（`pr #1533`）：15 项通过，1 项跳过（Documents domain projects）。
- 本地执行：
  - `make bin-tool-registry-audit`：成功。
  - `make bin-tool-registry-audit-emit`：成功，产物 `artifacts/bin-tool-registry-audit.json`。
  - `make bin-tool-registry-convergence`：成功。
  - `make bin-tool-registry-audit-strict`：当前失败（基线残留：9 个重复名、20 个循环）。

## 五、下一轮迭代计划（建议）
1. 将 `--strict` 改为可配置阈值/白名单：先允许已知归档脚本不计入强检。
2. 对重复脚本命名执行固化标准：统一归位到单路径（优先 `.py` 命名空间）并在 Makefile 增加迁移目标。
3. 对自循环脚本引入“封面脚本/入口脚本”标记，避免误判：
   - 使用注释约定 `# entrypoint: true`。
4. 把 `non-snake` 规则分为“建议项”和“阻断项”，降低短期阻塞。
