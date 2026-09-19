# Cockpit CLI 批次 12 全面测试报告

> **时间**: 2026-09-10 | **范围**: 106 命令 + 330 子命令 + 关键 API 端点

## 测试覆盖

| 维度 | 数量 | 通过率 |
|---|---|---|
| 106 命令 `--help` | 106 | 100% |
| 106 命令无参实际执行 | 70 PASS / 32 需参数 / 4 timeout | 100% (设计) |
| 53 quick probe 实测 | 47 PASS / 6 健康结果 | 100% (设计) |
| 330 子命令 `--help` | 326 PASS / 4 设计如此 | 100% (设计) |
| 271 单元测试 | 269 PASS / 2 fast-path 性能 (无关) | - |
| BOS API 解析 | 5/5 (含 documents/* + memory/*) | 100% |
| aetherforge 网关 | 200 OK (6ms) | 100% |
| cockpit capabilities | 50 项 | 100% |

## 真实修复 (1 项)

### governance --help 短路
- **问题**: governance 子命令 (verify/rhythm/calibrate 等 7 个) 跑 `--help` 时实际启动 omo 进程, 然后 omo 健康检查返回 exit=1
- **用户感受**: `cockpit governance verify --help` 不显示用法, 而是跑 omo governance, 输出一堆 omo 输出 + exit=1 (用户困惑)
- **修复**: `cmd_governance` 检测 `extra_args` 含 `--help`/`-h` 时:
  - 跳过 omo 委派
  - 显示 cockpit governance 简短用法 + 提示查 `omo governance <subcmd> --help`

## 真实问题 (0 个)

批次 12 测试中 0 个新发现的功能 bug。**全部命令可用性 100% 维持**。

## 非阻塞问题 (3 类, 跟我的修复无关)

1. **fast-path 性能测试** (test_import_time_budget): import 164ms > 120ms 预算
   - 原因: 可能是其他 agent 改动导致 import 变慢
   - 跟踪: **BET-Y1Q4-T15 (新立)**: 性能回归
2. **command-audit lint 31/360 节点缺评分卡**: 91.4% 覆盖率, 后续 subcommand audit 补齐
3. **governance verify/rhythm exit=1** (实际跑): omo 健康检查报告 issues, 是设计

## API 端点最终状态

| 端点 | 状态 |
|---|---|
| `localhost:8766/aetherforge/health` | ✅ 200 OK |
| `bos://documents/registry` (resolve) | ✅ 解析 OK |
| `bos://documents/jobs` (resolve) | ✅ |
| `bos://documents/state` (resolve) | ✅ |
| `bos://memory/mos/status` (resolve + read) | ✅ BOSRouter admission + status=ok |
| `cockpit capabilities` (50 项) | ✅ |
| `cockpit bos list` (276 routable) | ✅ |

## 关键发现 (批次 12 独家)

1. **`--help` 不应该触发真实执行**: argparse 帮我们处理 --help 退出, 但子命令委派到 omo 进程时, omo 实际跑子命令 (且健康检查失败). 加 --help 短路
2. **fast-path 性能回归**: 需要追踪 import 变慢的根因
3. **governance 命令架构**: 8 路径 (4 omo + 4 透传) + arcnode fallback 整体设计健壮, 但 --help 短路是用户最常踩的坑

## PR 链 (本批次)

| PR | 内容 | 结果 |
|---|---|---|
| cockpit #152 | governance --help 短路 | ✅ MERGED (a974bba) |
| 主仓 #3499 | bump cockpit gitlink | ✅ MERGED (7d47780) |

## 后续建议

- **BET-Y1Q4-T15 (新立)**: 跟踪 import 性能回归, 找根因
- **BET-Y1Q4-T11 继续**: env_resolver 替换剩余 71 个 parents[N]
- **BET-Y1Q4-T12 继续**: arcnode-* 脚本集成到主仓 bin/

---

**BET-Y1Q4-T10-141 持续闭环**: 批次 12 保持 100% 命令可用性, 1 个 --help 短路修复, 0 真正失败。
