from __future__ import annotations

# ruff: noqa: RUF001, RUF002, RUF003
from ._compat import Gateway, ProjectPaths

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import json
import logging
import os
import re
import sqlite3
from typing import Any

from .organs.intent_particle import (  # type: ignore[import-not-found]
    IntentParticle,
    MetabolicStage,
    VisionParticle,
)

try:
    MetaEvolveEngine = __import__("organs.D_Logos.organs", fromlist=["MetaEvolveEngine"]).MetaEvolveEngine

    _MetaEngineClass = MetaEvolveEngine
except ImportError:
    _MetaEngineClass = None

try:
    MetabolicLock = __import__("organs.D_Immunity.organs.metabolic_lock", fromlist=["MetabolicLock"]).MetabolicLock
except ImportError:
    MetabolicLock = None

try:
    EnergyDistributor = __import__(
        "organs.D_Economy.organs.energy_distributor", fromlist=["EnergyDistributor"]
    ).EnergyDistributor
except ImportError:
    EnergyDistributor = None

try:
    EnergyLedger = __import__("organs.D_Economy.organs.energy_ledger", fromlist=["EnergyLedger"]).EnergyLedger
except ImportError:
    EnergyLedger = None

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Execution_Organ ≡ Task_Executor
# 内涵 ≝ {Execute, Orchestrate, Manage}
# 外延 ≝ {e | e ∈ D-Execution ∧ executes(e, Tasks)}
# 功能 ⊢ {ExecuteTasks, ManageWorkspace, OrchestrateAgents}
# =============================================================================

"""
---
Type: Organ
Status: BETA
Version: 1.1.0
Owner: '@Architect'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
Layer: L3
Constraint: "[!!] INTENT_DIGESTOR_SCAFFOLDING"
Summary: '意图消化器 (IntentDigestor)：负责将原始意图拆解为 IntentParticle 群落。'
---
"""

_log = logging.getLogger(__name__)

# PII masking patterns (compiled once)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-+]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?<!\w)(\+?\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}")
_NAME_RE = re.compile(
    r"(?<![a-zA-Z])(?:(?:Dr|Mr|Mrs|Ms|Miss|Prof|Prof\.)[\s]+)?"
    r"(?:[A-ZÄÖÜÉÀÈÌ][a-zäöüéàèì]+[\s]+){1,3}[A-ZÄÖÜÉÀÈÌ][a-zäöüéàèì]+",
    re.UNICODE,
)
_ADDRESS_RE = re.compile(
    r"\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way|court|ct|road)[\s,]+[\w\s]+",
    re.IGNORECASE,
)


def _mask_pii(text: str) -> str:
    """Redact PII from free-form text before logging."""
    if not text:
        return text
    # Mask emails
    text = _EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    # Mask phone numbers
    text = _PHONE_RE.sub("[PHONE_REDACTED]", text)
    # Mask names (2–4 capitalized word sequences)
    text = _NAME_RE.sub("[NAME_REDACTED]", text)
    # Mask street addresses
    text = _ADDRESS_RE.sub("[ADDRESS_REDACTED]", text)
    return text


