# lib — 共享库

共享库与小规模工具文件存放处。

- 变更应保持接口稳定。
- 更新时补齐引用方影响清单。

## Capability federation audit

`capability_federation_audit.py` 是只读联合审计库，公共入口由
`bin/capability-sync.py federation-audit` 提供。它不写 registry、运行态或
观察记录，也不执行 registry 中的命令字段。直接下游：Makefile 入口、
`tests/test_capability_federation_audit.py` 与 Capability Federation 架构合同。
