---
type: ssot
---

# ssot-stable — mail-daemon 运行时稳定副本 (2026-08-25)

## 为什么存在

主 worktree 的分支随并行 agent 施工频繁切换(单日 4+ 次), mail_daemon.py
等运行时文件在某些分支上不存在 → launchd 每 30min 空跑
(mail-daemon.err: No such file or directory, jsonl 断档 8h 实锤)。
本副本将运行时与工作区解耦(同 aetherforge-final-ae3570f 思路)。

launchd plist(com.omostation.mail-daemon)已改指本目录(备份:
plist.bak-20260825-runtime-stable)。

## 同步纪律

bin/ssot/ 源码变更后需手动同步:
  cp ~/Workspace/bin/ssot/{mail_daemon,mail_agent,mail_reader,mail_sender,doc_generator,_llm_helper,_shared}.py ~/Workspace/runtime/ssot-stable/
变更里程碑建议顺手同步一次(等价于"发布")。自动化同步挂账待议——
源码热同步与"稳定"语义冲突, 需要版本化发布流程再上。
