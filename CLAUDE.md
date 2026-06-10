# OMO v4.0 (The OS Kernel) - Agent Instructions

Welcome to the OMO v4.0 Kernel. 
If you are an AI Agent assigned to work in this workspace, you MUST obey the following Contract-based Dispatch rules.

## 1. Do NOT modify `.omo` directly
The `.omo` directory is the K0 Data layer (the Database). You should NEVER manually create tasks, modify locks, or delete drafts directly unless absolutely necessary.
Instead, use the `omo-cli` toolchain to interact with it.

## 2. Using the OMO MCP Server (Hard Isolation)
All commands MUST be run using the `omo` MCP server. Direct filesystem manipulation of `.omo/` or direct invocation of the CLI is strictly forbidden to prevent privilege escalation.

- Call the `omo_bridge` MCP tool to import external BMAD/Markdown specs into OMO planned tasks.
- Call the `omo_worker_dispatch` MCP tool to fetch your next task. This will create `.omo/workers/runs/xxx-prompt.md`.
- Call the `omo_worker_reclaim` MCP tool to submit your work when done.
- Call the `omo_gc` MCP tool to snapshot and clean up the workspace state.

## 3. The Execution Loop
1. When you enter the workspace, check `.omo/_truth/goals/current.yaml` to understand the overarching Phase and Wave.
2. Look in `.omo/workers/runs/` for any `*-prompt.md` files assigned to you.
3. Execute the work in the specified `allowed_paths`.
4. Create a `*-review.md` file in `.omo/workers/runs/` detailing what you changed.
5. NEVER bypass the Micro-DAG. If your task is blocked by `depends_on`, wait or resolve the dependency first.

Remember: LLM = CPU, Agent = OS. OMO is the OS. You are the CPU. Follow the OS instructions.

## 4. The Law of Prudence (Anti-Optimism Directive)
- **NO HALLUCINATORY VICTORIES**: Do not declare "perfect alignment" or "flawless execution" just because your code logic is complete. Success requires hard data from the `health_score` or active integration tests.
- **DEVIL'S ADVOCATE**: Before declaring a task done, force yourself to evaluate the 3 worst-case edge scenarios.
- **OBJECTIVE TONE**: Strip all emotional boosterism from your summaries. Use cold, factual, and rigorous language. Read `.omo/_knowledge/process/retrospectives/RETRO-ANTI-OPTIMISM.md` for historical context on why this is strictly enforced.
