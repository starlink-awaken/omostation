from __future__ import annotations

# ruff: noqa: RUF003

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
---
"""


"""
---
Type: Module
Status: ACTIVE
Layer: L3
---
"""

import logging
import os
import re
from pathlib import Path

import yaml

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ System_Bus
# 内涵 ≝ {Routing, Scheduling, Communication}
# 外延 ≝ {m | m ∈ Z-Microkernel ∧ orchestrates(m, Communication)}
# 功能 ⊢ {RouteMessages, ScheduleTasks, ManageBus}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sage'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-16_archetype_library_axiom.md
Layer: L-∞ (Origin)
Constraint: "[!!] ARCHETYPE_DISTILLER"
---
"""
# 🧪 原型萃取器 (Archetype Distiller - AD-01)
# 职责: 物理执行“萃取”动作，将现役资产转化为符合 ST01-06 标准的无状态原型。

_log = logging.getLogger(__name__)


class ArchetypeDistiller:
    def __init__(self, root_dir: str | Path | None = None) -> None:
        super().__init__()
        self.root = Path(root_dir or os.environ.get("BOS_ROOT", os.getcwd()))
        self.archetype_base = self.root / "nucleus/Z-Spore/archetypes"

    def distill(self, source_rel_path: str, target_cat: str) -> bool:
        source_p = self.root / source_rel_path
        if not source_p.exists():
            _log.info("❌ [Distiller] 找不到源文件: {source_rel_path}")
            return False

        _log.info("🧪 [Distiller] 正在萃取本质: {source_rel_path} -> {target_cat}")
        content = source_p.read_text(encoding="utf-8")
        root_str = str(self.root)
        distilled_content = content.replace(root_str, "{{BOS_ROOT}}")

        fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n", distilled_content, re.DOTALL)
        if fm_match:
            try:
                meta = yaml.safe_load(fm_match.group(1)) or {}
            except (yaml.YAMLError, OSError) as e:
                _log.error("%s: %s", type(e).__name__, e)
                meta = {}
            template_meta = {
                "Type": "Template",
                "Status": "STABLE",
                "Origin_Class": meta.get("Class", "Unknown"),
                "Upstream": source_rel_path,
                "Summary": f"Drawn from {source_p.name} for global reuse.",
                "Archetype": {
                    "Purity_Level": 1.0,
                    "Parameters": [{"name": "ROOT", "placeholder": "{{BOS_ROOT}}"}],
                },
            }
            if "Membrane" in meta:
                template_meta["Membrane"] = meta["Membrane"]
            header = "---\n" + yaml.dump(template_meta, allow_unicode=True, sort_keys=False) + "---\n"
            body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", distilled_content, flags=re.DOTALL).strip()
            distilled_content = header + "\n" + body

        target_p = self.archetype_base / target_cat / source_p.name
        target_p.parent.mkdir(parents=True, exist_ok=True)
        target_p.write_text(distilled_content, encoding="utf-8")
        try:
            _log.info("✅ [Distiller] 萃取完成: {target_p.relative_to(self.root)}")
        except (yaml.YAMLError, OSError):
            _log.info("✅ [Distiller] 萃取完成 (跨域): {target_p}")
        return True


Distiller = ArchetypeDistiller()
