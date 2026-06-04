# OMO v4.0 (The OS Kernel) - Agent Instructions

Welcome to the OMO v4.0 Kernel. 
If you are an AI Agent assigned to work in this workspace, you MUST obey the following Contract-based Dispatch rules.

## 1. Do NOT modify `.omo` directly
The `.omo` directory is the K0 Data layer (the Database). You should NEVER manually create tasks, modify locks, or delete drafts directly unless absolutely necessary.
Instead, use the `omo-cli` toolchain to interact with it.

## 2. Using the OMO CLI
All commands should be run using `uvx omo-cli` (or `PYTHONPATH=projects/omo/src python3 projects/omo/src/omo/cli.py` if not installed globally).

- `omo bridge <file.md> --sequential`: Import external BMAD/Markdown specs into OMO planned tasks.
- `omo worker dispatch`: Fetch your next task. This will create `.omo/workers/runs/xxx-prompt.md`.
- `omo-debt analyze`: Check the current system technical debt before writing new features.
- `omo ledger`: Snapshot the workspace state.

## 3. The Execution Loop
1. When you enter the workspace, check `.omo/_truth/goals/current.yaml` to understand the overarching Phase and Wave.
2. Look in `.omo/workers/runs/` for any `*-prompt.md` files assigned to you.
3. Execute the work in the specified `allowed_paths`.
4. Create a `*-review.md` file in `.omo/workers/runs/` detailing what you changed.
5. NEVER bypass the Micro-DAG. If your task is blocked by `depends_on`, wait or resolve the dependency first.

Remember: LLM = CPU, Agent = OS. OMO is the OS. You are the CPU. Follow the OS instructions.
