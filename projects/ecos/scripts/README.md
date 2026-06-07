# eCOS 运营脚本

> 源目录: ~/Workspace/projects/ecos/scripts/
> 兼容层: ~/.ecos/scripts/ → symlink → 此处

## 分类

| 目录 | 说明 |
|------|------|
| `./` | 核心运营脚本 (daemon/digest/sla/healer) |
| `../src/ecos/services/` | 服务模块 (domain_manager/bos_mcp) |
| `../src/ecos/ssot/tools/` | L0 治理工具 (mof-bos/mof-gate) |

## 维护

- 所有脚本通过 git 版本管理
- 修改后: `git add scripts/ && git commit`
- 新脚本加入时同步更新此 README
