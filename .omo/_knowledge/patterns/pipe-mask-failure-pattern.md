---
lifecycle: pattern
owner: governance-team
last_updated: 2026-07-28
---
# Pattern: 管道/异常掩盖失败（与"为变绿改断言"同族）

> 与 p73/p74 同级避坑基因; 新进 Agent 通读, 严禁二次栽倒.

## 症状
命令管道 / 异常处理吃掉真实失败 exit code, 让失败看起来像成功 → 循环误判 / 静默漏检.

## 本轮案例 (P84 W2.1 push 循环)
```
# bug: tail 的 exit code (0) 覆盖 git push 的失败
for i in 1 2 3; do
  git push ... 2>&1 | tail -3        # tail exit 0, 非 git push
  rc=${PIPESTATUS[0]}                 # zsh 语法错! zsh 是 $pipestatus[1]
  if [ $rc -eq 0 ]; then ...; fi      # rc 空, [ -eq ] 报错, 循环失灵
done
```
**结果**: git push 实际失败 (reachability gate FAIL), 但循环误判 PUSH_OK 总 break.

## 通用陷阱
1. **管道吃 exit**: `cmd_a | cmd_b` 的 `$?` 是 cmd_b 的 exit, cmd_a 失败被掩盖.
2. **except 吞异常**: `except Exception: pass` (check-work-landed 同族问题, K3 待修), 失败静默.
3. **shell 语法错位**: bash `${PIPESTATUS[0]}` vs zsh `$pipestatus[1]` (0-indexed vs 1-indexed), 跨 shell 脚本易错.

## 处方
- **bash**: `set -o pipefail` (管道任一段失败则整体失败) + `${PIPESTATUS[0]}` 取首段 exit
- **zsh**: `$pipestatus[1]` (1-indexed); 跨 shell 用 `bash -c '...'` 显式
- **python 异常**: `except Exception as e: log(e); raise` (记录 + 重抛, 不吞)
- **验证**: 故意触发失败 (如 push 到不存在 remote), 确认循环/脚本真检测到

## 同族（掩盖失败 = 最高级违规, 与 gaming 同级）
- 为变绿改断言 (改 expected 让 fail 变 pass)
- 调大 timeout 掩盖性能问题
- 往 baseline 塞违规
- `|| true` 绕过门禁
- `except: pass` 吞异常 (check-work-landed K3 待修)
- `cmd | tail` 吃 exit code (本轮 push 循环)

## 红线
掩盖失败 = 最高级违规. 失败必须**可见 + 可处置** (循环真 break / 异常真抛 / exit code 真传).
