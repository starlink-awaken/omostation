.PHONY: help kairon-test kairon-build

help:
	@echo "Workspace 根 Makefile — 委派到 projects/"
	@echo ""
	@echo "make kairon-test    运行 kairon 全部测试"
	@echo "make kairon-lint    ruff 检查所有包"
	@echo "make help           显示本消息"

kairon-test:
	cd projects/kairon && make test

kairon-lint:
	cd projects/kairon && ruff check packages/

kairon-build:
	cd projects/kairon && uv sync
