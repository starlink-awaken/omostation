# BET-Y1Q3-T1-10 Retro

## 五问

1. **What happened?**  
   resident 常驻 agent 体系 (WP-A~I / ADR-0396) 的感知面在治理/CI/MCP/BOS 四层存在系统性缺口。通过 PR #2047 完成全覆盖。

2. **What went well?**  
   - 3 个 CR-RESIDENT check 工具（status/mof-sync/bos）一次落地并通过 gac-local-gate
   - ci-surfaces.yaml 和 governance-checks.yaml 同步登记
   - agent-workflows registry 新增 resident-runtime-observe workflow
   - docs/architecture/resident-agent-system-v1.md 漂移修复（Agora MCP 声明修正）

3. **What went poorly?**  
   - 台账状态未随 PR #2047 合并自动回写，导致 bet 仍显示 in_progress
   - Agora MCP resident 工具未实现，文档曾声明"已接线"造成漂移

4. **What did we learn?**  
   - PR 合入后必须同步更新 bet 台账状态（防 done 状态滞后）
   - 文档声明必须与实际代码对齐，L0 enforcement 引用不能悬空

5. **What should we do next?**  
   - 如需 Agora MCP resident 工具，新建 bet（运行时能力扩展）
   - 监控 CR-RESIDENT check 工具的 CI 执行率
