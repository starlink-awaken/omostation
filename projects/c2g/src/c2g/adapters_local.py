import json
from pathlib import Path
from typing import List
from .ports import IGovernanceProvider, IStorageProvider
from .domain import PitchSchema, BetSchema, TaskSchema

class LocalGovernanceProvider(IGovernanceProvider):
    def validate_pitch(self, pitch: PitchSchema) -> bool:
        if not pitch.title or len(pitch.title) < 3:
            print("❌ Pitch 标题过短。")
            return False
        return True

    def validate_task(self, task: TaskSchema) -> bool:
        if not task.title:
            return False
        return True

    def get_current_phase(self) -> str:
        return "Local Default Phase"

class LocalStorageProvider(IStorageProvider):
    def __init__(self, base_dir: str = ".c2g_data"):
        self.base_dir = Path(base_dir)
        self.pitches_dir = self.base_dir / "pitches"
        self.bets_file = self.base_dir / "bets.json"
        self.tasks_file = self.base_dir / "tasks.json"
        self._init_fs()

    def _init_fs(self):
        self.pitches_dir.mkdir(parents=True, exist_ok=True)
        if not self.bets_file.exists():
            self.bets_file.write_text("[]", encoding="utf-8")
        if not self.tasks_file.exists():
            self.tasks_file.write_text("[]", encoding="utf-8")

    def save_bet(self, bet: BetSchema) -> str:
        data = json.loads(self.bets_file.read_text(encoding="utf-8"))
        data.append(bet.model_dump())
        self.bets_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return bet.goal_id

    def save_task(self, task: TaskSchema) -> str:
        data = json.loads(self.tasks_file.read_text(encoding="utf-8"))
        data.append(task.model_dump())
        self.tasks_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return task.task_id

    def get_pitches(self) -> List[PitchSchema]:
        pitches = []
        for pf in self.pitches_dir.glob("*.md"):
            content = pf.read_text(encoding="utf-8")
            pitches.append(PitchSchema(
                pitch_id=pf.name,
                title=pf.stem,
                content=content,
                created_at=""
            ))
        return pitches

    def delete_pitch(self, pitch_id: str) -> bool:
        pf = self.pitches_dir / pitch_id
        if pf.exists():
            pf.unlink()
            return True
        return False

    def get_active_bets(self) -> List[BetSchema]:
        data = json.loads(self.bets_file.read_text(encoding="utf-8"))
        return [BetSchema(**d) for d in data if d.get("status") == "active"]
