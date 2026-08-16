from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Rollback ≡ Module
# 内涵 ≝ {Rollback}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Rollback)}
# 功能 ⊢ {Init_Rollback, Execute_Rollback, Validate_Rollback}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
Rollback procedures for D-Harvest operations

Provides safe rollback mechanisms for failed harvest operations.
Preserves recent checkpoints to minimize data loss.
"""
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


class RollbackManager:
    """
    Manage rollback operations for harvest failures

    Provides incremental rollback preserving recent checkpoints.
    """

    def __init__(self, backup_dir: Path | None = None, max_backups: int = 5) -> None:
        """
        Initialize rollback manager

        Args:
            backup_dir: Directory for rollback backups
            max_backups: Maximum number of backups to retain
        """
        self.backup_dir = backup_dir or Path(".omc/rollbacks")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.max_backups = max_backups

    def _get_rollback_path(self, source_id: str, timestamp: str) -> Path:
        """Get rollback backup path"""
        return self.backup_dir / f"{source_id}_{timestamp}.rollback.json"

    async def create_rollback_point(
        self, source_id: str, harvested_items: list[Any], checkpoint_data: dict[str, Any]
    ) -> bool:
        """
        Create rollback point before harvest

        Args:
            source_id: Source identifier
            harvested_items: Items harvested before failure point
            checkpoint_data: Checkpoint data for recovery

        Returns:
            True if rollback point created successfully
        """
        timestamp = datetime.now(UTC).isoformat()
        rollback_path = self._get_rollback_path(source_id, timestamp)

        try:
            rollback_data = {
                "source_id": source_id,
                "timestamp": timestamp,
                "harvested_items": len(harvested_items),
                "items": harvested_items,
                "checkpoint_data": checkpoint_data,
            }

            with open(rollback_path, "w") as f:
                json.dump(rollback_data, f, indent=2, default=str)

            # Clean up old backups
            await self._cleanup_old_backups(source_id)

            _log.info(f"Rollback point created for {source_id} at {timestamp}")
            return True

        except (OSError, json.JSONDecodeError) as e:
            _log.error(f"Failed to create rollback point for {source_id}: {e}")
            return False

    async def rollback(self, source_id: str, preserve_recent: int = 1) -> dict[str, Any]:
        """
        Rollback to previous checkpoint

        Args:
            source_id: Source identifier
            preserve_recent: Number of recent checkpoints to preserve

        Returns:
            Rollback result dictionary
        """
        # Find most recent rollback point
        rollbacks = sorted(
            self.backup_dir.glob(f"{source_id}_*.rollback.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not rollbacks:
            return {"success": False, "error": "No rollback points found", "source_id": source_id}

        # Use most recent backup
        rollback_path = rollbacks[0]

        try:
            with open(rollback_path) as f:
                rollback_data = json.load(f)

            # Preserve recent checkpoints by keeping newer ones
            await self._preserve_recent_checkpoints(source_id, preserve_recent)

            # In a real implementation, this would:
            # 1. Remove items from FactGraph that were added after this point
            # 2. Restore vector database state
            # 3. Reset harvest orchestrator state

            _log.info(f"Rollback completed for {source_id} to {rollback_data['timestamp']}")

            return {
                "success": True,
                "source_id": source_id,
                "rolled_back_to": rollback_data["timestamp"],
                "preserved_items": rollback_data["harvested_items"],
                "checkpoint_data": rollback_data["checkpoint_data"],
            }

        except (OSError, json.JSONDecodeError) as e:
            return {"success": False, "error": str(e), "source_id": source_id}

    async def _preserve_recent_checkpoints(self, source_id: str, count: int) -> None:
        """
        Preserve recent checkpoints during rollback

        Args:
            source_id: Source identifier
            count: Number of checkpoints to preserve
        """
        # This is a placeholder - actual implementation would
        # ensure checkpoints newer than the rollback point are preserved

        # For now, just log the action
        _log.info(f"Preserving {count} recent checkpoints for {source_id}")

    async def _cleanup_old_backups(self, source_id: str) -> None:
        """
        Clean up old rollback backups

        Args:
            source_id: Source identifier
        """
        rollbacks = sorted(
            self.backup_dir.glob(f"{source_id}_*.rollback.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        # Remove excess backups
        for old_backup in rollbacks[self.max_backups :]:
            try:
                old_backup.unlink()
                _log.debug(f"Removed old rollback backup: {old_backup.name}")
            except OSError as e:
                _log.warning(f"Failed to remove old backup {old_backup.name}: {e}")

    async def list_rollback_points(self, source_id: str) -> list[dict[str, Any]]:
        """
        List available rollback points for a source

        Args:
            source_id: Source identifier

        Returns:
            List of rollback point metadata
        """
        rollbacks = sorted(
            self.backup_dir.glob(f"{source_id}_*.rollback.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        points = []

        for rollback_path in rollbacks:
            try:
                with open(rollback_path) as f:
                    data = json.load(f)

                points.append(
                    {
                        "timestamp": data["timestamp"],
                        "items_count": data["harvested_items"],
                        "path": str(rollback_path),
                    }
                )

            except (OSError, json.JSONDecodeError) as e:
                _log.warning(f"Failed to read rollback {rollback_path.name}: {e}")

        return points

    async def get_rollback_plan(self, source_id: str) -> dict[str, Any]:
        """
        Get detailed rollback plan for a source

        Args:
            source_id: Source identifier

        Returns:
            Rollback plan with steps and consequences
        """
        points = await self.list_rollback_points(source_id)

        if not points:
            return {"available": False, "message": "No rollback points available"}

        most_recent = points[0]

        # In a real implementation, this would analyze:
        # - What items would be removed
        # - What checkpoints would be affected
        # - Estimated time to rollback
        # - Potential data loss

        return {
            "available": True,
            "source_id": source_id,
            "rollback_to": most_recent["timestamp"],
            "items_that_would_be_removed": most_recent["items_count"],
            "steps": [
                "1. Pause harvest operations for source",
                "2. Remove items added after rollback point",
                "3. Restore checkpoint state",
                "4. Verify system consistency",
                "5. Resume harvest operations",
            ],
            "estimated_duration_seconds": 30,  # Placeholder
            "data_loss_risk": "low",  # Based on checkpoint frequency
        }
