---
lifecycle: contract
owner: runtime-team
last_updated: 2026-08-17
review-state: generated-report
title: 主仓目录治理表面扫描
type: doc
---

# 主仓目录治理表面扫描

- 生成时间: 2026-08-17T03:19:47.885982+00:00
- 目录总数: 24
- 必做治理项: 1
- 建议治理项: 3
- 目录卫生违规: 0

## 一、目录级体检
| 目录 | 文件数 | 子目录数 | 大小(KB) | AGENTS.md | README | tracked | ignored | policy | disposition | 优先级 |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |
| projects | 8595 | 1087 | 113339.26 | yes | yes | yes | no | no | tracked | ok |
| .omo | 3440 | 204 | 14177.80 | yes | yes | yes | no | no | tracked | ok |
| scripts | 3040 | 282 | 15945.64 | yes | yes | yes | no | no | tracked | ok |
| bin | 537 | 21 | 4155.51 | yes | yes | yes | no | no | tracked | ok |
| docs | 292 | 22 | 2732.86 | yes | yes | yes | no | no | tracked | ok |
| tests | 177 | 15 | 1120.85 | yes | yes | yes | no | no | tracked | ok |
| .github | 53 | 2 | 117.53 | yes | yes | yes | no | no | tracked | ok |
| runtime | 36 | 6 | 45.43 | yes | yes | yes | no | yes | tracked | ok |
| .agents | 32 | 26 | 144.03 | yes | yes | yes | no | no | tracked | ok |
| spaces | 28 | 2 | 26.65 | yes | yes | yes | no | yes | tracked | ok |
| .venv | 20 | 5 | 50981.38 | no | no | no | yes | yes | allowed-ignored | must |
| data | 12 | 6 | 10.15 | yes | yes | yes | no | yes | tracked | ok |
| tools | 11 | 3 | 13.83 | yes | yes | yes | no | no | tracked | ok |
| artifacts | 7 | 0 | 414.06 | yes | yes | yes | no | yes | tracked | ok |
| protocols | 7 | 0 | 33.54 | yes | yes | yes | no | no | tracked | ok |
| Plans | 6 | 0 | 32.74 | yes | yes | yes | no | no | tracked | ok |
| .githooks | 6 | 0 | 23.80 | yes | yes | yes | no | no | tracked | ok |
| .serena | 5 | 3 | 243.35 | no | no | no | yes | yes | allowed-ignored | should |
| .pytest_cache | 5 | 2 | 0.89 | no | yes | no | yes | yes | allowed-ignored | should |
| .kilo | 4 | 1 | 4.64 | yes | yes | yes | no | no | tracked | ok |
| locks | 4 | 0 | 0.71 | yes | yes | yes | no | yes | tracked | ok |
| lib | 3 | 0 | 6.47 | yes | yes | yes | no | no | tracked | ok |
| evidence | 3 | 0 | 3.96 | yes | yes | yes | no | no | tracked | ok |
| .mimocode | 2 | 1 | 5.90 | no | no | yes | no | no | tracked | should |

## 二、治理优先级

### 1) 必做（高优先）
- `.venv`: 文件20，问题 AGENTS.md/README。

### 2) 建议（中优先）
- `.serena`: 文件5，缺失 AGENTS.md/README。
- `.pytest_cache`: 文件5，缺失 AGENTS.md。
- `.mimocode`: 文件2，缺失 AGENTS.md/README。
