# BOS 契约走查报告 — 第九轮 (2026-08/09 走查序列)

> 前置: 第八轮收尾后进入"收尾巩固"。双门禁终验时 bos-tracking-gate 实跑 FAIL（62 处漂移），
> 顺藤摸出本轮全部发现。日期: 2026-09-24。

## TL;DR

门禁曾长期显示 "59 checks ALL GREEN"，实为**残缺绿**：sgf-policy 动态策略整体覆盖
DEFAULT_POLICY，导致 21 个 checks（含 bos-tracking-gate 等硬核检查）从未运行；而
bos-tracking-gate 若真跑会报 62 处 BOS 追踪漂移。本轮修复后：**68 checks ALL GREEN
（真实绿）**，BOS 追踪 62→0 漂移，3 条服务经实测复活，7 条零引用占位清理。

## 一、门禁旁路链（root cause 链）

1. **旁路机制**: `load_sgf_policy() or DEFAULT_POLICY` 为整体覆盖语义——sgf-policy.yaml
   存在时，DEFAULT_POLICY 定义但未收录进 sgf-policy 的 checks 全部静默失联。
   比对: DEFAULT_POLICY 72 项 vs sgf-policy 63 项 → 21 项失联。
2. **若它曾运行**: bos-tracking-gate 报 62 处漂移（agent-cell 23 + auto-registered 39）。
3. **配套盲区**: gate-parity 只校验"sgf-policy 引用 → ci-surfaces 登记"，不校验工具文件
   真实存在——补录时 7 个幽灵工具（并行 agent 未提交的 untracked 脚本）畅通无阻。

## 二、BOS 注册表三层真相

1. **SSOT 层**: bos-services.yaml 62 条缺 module_path（internal 33 + stdio/inline/mcp_proxy 29）
2. **追踪层**: bos-unimplemented.yaml 与 SSOT 判定字段不一致——gate 认 description 前缀
   `[UNIMPLEMENTED]`，大量条目只有 `status: unimplemented` 字段 → 双向校验全错位
3. **运行时层**: `load_from_yaml` 跳过 status:unimplemented 与缺必填字段条目 →
   33 条 internal 在运行时是**死数据**（resolve 报 unknown_bos_uri）

**漂移源头**: `.omo/_truth/registry/bos-pending-registrations.yaml` 曾把 41 个
"代码引用但未注册" URI 批量登记进 SSOT，只写了 URI+描述，未锚定实现（module_path）。

## 三、处置结果（全部逐条实测，declare≠execute 纪律）

| 处置 | 数量 | 明细 |
|---|---|---|
| ♻️ 复活 | 3 | im-session/triage + scene/anchor（resolver 全链路 ok）；agent-cell/pool/status（command 死语法 `--status --json`→`--action status`，实测真实 JSON） |
| 🧹 清理 | 7 | observatory×6 + memory/kairon/minerva（代码零真实引用，双文件同步删） |
| 🏷️ 归位 | 44 | unimplemented 意图条目 desc 补 `[UNIMPLEMENTED]` 前缀 → gate 判定对齐 |
| 📥 补登记 | 3 | analysis/iris×3（SSOT 标记但追踪缺失） |
| ⏸️ 保持 | ~26 | 真实引用但实现未落地（capability/governance 系），双文件追踪闭环在位 |

复活判定标准（全部实测）：
- im-session/triage → `bos_im_session_triage` 实测输出 cards/passive/dropped 分诊
- scene/anchor → `scene_anchor` kernel 可用真实打分 / 不可用诚实 `kernel_unavailable`
- ocr **降级不复活**: 实现存在但返回 `list[TextBox]` 与 internal dict 契约不兼容（复活需先补 dict 包装层 — owner 决策）
- execution-workers/status **降级**: 仅 MCP resources 展示条目 + 硬编码 fallback（假数据）

## 四、sgf-policy 补录与幽灵污染

- 21 失联项中 **14 项试跑验证绿后补录**（ecos PR #78 合并，74c3c77e2）
- **7 项为幽灵**: 引用的脚本（check-doc-governance.py 等）是并行 agent 在共享工作区
  创建的 untracked 文件，试跑后即被清理，git 全历史无记录。sgf-policy/ci-surfaces
  的引用已同步剔除。
- ci-surfaces.yaml 净增 9 个真实登记（16 登记 − 7 幽灵剔除）

## 五、登记项（未修，需 owner 决策/后续轮次）

