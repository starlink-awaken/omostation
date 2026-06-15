from typing import Protocol, List, Optional
from .domain import PitchSchema, BetSchema, TaskSchema

class IGovernanceProvider(Protocol):
    def validate_pitch(self, pitch: PitchSchema) -> bool:
        """验证 Pitch 是否符合战略规范 (例如 Appetite, Upstream)."""
        ...
    
    def validate_task(self, task: TaskSchema) -> bool:
        """验证生成的执行任务是否合规."""
        ...
        
    def get_current_phase(self) -> str:
        """获取系统当前的生命周期阶段 (例如 Phase 42)."""
        ...

class IStorageProvider(Protocol):
    def save_bet(self, bet: BetSchema) -> str:
        """存储战略目标 (Bet). 返回 Bet ID."""
        ...
        
    def save_task(self, task: TaskSchema) -> str:
        """存储拆解出的任务 (Task). 返回 Task ID."""
        ...
        
    def get_pitches(self) -> List[PitchSchema]:
        """获取沙箱中所有的 Pitch."""
        ...
        
    def delete_pitch(self, pitch_id: str) -> bool:
        """删除 (或归档) 已处理/滞留的 Pitch."""
        ...
        
    def get_active_bets(self) -> List[BetSchema]:
        """获取当前活跃的所有 Bets."""
        ...
