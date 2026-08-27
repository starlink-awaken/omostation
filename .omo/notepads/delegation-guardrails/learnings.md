## [2026-08-07] P3: 会话经验固化（防复发）
1. 技能索引 = 会话启动快照；新 skill 本会话不可见，需新会话生效
2. CI 基线归因判据：main 同 job 同失败 ⇒ 基线预存（30 秒定性，P78 四问之反证）
3. 逃生口：SWARM_ESCAPE_ID + swarm-git --no-verify（白名单+台账），勿裸 --no-verify
4. preflight 工具实测：正常 EXIT=0（5 critical PASS），--base-url 故障注入 EXIT=1（endpoint FAIL 检测正确）
5. worktree 卫生：gac-worktree-prune.sh 清理 10 个过期 work/* 分支（TTL 24h）