class IntentDigestor:
    """意图消化器 - 系统之胃"""

    def __init__(self, db_path: str = str(ProjectPaths.get_db_path("execution", "tasks.db"))) -> None:
        object.__init__(self)
        self.db_path = db_path
        self.gateway = Gateway
        self.lock = MetabolicLock() if MetabolicLock else None

        # 注入能量分配器 (Surgery 8: Metabolic Strategy)
        try:
            self.energy_distributor = EnergyDistributor() if EnergyDistributor else None
        except (TypeError, ValueError, AttributeError):
            self.energy_distributor = None

        # 可注入的能量账本 (供测试或外部注入；None 表示使用默认 EnergyLedger)
        self.energy_ledger: Any | None = None

        self._init_metabolic_ledger()

    def _init_metabolic_ledger(self) -> None:
        """初始化代谢账本 (实事求是：状态必须落盘)。"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metabolic_particles (
                    id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    root_id TEXT,
                    intent TEXT,
                    stage TEXT,
                    estimated_eu REAL,
                    actual_eu REAL,
                    expected_nectar REAL,
                    required_capabilities TEXT,
                    dependencies TEXT,
                    assigned_role TEXT,
                    payload TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    failure_reason TEXT,
                    created_at REAL
                )
            """
            )
            conn.commit()
        except sqlite3.Error:
            _log.info("⚠️ [Digestor] Failed to init ledger: {e}")
        finally:
            conn.close()

    def ingest(self, raw_intent: str, context: dict | None = None) -> IntentParticle:
        """摄入原始意图。

        Args:
            raw_intent: 原始意图文本。
            context: 可选的上下文快照字典。

        Returns:
            新创建并落盘的 IntentParticle 实例。
        """
        _log.info("🍽️ [Digestor] 正在摄入意图: {_mask_pii(raw_intent[:50])}...")

        particle = IntentParticle(intent=raw_intent, stage=MetabolicStage.INGESTED, context_snapshot=context or {})

        self._persist_particle(particle)
        return particle

    def digest(self, root_particle: IntentParticle, use_llm: bool = False) -> list[IntentParticle]:
        """消化意图：执行语义拆解逻辑。

        Args:
            root_particle: 待消化的根意图粒子。
            use_llm: 是否使用动态 LLM 拆解。

        Returns:
            生成的子粒子列表。
        """
        _log.info("🧬 [Digestor] 正在执行语义消化: {root_particle.id}")

        # 1. 更新根节点状态
        self._update_particle_stage(root_particle.id, MetabolicStage.DIGESTING)

        # 2. 决策：动态还是静态
        if isinstance(root_particle, VisionParticle):
            sub_particles = self._vision_decomposition(root_particle)
        elif use_llm and self.gateway is not None:
            sub_particles = self._dynamic_decomposition(root_particle)
        else:
            sub_particles = self._static_decomposition(root_particle)

        # 2.1 安全加锁：DAG 拓扑与能量审计 (Phase 1 Evolution)
        if self.lock:
            # 2.1.1 拓扑校验 (Fatal)
            is_valid, level, reason = self.lock.validate_dag(sub_particles)
            if not is_valid:
                _log.info("🛑 [Digestor] DAG 校验失败 ({level}): {reason}")
                self._update_particle_stage(root_particle.id, MetabolicStage.EXCRETED)
                return []

            # 2.1.2 能量审计 (使用拆解出的原始预算进行初步审计)
            try:
                # 优先使用注入的账本（便于测试），否则动态实例化默认账本
                if self.energy_ledger is not None:
                    ledger = self.energy_ledger
                else:
                    ledger = EnergyLedger() if EnergyLedger else None
                    if ledger is None:
                        raise RuntimeError("EnergyLedger unavailable")
                balance = ledger.get_balance()

                is_ok, level, reason = self.lock.validate_energy_budget(sub_particles, balance)  # noqa: RUF059
                if level == "FATAL":
                    _log.info("🛑 [Digestor] 能量审计失败 (FATAL): {reason}")
                    self._update_particle_stage(root_particle.id, MetabolicStage.EXCRETED)
                    return []
                elif level == "WARNING":
                    _log.info("⚠️ [Digestor] 能量风险预警 (WARNING): {reason}")
            except (TypeError, ValueError, AttributeError):
                _log.info("⚠️ [Digestor] 能量审计跳过 (接驳异常): {e}")

        # 2.2 能量再分配 (Phase 3 Evolution)
        # 在审计通过后，根据父粒子的实际配额进行重分配
        if hasattr(self, "energy_distributor") and self.energy_distributor:
            strategy = root_particle.context_snapshot.get("metabolic_strategy", "POOLING")
            self.energy_distributor.distribute(root_particle, sub_particles, strategy=strategy)

        # 3. 物理落盘
        for p in sub_particles:
            self._persist_particle(p)
            _log.info("  └─ 孵化意图粒子: {p.id} ({p.intent})")

        return sub_particles

    def _dynamic_decomposition(self, root: IntentParticle) -> list[IntentParticle]:
        """调用本地 LLM 进行动态任务研磨。

        Args:
            root: 根意图粒子。

        Returns:
            拆解后的子粒子列表。
        """
        _log.info("🧠 [Digestor] 正在启动本地算力进行动态拆解...")

        # 建立拆解公理 Prompt
        prompt = f"""
        你作为 SharedBrain B-OS 的核心拆解引擎，请将以下意图拆解为 2-5 个具备依赖关系的子任务粒子。
        意图: {_mask_pii(root.intent)}

        输出格式必须为纯 JSON 数组，每个元素包含:
        - intent: 任务描述
        - caps: 所需能力列表 (例如: infra.scan, code.python, docs.write)
        - eu: 预估能量消耗 (0.1 - 5.0)
        - deps: 依赖项在数组中的索引列表 (例如: [0] 表示依赖第一个任务)

        示例输出:
        [
            {{"intent": "任务A", "caps": ["infra"], "eu": 0.5, "deps": []}},
            {{"intent": "任务B", "caps": ["code"], "eu": 1.5, "deps": [0]}}
        ]
        """

        # 为了提高智力，注入核心架构上下文
        seeds = ["nucleus/Z-Microkernel/organs", "organs/D-Execution/organs"]
        response = self.gateway.call(prompt, iq_req=7.0, spec="architect", seed_node_ids=seeds)

        if response.get("status") != "success":
            _log.info("⚠️ [Digestor] 动态拆解失败，回退至静态模式")
            return self._static_decomposition(root)

        # [Evolution V2] 记录意图研磨本身的能耗 (Surgery 6.3)
        usage = response.get("metadata", {}).get("usage")
        if usage:
            root.usage = usage
            _log.info("📊 [Digestor] 意图研磨能耗已同步 (Tokens: {usage.get('total_tokens')})")

        try:
            # 兼容性解析: 检查响应内容类型 (Surgery 5.1)
            raw_content = response.get("content")

            if isinstance(raw_content, list):
                plan = raw_content
            elif isinstance(raw_content, str):
                # 清洗并解析 JSON
                match = re.search(r"\[.*\]", raw_content, re.DOTALL)
                if not match:
                    raise ValueError("No JSON array found in LLM string response")
                plan = json.loads(match.group(0))
            else:
                raise ValueError(f"Unsupported content type: {type(raw_content)}")

            # 物理映射为 IntentParticle 对象
            particles = []
            for item in plan:
                p = IntentParticle(
                    parent_id=root.id,
                    root_id=root.root_id,
                    intent=item.get("intent", "未命名子任务"),
                    required_capabilities=item.get("caps", ["general"]),
                    estimated_eu=float(item.get("eu", 1.0)),
                    symphony_phase=3,
                )
                particles.append(p)

            # 建立依赖链路
            for i, item in enumerate(plan):
                for dep_idx in item.get("deps", []):
                    if dep_idx < len(particles):
                        particles[i].dependencies.append(particles[dep_idx].id)

            return particles

        except (TypeError, ValueError, AttributeError):
            _log.info("⚠️ [Digestor] 响应解析失败: {e}. 响应内容: {response.get('content')[:100]}...")
            return self._static_decomposition(root)

    def _vision_decomposition(self, root: VisionParticle) -> list[IntentParticle]:
        """将顶层 VisionParticle 通过 D-Logos 的 MetaEvolveEngine 拆解为 Symphony 任务流。"""
        if not _MetaEngineClass:
            _log.info("⚠️ [Digestor] MetaEvolveEngine 不可用，使用 Symphony 静态分解")
            return self._vision_symphony_decomposition(root)

        try:
            engine = _MetaEngineClass()
            plan = engine.breakdown_vision_to_symphony(root.intent, domain=root.vision_domain)

            particles = []
            # 1. 映射为对象
            for item in plan:
                p = IntentParticle(
                    parent_id=root.id,
                    root_id=root.root_id,
                    intent=item["intent"],
                    required_capabilities=item["caps"],
                    estimated_eu=root.estimated_eu * (item["eu"] / 4.5),  # 归一化权重
                    symphony_phase=item["phase"],
                )
                particles.append(p)

            # 2. 建立依赖关系
            for i, item in enumerate(plan):
                for dep_idx in item.get("deps", []):
                    if dep_idx < len(particles):
                        particles[i].dependencies.append(particles[dep_idx].id)

            return particles
        except (json.JSONDecodeError, OSError, ValueError) as e:
            _log.error(f"❌ [Digestor] Vision 拆解失败: {e}")
            return self._vision_symphony_decomposition(root)

    def _vision_symphony_decomposition(self, root: VisionParticle) -> list[IntentParticle]:
        """Symphony 四阶段静态分解 (VisionParticle 专用回退模式)。

        产出标准的 Anchoring → Scaffolding → Implementation → Polishing 任务流，
        保证 CapabilityMatcher 能正确匹配角色。
        """
        anchoring = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"[Anchoring] {root.intent}",
            required_capabilities=["vision_analysis", "context.anchoring"],
            symphony_phase=1,
            estimated_eu=root.estimated_eu * 0.15,
        )
        scaffolding = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"[Scaffolding] {root.intent}",
            required_capabilities=["architect", "system_design"],
            symphony_phase=2,
            dependencies=[anchoring.id],
            estimated_eu=root.estimated_eu * 0.25,
        )
        implementation = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"[Implementation] {root.intent}",
            required_capabilities=["coding", "python"],
            symphony_phase=3,
            dependencies=[scaffolding.id],
            estimated_eu=root.estimated_eu * 0.45,
        )
        polishing = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"[Polishing] {root.intent}",
            required_capabilities=["documentation", "code.refinement"],
            symphony_phase=4,
            dependencies=[implementation.id],
            estimated_eu=root.estimated_eu * 0.15,
        )
        return [anchoring, scaffolding, implementation, polishing]

    def _static_decomposition(self, root: IntentParticle) -> list[IntentParticle]:
        """静态拆解逻辑 (回退模式)。

        Args:
            root: 根意图粒子。

        Returns:
            生成的子粒子列表。
        """
        intent = root.intent.lower()

        # Pattern A: Architecture/refactoring
        if any(kw in intent for kw in ("架构", "重构", "refactor", "architecture")):
            return self._arch_decomposition(root)

        # Pattern B: Research/analysis
        if any(kw in intent for kw in ("调研", "研究", "分析", "research", "analyze", "analysis")):
            return self._research_decomposition(root)

        # Pattern C: Testing/validation
        if any(kw in intent for kw in ("测试", "验证", "test", "validate", "verify")):
            return self._test_decomposition(root)

        # Pattern D: Documentation
        if any(kw in intent for kw in ("文档", "文档化", "document", "docs")):
            return self._docs_decomposition(root)

        # Default: generic 2-phase
        return self._generic_decomposition(root)

    def _arch_decomposition(self, root: IntentParticle) -> list[IntentParticle]:
        """架构/重构类任务拆解。"""
        p1 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"全息图谱扫描: {root.intent[:30]}",
            required_capabilities=["infra.scan", "hifi.read"],
            symphony_phase=2,
            estimated_eu=0.3,
        )
        p2 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"逻辑实现: {root.intent[:30]}",
            required_capabilities=["code.implementation"],
            symphony_phase=3,
            dependencies=[p1.id],
            estimated_eu=1.5,
        )
        p3 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"打磨与文档: {root.intent[:30]}",
            required_capabilities=["documentation", "code.refinement"],
            symphony_phase=4,
            dependencies=[p2.id],
            estimated_eu=0.5,
        )
        return [p1, p2, p3]

    def _research_decomposition(self, root: IntentParticle) -> list[IntentParticle]:
        """调研/分析类任务拆解。"""
        p1 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"资料收集与文献调研: {root.intent[:30]}",
            required_capabilities=["research", "hifi.read"],
            symphony_phase=1,
            estimated_eu=0.4,
        )
        p2 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"深度分析与模式提取: {root.intent[:30]}",
            required_capabilities=["data_analysis", "theoretical.modeling"],
            symphony_phase=2,
            dependencies=[p1.id],
            estimated_eu=0.8,
        )
        p3 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"结论综合与报告: {root.intent[:30]}",
            required_capabilities=["report_generation", "documentation"],
            symphony_phase=3,
            dependencies=[p2.id],
            estimated_eu=0.5,
        )
        return [p1, p2, p3]

    def _test_decomposition(self, root: IntentParticle) -> list[IntentParticle]:
        """测试/验证类任务拆解。"""
        p1 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"测试规划与用例设计: {root.intent[:30]}",
            required_capabilities=["test.design", "theoretical.modeling"],
            symphony_phase=1,
            estimated_eu=0.3,
        )
        p2 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"测试实现与执行: {root.intent[:30]}",
            required_capabilities=["code.testing", "code.implementation"],
            symphony_phase=3,
            dependencies=[p1.id],
            estimated_eu=1.0,
        )
        p3 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"结果验证与覆盖率报告: {root.intent[:30]}",
            required_capabilities=["validation", "report_generation"],
            symphony_phase=4,
            dependencies=[p2.id],
            estimated_eu=0.3,
        )
        return [p1, p2, p3]

    def _docs_decomposition(self, root: IntentParticle) -> list[IntentParticle]:
        """文档类任务拆解。"""
        p1 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"现有文档审计与结构规划: {root.intent[:30]}",
            required_capabilities=["hifi.read", "theoretical.modeling"],
            symphony_phase=1,
            estimated_eu=0.3,
        )
        p2 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"文档撰写与完善: {root.intent[:30]}",
            required_capabilities=["documentation", "docs.write"],
            symphony_phase=3,
            dependencies=[p1.id],
            estimated_eu=0.8,
        )
        return [p1, p2]

    def _generic_decomposition(self, root: IntentParticle) -> list[IntentParticle]:
        """通用任务拆解 (默认回退)。"""
        p1 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"上下文分析: {root.intent[:30]}",
            required_capabilities=["theoretical.modeling"],
            symphony_phase=1,
            estimated_eu=0.2,
        )
        p2 = IntentParticle(
            parent_id=root.id,
            root_id=root.root_id,
            intent=f"具体执行: {root.intent[:30]}",
            required_capabilities=["heavy-lifting"],
            symphony_phase=3,
            dependencies=[p1.id],
            estimated_eu=1.0,
        )
        return [p1, p2]

    def fail_particle(self, p_id: str, reason: str) -> None:
        """记录粒子失败并尝试触发重试或排泄。

        Args:
            p_id: 粒子 ID。
            reason: 失败原因。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM metabolic_particles WHERE id = ?", (p_id,)).fetchone()

            if not row:
                return

            data = dict(row)
            # 兼容性处理
            if "required_capabilities" not in data and "required_caps" in data:
                data["required_capabilities"] = data.pop("required_caps")

            p = IntentParticle.from_dict(data)
            p.retry_count += 1
            p.failure_reason = reason

            if p.retry_count >= p.max_retries:
                p.stage = MetabolicStage.EXCRETED
                _log.info("💀 [Digestor] 粒子 {p_id} 达到最大重试次数，已排泄。原因: {reason}")
            else:
                p.stage = MetabolicStage.ABSORBED  # 回退到已吸收状态
                _log.info("🔄 [Digestor] 粒子 {p_id} 失败，准备重试 ({p.retry_count}/{p.max_retries})。")

            conn.execute(
                "UPDATE metabolic_particles SET stage = ?, retry_count = ?, failure_reason = ? WHERE id = ?",
                (p.stage.value, p.retry_count, p.failure_reason, p_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _persist_particle(self, p: IntentParticle) -> None:
        """实事求是：每个粒子的诞生必须记录"""
        conn = sqlite3.connect(self.db_path)
        try:
            data = p.to_dict()
            conn.execute(
                """
                INSERT INTO metabolic_particles
                (id, parent_id, root_id, intent, stage, estimated_eu, actual_eu, expected_nectar, required_capabilities, dependencies, retry_count, max_retries, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["id"],
                    data["parent_id"],
                    data["root_id"],
                    data["intent"],
                    data["stage"],
                    data["estimated_eu"],
                    data["actual_eu"],
                    data["expected_nectar"],
                    json.dumps(data["required_capabilities"]),
                    json.dumps(data["dependencies"]),
                    data.get("retry_count", 0),
                    data.get("max_retries", 3),
                    data["birth_time"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _update_particle_stage(self, p_id: str, stage: MetabolicStage) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE metabolic_particles SET stage = ? WHERE id = ?", (stage.value, p_id))
            conn.commit()
        finally:
            conn.close()

    def validate_internal_state(self) -> bool:
        """验证消化器内部状态 (实事求是：检查数据库连接)。

        Returns:
            如果数据库连接正常且可读，则返回 True。
        """
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("SELECT 1 FROM metabolic_particles LIMIT 1")
                return True
            finally:
                conn.close()
        except sqlite3.Error as e:
            _log.error("%s: %s", type(e).__name__, e)
            return False


# 全局单例
Digestor = IntentDigestor()
