from __future__ import annotations

# ruff: noqa: RUF003

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-GN01-01_differentiation_protocol.md
---
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Z_Spore_Component ≡ System_Core
# 内涵 ≝ {Bootstrap, Genesis, DNA_Management}
# 外延 ≝ {c | c ∈ Z-Spore ∧ essential(c, System)}
# 功能 ⊢ {InitializeSystem, ManageDNA, BootstrapArchitecture}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sage'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-PT01-mutation_protocol.md
Layer: L3
Constraint: "[!!] MUTATION_SAFEGUARD"
---
"""
# 🛡️ 突变验证器 (Mutation Validator - MV-01)
# 职责: 物理执行 PT01 协议中的“影子验证”，确保基因突变不会导致系统发育畸形。

_log = logging.getLogger(__name__)


class MutationValidator:
    def __init__(self, root_dir: str | Path | None = None) -> None:
        super().__init__()
        self.root = Path(root_dir or os.environ.get("BOS_ROOT", os.getcwd()))
        self.shadow_root = self.root / ".runtime/shadow_bos"

    def validate_proposal(self, proposal_dna_path: str) -> tuple[bool, str]:
        """
        [Phase 2: Shadow Testing]
        1. 建立纯净的影子空间。
        2. 将提议的 DNA 覆盖进影子空间的 Z-Spore。
        3. 执行 bootstrap.py 尝试全链路分化。
        4. 审计分化产物的完整性。
        """
        _log.info("\n🧬 [Validator] 启动影子验证: {proposal_dna_path}")

        # 1. 环境准备
        if self.shadow_root.exists():
            shutil.rmtree(self.shadow_root)
        self.shadow_root.mkdir(parents=True, exist_ok=True)

        # 2. 物理克隆 (仅克隆 Z-Spore 用于测试)
        _log.info("  └─ 正在构建影子起源环境...")
        shutil.copytree(self.root / "Z-Spore", self.shadow_root / "Z-Spore")

        # 3. 注入突变基因
        target_dna = self.shadow_root / "Z-Spore/dna" / Path(proposal_dna_path).name
        shutil.copy(self.root / proposal_dna_path, target_dna)
        _log.info("  └─ 注入突变基因: {target_dna.name}")

        # 4. 执行创世测试
        _log.info("  🚀 正在影子空间启动创世自举测试...")
        try:
            # 禁用影子空间中的认知增强以节省 Token 并加快速度
            env = os.environ.copy()
            env["BOS_SKIP_COGNITION"] = "True"
            env["BOS_ROOT"] = str(self.shadow_root)

            result = subprocess.run(
                [sys.executable, "Z-Spore/bootstrap.py"],
                cwd=self.shadow_root,
                env=env,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                _log.info("  ✅ [Success] 突变基因通过了创世发育测试。")
                return True, "Mutation is stable."
            else:
                _log.info("  ❌ [Failure] 突变导致发育畸形:\n{result.stderr}")
                return False, result.stderr
        except (subprocess.CalledProcessError, OSError) as e:
            return False, str(e)


_log = logging.getLogger(__name__)

Validator = MutationValidator()
