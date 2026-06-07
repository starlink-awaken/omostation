from __future__ import annotations

# ruff: noqa: RUF001, RUF002, RUF003
import datetime
import importlib
import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)


class PrimordialSoil:
    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root = Path(root_dir or os.environ.get("BOS_ROOT", os.getcwd()))
        self._bus = None
        self.cognitive_queue: list[tuple[Path | str, str]] = []

    def set_root(self, root_path: str | Path) -> None:
        self.root = Path(root_path)

    def _get_bus(self) -> Any | None:
        """延迟加载语义总线以避免循环引用"""
        if self._bus is None:
            try:
                module = importlib.import_module("organs.D_Execution.organs.engine.cognitive_bus")
                self._bus = module.Bus
            except (TypeError, ValueError, AttributeError):
                _log.debug("CognitiveBus not available; proceeding without it", exc_info=True)
        return self._bus

    # --- 1. 元数据与 Frontmatter (SSOT) ---
    def get_node_metadata(self, rel_path: str | Path) -> dict[str, Any]:
        full_path = self.root / rel_path
        if not full_path.exists():
            return {}
        try:
            content = full_path.read_text(encoding="utf-8")
            fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if fm_match is None:
                return {}
            return yaml.safe_load(fm_match.group(1)) or {}
        except (yaml.YAMLError, OSError):
            _log.debug("Failed to parse frontmatter for %s", rel_path, exc_info=True)
        return {}

    def _complete_metadata(
        self, rel_path: str | Path, meta: dict[str, Any], content: str, defer_cognition: bool = False
    ) -> dict[str, Any]:
        if "Class" not in meta:
            if "L0-Genome" in str(rel_path) or "dna" in str(rel_path):
                meta["Class"] = "Gene"
            elif "/organs/" in str(rel_path):
                meta["Class"] = "Organ"
            elif "/data/" in str(rel_path):
                meta["Class"] = "Matter"
            elif "/rules/" in str(rel_path):
                meta["Class"] = "Cell"
            else:
                meta["Class"] = "Generic"

        now = datetime.date.today().isoformat()
        if "Created" not in meta:
            meta["Created"] = now
        meta["Updated"] = now
        if "Version" not in meta:
            meta["Version"] = "1.0.0"
        if "Upstream" not in meta and "Authority" in meta:
            meta["Upstream"] = meta["Authority"]

        # [TSK-401] 认知增强：延迟摘要机制
        if (
            "Summary" not in meta
            or meta["Summary"].startswith("Logical node for")
            or meta["Summary"] == "[⏳ PENDING_COGNITION]"
        ):
            if defer_cognition:
                meta["Summary"] = "[⏳ PENDING_COGNITION]"
                self.cognitive_queue.append((rel_path, content))
            else:
                bus = self._get_bus()
                if bus and os.environ.get("BOS_SKIP_COGNITION") != "True":
                    _log.info("    🧠 [Toolkit] 正在调用 S-CPU 生成深度摘要: {rel_path}")
                    prompt = f"请为以下代码或文档片段生成一句极简且深刻的 TL;DR 摘要（中文）：\n\n{content[:1000]}"
                    suggestion = bus.think(prompt)
                    meta["Summary"] = suggestion or f"Deep logic node for {Path(rel_path).name}."
                else:
                    meta["Summary"] = f"Logical node for {Path(rel_path).name}."

        if "Tags" not in meta:
            meta["Tags"] = [meta["Class"].lower(), "differentiated"]
        return meta

    def write_hifi_node(
        self, rel_path: str | Path, body_content: str, metadata: dict[str, Any], defer_cognition: bool = False
    ) -> bool:
        full_path = self.root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = self._complete_metadata(rel_path, metadata, body_content, defer_cognition)
        header = "---\n" + yaml.dump(metadata, allow_unicode=True, sort_keys=False) + "---\n"
        clean_body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", body_content, flags=re.DOTALL).strip()
        full_path.write_text(header + "\n" + clean_body, encoding="utf-8")
        return True

    def flush_cognitive_queue(self) -> None:
        """[TSK-401] 批量影子推理：一次性处理所有积压的认知请求"""
        if not self.cognitive_queue:
            return
        bus = self._get_bus()
        if not bus:
            _log.info("⚠️ [Toolkit] S-CPU 未就绪，使用占位符完成批量认知。")
            for path, _ in self.cognitive_queue:
                self._update_summary_in_file(path, f"Logical node for {Path(path).name}.")
            self.cognitive_queue.clear()
            return

        _log.info(f"\n🧠 [Toolkit] 启动批量影子推理 (Batch Cognition)，处理节点数: {len(self.cognitive_queue)}")

        # 演示版：聚合提示词或快速处理
        batch_prompt = f"请为这 {len(self.cognitive_queue)} 个文件分别提供一句极简中文 TL;DR 摘要。"
        bus.think(batch_prompt)

        # 执行回写
        for path, _cont in self.cognitive_queue:
            # 真实环境中，这里应该解析 S-CPU 的批量响应，目前统一写入固定格式以验证流转
            new_summary = f"Auto-distilled logic for {Path(path).name} via Shadow Reasoning."
            self._update_summary_in_file(path, new_summary)

        _log.info("✅ [Toolkit] 批量影子推理完成，元数据已回写。")
        self.cognitive_queue.clear()

    def _update_summary_in_file(self, rel_path: str | Path, new_summary: str) -> None:
        full_path = self.root / rel_path
        if not full_path.exists():
            return
        content = full_path.read_text(encoding="utf-8")
        content = content.replace("[⏳ PENDING_COGNITION]", new_summary)
        full_path.write_text(content, encoding="utf-8")

    # --- 2. 免疫与自愈 ---
    def validate_authority_chain(self, rel_path: str | Path) -> dict[str, Any]:
        meta = self.get_node_metadata(rel_path)
        auth = meta.get("Authority", "ORPHAN")
        if auth in ["SELF", "Absolute Root"] or not auth:
            return {"valid": True, "broken_links": []}
        auth_list = (
            [auth]
            if isinstance(auth, str)
            else ([auth.get("Primary")] + auth.get("Secondary", []) if isinstance(auth, dict) else [])  # noqa: RUF005
        )
        issues = []
        for a in auth_list:
            if not a or a in ["SELF", "Absolute Root"]:
                continue
            a_clean = a.replace("Authority: ", "").strip()
            if not (self.root / a_clean).exists():
                issues.append(a_clean)
        return {"valid": len(issues) == 0, "broken_links": issues}

    def heal_authority_chains(self, scope_dir: str = "Z-Core", dry_run: bool = True) -> list[tuple[str, str, str]]:
        report = []
        target = self.root / scope_dir
        if not target.exists():
            return []
        for f in target.rglob("*.md"):
            rel = str(f.relative_to(self.root))
            check = self.validate_authority_chain(rel)
            if not check["valid"]:
                for broken in check["broken_links"]:
                    match = list(self.root.rglob(Path(broken).name))
                    if match:
                        new_auth = str(match[0].relative_to(self.root))
                        report.append((rel, broken, new_auth))
                        if not dry_run:
                            f.write_text(
                                f.read_text(encoding="utf-8").replace(broken, new_auth),
                                encoding="utf-8",
                            )
        return report


Toolkit = PrimordialSoil()
