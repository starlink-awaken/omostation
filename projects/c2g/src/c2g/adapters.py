from typing import Optional, List
import importlib
from .ports import IGovernanceProvider, IStorageProvider
from .domain import PitchSchema, BetSchema, TaskSchema

class EcosGovernanceProvider(IGovernanceProvider):
    def __init__(self):
        try:
            self.omo_task_schema = importlib.import_module("omo.omo_task_schema")
        except ImportError:
            raise ImportError("The 'omo' package is required to use EcosGovernanceProvider. Install c2g[ecos].")

    def validate_pitch(self, pitch: PitchSchema) -> bool:
        if not pitch.upstream_ref:
            print(f"  ❌ [CR-STRATEGY-01 孤儿拦截] Pitch缺乏Upstream锚点，拒绝转化为Bet。")
            return False
        return True

    def validate_task(self, task: TaskSchema) -> bool:
        errors = self.omo_task_schema.validate_task_data(task.model_dump(), group="planned")
        if errors:
            print("  ❌ M2 防腐层拦截 (Schema Validation Failed)")
            for err in errors:
                print(f"     - {err}")
            return False
        return True

    def get_current_phase(self) -> str:
        # Dummy implementation for now
        return "Phase 42"

class EcosStorageProvider(IStorageProvider):
    def __init__(self, omo_dir_path):
        from pathlib import Path
        self.omo_dir = Path(omo_dir_path)
        try:
            self.omo_goal = importlib.import_module("omo.omo_goal")
        except ImportError:
            raise ImportError("The 'omo' package is required to use EcosStorageProvider. Install c2g[ecos].")

    def save_bet(self, bet: BetSchema) -> str:
        self.omo_goal.cmd_goal_create(self.omo_dir, bet.goal_id, f"Bet: {bet.title} (Appetite: {bet.appetite})")
        return bet.goal_id

    def save_task(self, task: TaskSchema) -> str:
        import yaml
        planned_dir = self.omo_dir / "tasks" / "planned"
        planned_dir.mkdir(parents=True, exist_ok=True)
        task_file = planned_dir / f"{task.task_id}.yaml"
        task_file.write_text(yaml.dump(task.model_dump(), allow_unicode=True, sort_keys=False))
        return task.task_id

    def get_pitches(self) -> List[PitchSchema]:
        import hashlib
        sandbox_dir = self.omo_dir.parent / "runtime" / "sandbox" / "pitches"
        if not sandbox_dir.exists():
            return []
        
        pitches = []
        for pf in sandbox_dir.glob("*.md"):
            content = pf.read_text(encoding="utf-8")
            upstream = None
            appetite = "Unknown"
            for line in content.split("\n"):
                if "> **Upstream**" in line:
                    upstream = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                if "**Appetite:**" in line:
                    appetite = line.replace("**Appetite:**", "").strip()
            
            p = PitchSchema(
                pitch_id=pf.name,
                title=pf.stem,
                content=content,
                upstream_ref=upstream,
                appetite=appetite,
                created_at="Unknown"
            )
            pitches.append(p)
        return pitches

    def delete_pitch(self, pitch_id: str) -> bool:
        pf = self.omo_dir.parent / "runtime" / "sandbox" / "pitches" / pitch_id
        if pf.exists():
            pf.unlink()
            return True
        return False

    def get_active_bets(self) -> List[BetSchema]:
        # Minimal mock for radar
        return [
            BetSchema(goal_id="BET-1", title="Indie Efficiency", description="", vector="V1", created_at=""),
            BetSchema(goal_id="BET-2", title="Agent Autonomy", description="", vector="V2", created_at="")
        ]

def get_providers(omo_dir_path):
    # Dependency Injection point
    # Could fall back to Local providers if OMO is not installed
    return EcosGovernanceProvider(), EcosStorageProvider(omo_dir_path)
