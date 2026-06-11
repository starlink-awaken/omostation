.PHONY: help kairon-test kairon-test-fast kairon-test-diff kairon-test-e2e kairon-build kairon-lint governance-check governance-sync governance-validate governance-index-check governance-verify

help:
	@echo "Workspace 根 Makefile — 委派到 projects/"
	@echo ""
	@echo "make kairon-test       运行 kairon 全部测试"
	@echo "make kairon-test-fast  运行 kairon 单元测试 (跳过集成/基准)"
	@echo "make kairon-test-diff  运行 kairon 差异测试 (仅修改的包)"
	@echo "make kairon-test-e2e   运行 kairon E2E 测试 (Postgres+gbrian+kairon 容器化)"
	@echo "make kairon-lint       ruff 检查所有包"
	@echo "make kairon-build      安装 kairon 依赖 (uv sync)"
	@echo "make governance-verify  运行 canonical .omo 验证链 (sync → validate → test)"
	@echo "make governance-check   全量治理检查 (canonical verify → index)"
	@echo "make governance-sync    同步 .omo/state/system.yaml"
	@echo "make governance-validate 验证任务 Schema"
	@echo "make governance-index-check 检查 INDEX.md 覆盖率"
	@echo "make help              显示本消息"

kairon-test:
	cd projects/kairon && make test

kairon-test-fast:
	cd projects/kairon && make test-fast

kairon-test-diff:
	cd projects/kairon && make test-diff

kairon-test-e2e:
	cd projects/kairon && make test-e2e

kairon-lint:
	cd projects/kairon && ruff check packages/

kairon-build:
	cd projects/kairon && uv sync

governance-verify:
	bash bin/verify-omo.sh

governance-check: governance-verify governance-index-check
	@echo "Governance checks complete."

governance-sync:
	python3 scripts/sync_omo_state.py --omo-dir .omo

governance-validate:
	python3 scripts/omo_task_schema.py --all-active

governance-index-check:
	python3 scripts/check-index-coverage.py