1. **gate-parity 盲区**: check-ci-surfaces.py 增加工具文件存在性校验（防幽灵工具畅通）
2. **agent-cell submit/scale**: command 死语法（真实 CLI 无此 action），语义映射需 owner 决策
3. **bos://perception/agora/ocr 复活**: 需先补 dict 包装层
4. **kairon minerva 预存失败**: `test_minerva_main_help` subprocess 跑 kairon venv
   `No module named minerva`——kairon 项目模块缺失或测试过时（stash 验证与本轮无关）
5. **26 条 B 类保持 unimplemented**: 真实引用、实现未落地，待逐条锚定实现
6. **bos://memory/brain-events/card_updated**: 文档引用 legacy 名，建议 resolver
   normalize_bos_uri 增加 legacy→canonical 映射

## 六、门禁数字变化

| 指标 | 修复前 | 修复后 |
|---|---|---|
| gac-local-gate | 59 checks（21 失联） | **68 checks ALL GREEN** |
| bos-tracking-gate | FAIL（62 漂移） | PASS（53 unimplemented / 352 active） |
| SSOT internal 缺 module_path | 33（死数据） | 29（结构化 unimplemented 追踪） |
| ci-surfaces | 149 surfaces | 158 surfaces（+9 真实登记） |
| ci-local-fast | ✅ | ✅ |

## 七、PR 链

- agora: PR #96（bfd450f）— BOS 注册表契约修复
- ecos: PR #78（74c3c77e2）— sgf-policy 14 项登记
- 主仓: PR #4279 — gitlink bump + ci-surfaces + 生成物 + 本报告

---

# 第十轮：stdio 面全面覆盖 (2026-09-24 同日)

## TL;DR

第九轮主攻 internal transport 33 条 + 门禁旁路。第十轮按用户"全面覆盖优化"指令，
系统性排查 **29 条 stdio/inline/mcp_proxy 占位条目的 command 真实可执行性**——
cell-pool/status 的死语法问题（第九轮个案）被证实是**系统性模式**：22 条 stdio
占位中 **17 条 command 无法原样执行**（8 死语法 + 9 缺 PYTHONPATH 必炸）。

## 处置矩阵（每条 3 轮真实执行验证）

| 处置 | 数量 | 明细 |
|---|---|---|
| ♻️ 复活 | 19 | agent-cell 18 条 stdio + ocr（锚定已有 bos_ocr_extract，第九轮漏判纠正） |
| ⏸️ 保持 | 4 | pool/submit、scale、auto-scale、metrics（CLI 无对应 action，语义映射 owner 决策） |
| 🗺️ legacy 路由 | 1 | brain-events: normalize_bos_uri 映射后删除占位条目 — legacy 名真实可路由 |
| 🧪 测试修复 | 1 | minerva: uv workspace member 需 --package（历史预存失败转绿） |

## 三轮实测暴露的层次问题

1. **首轮（参数语法）**: 8 条 --json 死语法、9 条 ModuleNotFoundError
2. **二轮（执行形态）**: uv --directory 切 cwd → 脚本路径必须相对 omo 根；pool/status
   第九轮复活只验了参数合法性没验 resolver 运行时形态 → 本轮补强
3. **三轮（yaml 语义）**: JSON payload 参数无引号被 yaml 解析为 flow mapping →
   str(dict) 的单引号 JSON 让脚本 json.loads 必炸 → 单引号包裹修正

## 运行时环境事实（新增沉淀）

- agora stdio adapter Popen 只设 cwd=workspace，**不注入 PYTHONPATH** →
  裸 python3 + import omo 的 command 必炸，必须 uv --directory 形式
- uv workspace 根 venv 不自动含 members → 跨包 python -m 需 --package
- JSON payload 参数在 yaml 列表中必须引号包裹，否则被解析为 flow mapping

## 数字变化（累计两轮）

| 指标 | 走查前 | 第九轮末 | 第十轮末 |
|---|---|---|---|
| BOS unimplemented/active | 62 漂移 | 53/352 | **33/351** |
| 可路由 BOS 服务 | 277 | ~290 | **351** (含 19+3 复活) |
| minerva 预存失败 | FAIL | FAIL | **PASS** |

## 第十轮登记项

1. 4 条 pool 系保持 unimplemented — CLI 只有 dispatch/status/complete/recover，
   submit/scale/auto-scale/metrics 语义映射需 owner 决策
2. omo published.jsonl 4 条测试残留清理在工作区（3 条本轮实测产生 + 1 条历史同类），
   因并行 agent 占用 omo 仓暂不提交 — owner 择机入库
3. 26 条 B 类（capability/governance 系）维持 unimplemented 追踪
4. gate-parity 盲区已修（check-ci-surfaces.py 增加工具文件存在性校验，见主仓 PR）
