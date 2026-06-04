# OMO 内核整治计划

## Phase 1：基建清理
- [ ] 1.1 cli.py 去掉 sys.path.insert，统一为 from .omo_* 导入
- [ ] 1.2 18个模块去掉 try/except ModuleNotFoundError，直接 from .omo_xxx import
- [ ] 1.3 pyproject.toml 加 dev-dependencies (pytest, pytest-cov, ruff)
- [ ] 1.4 phase16.py 硬编码 EXTERNAL_OMO_ROOT 改为参数/环境变量

## Phase 2：重复代码收敛
- [ ] 2.1 提取 omo_shared_utils.py：_utc_now, _root, _load_yaml, _write, atomic IO 导入 (depends_on: IMPORTED-08ea57, IMPORTED-b7fb35)
- [ ] 2.2 加 tests/conftest.py：全局 fixture（tmpdir, yaml_loader, mock_time）

## Phase 3：测试优化
- [ ] 3.1 拆分 test_omo_automation.py（5,388行→按域拆为3-4个文件） (depends_on: IMPORTED-b461d5)
- [ ] 3.2 全量测试运行 + 回归修复 (depends_on: IMPORTED-7bea82)

## Phase 4：CI 集成 + 战略
- [ ] 4.1 GHA workflow：uv sync --group dev → pytest → ruff check (depends_on: IMPORTED-dffdd8, IMPORTED-4c93ca)
- [ ] 4.2 omo-debt 收敛设计文档（决策树：合并 vs 统一数据模型 vs 保持双轨）
