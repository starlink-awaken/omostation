# Retro — BET-Y2Q1-T7-06 卫健公文全周期拟办、批阅与会议督办全闭环场景包

- bet: BET-Y2Q1-T7-06
- date: 2026-09-15
- track: T7-SCENE
- appetite: 3 days（实际 1 会话内交付）
- status: delivered-PR（待 owner 人审合入，human_gate: true）

## 交付物

1. `docs/superpowers/specs/2026-09-15-y2q1-t7-06-health-gov-doc-cycle-design.md`（spec v1.0.0, accepted）
   - digest `sha256:6c4fcfef...074f3459b5b` 已回填 ledger `accepted_specifications`（恰 1 条）
2. `projects/domain-cartridges/health-gov/domain/health_gov/{doc_pipeline,test_doc_pipeline}.py`
   - 登记→拟办→批阅（署名）→办结状态机 + 红头导出 + 会议督办
3. `docs/scene-cards/health-gov-doc-cycle.yaml`（lifecycle: assisted, synthetic-seed 校准）
4. ledger：verify cmd 补 `PYTHONPATH` 前缀（T10-05 同先例，使根目录可运行）

## 验证

- `PYTHONPATH=projects/domain-cartridges/health-gov uv run python -m domain.health_gov.test_doc_pipeline` → ALL PASS
  - 3 e2e（通知/函/纪要督办，真实 PDF 产物 `%PDF-` 头 + >2KB）
  - 6 类负例熔断全拦截（涉密/文号/无署名/退回无意见/缺要素/非法跃迁）
  - 36 例合成校准 F1=1.000 ≥ 0.6 门
- `make gac-local-gate` → FAIL，唯一红项 `CR-RESIDENT-BOS-01`（resident BOS 路由缺 8）
  - **实证与本 bet 无关**：`git stash -u` 后在纯净 HEAD 复跑同 check，依然 FAIL；
    `git status` 本分支改动仅 5 个 T7-06 路径，被检文件（bos-services.yaml/allowlist）未动
  - 其余 gate 检查项（含 sfop-slots/execution-chain/pitfall-gat006）全 PASS
  - 结论：main 基线预存 breakage，修复属 resident 域 scope，不在本 bet 内顺手修（防回退/扩面）

## 经验教训

1. **verify cmd 必须在根目录实测**：cartridge 自测在包目录内 pass 不等于 ledger verify 可跑；
   根目录 `python -m domain.*` 需要 `PYTHONPATH` 前缀（T10-05 早有先例，本次复用而非发明新约定）。
2. **PDF 依赖诚实化**：root pyproject 故意零依赖，reportlab 装进 workspace `.venv`
   （`uv pip install`，两次 `uv run` 复测不丢失）；管线缺依赖时显式抛错，
   与“缺失标 unmeasured、不伪造”同构——熔断语义跨域一致。
3. **assisted 口径诚实标注**：30-sample 门槛用 synthetic-seed 满足（沿用 T7-03 先例），
   卡内 `notes` + spec §4 双处声明真实样本待 follow-up，不虚报。
4. **全字日期双解析**：公文成文日期须全字（GB/T），而内部时限计算需 ISO；
   `_parse_day` 双向兼容，避免登记字段与计算字段打架。
5. **worktree claim 超时**：`gac-worktree.sh claim` 在子模块全量 init 处超时，
   但分支已建（`agent/governance-agent/t7-06-health` @ 最新 main）；改走后台
   `submodule update --init projects/omo projects/ecos` 最小集，不阻塞交付编码。
6. **claim 超时不等于 claim 失败**：先 `git worktree list` 确认分支状态再重试，
   避免重复 claim 产生悬空 worktree。
