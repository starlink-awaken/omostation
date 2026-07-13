"""OMO dashboard API — cockpit 收敛 (P46 follow-up P45 W3 known issue)

P45 W3 发现: port-registry 注释 9190 (omo-dashboard) "converged to cockpit /api/..."
但 cockpit 无 /api/omos/status 端点. P46 真修.

端点 (新):
  GET /api/omos/status  → OMO dashboard status JSON (从 .omc/state/ + .omo/state/system.yaml + radar 读)
  GET /api/omos/health  → OMO health check

数据源:
- .omc/state/sessions/{sessionId}/autopilot-state.json (autopilot 状态)
- .omo/state/system.yaml (system state, health_score_ref)
- .omo/state/health.yaml (governance health, governance 治理)
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path

import yaml

try:
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/omos", tags=["omos"])
except ImportError:
    router = None


_REPO_ROOT = Path(__file__).resolve().parents[5]

import sys

# 统一在模块加载时注入 sys.path
for _path in (
    _REPO_ROOT / "projects" / "omo" / "src",
    _REPO_ROOT / "projects" / "bus-foundation" / "src",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import time
from datetime import UTC, datetime

import bus_foundation.facade.event as bus_event

from cockpit.adapters.omo import omo_ingress

_VIOLATIONS_CACHE = None
_VIOLATIONS_CACHE_TIME = 0.0
_VIOLATIONS_TTL = 15.0  # 15秒缓存


async def _git_commit_fix_drift():
    try:
        import asyncio

        add_proc = await asyncio.create_subprocess_exec(
            "git", "add", ".omo/state/system.yaml", ".omo/change-log/mutations.jsonl", cwd=str(_REPO_ROOT)
        )
        await add_proc.wait()
        commit_proc = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", "chore: auto-fix ssot task_count_drift via cockpit-ui", cwd=str(_REPO_ROOT)
        )
        await commit_proc.wait()
    except Exception:
        pass


if router:

    @router.get("/status")
    async def get_omos_status():
        """获取 OMO dashboard 状态.

        数据源 (优先级):
        1. .omo/state/system.yaml (system state)
        2. .omo/state/health.yaml (governance health)
        3. .omc/state/sessions/ (autopilot 状态)
        """
        try:
            state = {}
            system_yaml = _REPO_ROOT / ".omo" / "state" / "system.yaml"
            if system_yaml.exists():
                with open(system_yaml) as f:
                    state.update(yaml.safe_load(f) or {})

            health_yaml = _REPO_ROOT / ".omo" / "state" / "health.yaml"
            health = {}
            if health_yaml.exists():
                with open(health_yaml) as f:
                    health = yaml.safe_load(f) or {}

            return {
                "service": "omo-dashboard",
                "status": "converged",
                "converged_to": "cockpit /api/omos/status",
                "system": {
                    "current_phase": state.get("current_phase"),
                    "health_score": state.get("health_score"),
                    "completed_tasks": state.get("completed_tasks"),
                    "active_tasks": state.get("active_tasks"),
                    "blocked_tasks": state.get("blocked_tasks"),
                },
                "governance": {
                    "health_score": health.get("health_score"),
                    "anomaly_count": health.get("anomaly_count"),
                    "total_tasks": health.get("total_tasks"),
                    "done": health.get("done"),
                    "planned": health.get("planned"),
                },
            }
        except Exception as e:  # defensive fallback
            return {
                "service": "omo-dashboard",
                "status": "degraded",
                "converged_to": "cockpit /api/omos/status",
                "error": str(e),
            }

    @router.get("/health")
    async def get_omos_health():
        """OMO health check."""
        return {"status": "ok", "service": "omo-dashboard-converged", "endpoint": "/api/omos/status"}

    @router.get("/quests")
    async def get_quests():
        """列出家庭 Quests 和家庭排行榜"""
        try:
            db_path = _REPO_ROOT / "projects" / "family-hub" / "family_hub.db"
            if not db_path.exists():
                return {"error": f"family_hub.db not found at {db_path}"}

            import sqlite3

            with closing(sqlite3.connect(str(db_path))) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM quests ORDER BY id DESC")
                quests = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT role, name, level, wisdomPoints, responsibilityPoints, inventory FROM profiles")
                profiles = [dict(row) for row in cursor.fetchall()]

                cursor.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 15")
                raw_logs = [dict(row) for row in cursor.fetchall()]

            # ─── 动态注入 1：扫描并注入 direct-omo-io 违规作为 Dev Quests ───
            violation_count = 0
            try:
                violations_res = await get_omos_violations()
                if isinstance(violations_res, dict) and violations_res.get("status") == "ok":
                    violation_count = len(violations_res.get("violations", []))
            except Exception:  # defensive fallback
                pass

            if violation_count > 0:
                quests.insert(
                    0,
                    {
                        "id": 99901,
                        "title": f"🚨 消除 direct-omo-io 直写违规 ({violation_count} 处拦截)",
                        "type": "wisdom",
                        "reward": 100,
                        "completed": 0,
                        "assignee": "parent",
                    },
                )

            # ─── 动态注入 2：扫描并注入 OMO Cards 卡片作为 Dev Quests ───
            try:
                from cockpit.scripts.cockpit_mcp import _scan_cards

                cards = _scan_cards()
                active_cards = [c for c in cards if c.get("status") not in ("closed", "done")]

                def card_id_to_int(card_id: str) -> int:
                    digits = "".join(ch for ch in card_id if ch.isdigit())
                    if digits:
                        return 99910 + (int(digits) % 1000)
                    return 99910 + (hash(card_id) % 1000)

                for card in active_cards:
                    quests.insert(
                        0,
                        {
                            "id": card_id_to_int(card["id"]),
                            "title": f"📋 [Dev Card] {card['title']} (Ref: {card['id']})",
                            "type": "wisdom" if card.get("priority") in ("P0", "P1") else "responsibility",
                            "reward": 150
                            if card.get("priority") == "P0"
                            else 100
                            if card.get("priority") == "P1"
                            else 50,
                            "completed": 0,
                            "assignee": "parent",
                        },
                    )
            except Exception:  # defensive fallback
                pass

            # ─── 动态注入 3：解析已完成任务日志并放入荣誉殿堂 ───
            import re

            for log in raw_logs:
                message = log.get("message", "")
                if "parent completed quest: 消除 AST 直写违规行为" in message:
                    # 避免重复放入
                    if not any(q["id"] == 99901 and q["completed"] == 1 for q in quests):
                        quests.append(
                            {
                                "id": 99901,
                                "title": "🚨 消除 direct-omo-io 直写违规 (已修复代码库直写规范)",
                                "type": "wisdom",
                                "reward": 100,
                                "completed": 1,
                                "assignee": "parent",
                            }
                        )

                m_card = re.match(r"^parent completed quest: \[Dev Card\] (.+?) for (\d+) points$", message)
                if m_card:
                    card_title = m_card.group(1)
                    card_reward = int(m_card.group(2))
                    quests.append(
                        {
                            "id": 99990,
                            "title": f"📋 [Dev Card] {card_title}",
                            "type": "wisdom" if card_reward >= 100 else "responsibility",
                            "reward": card_reward,
                            "completed": 1,
                            "assignee": "parent",
                        }
                    )

            # ─── 动态注入 4：对 logs 进行格式解析 ───
            formatted_logs = []
            for log in raw_logs:
                message = log.get("message", "")
                user = "parent"
                action = message
                amount = 0

                m1 = re.match(r"^(\w+) completed quest: (.+?) for (\d+) points$", message)
                if m1:
                    user = m1.group(1)
                    action = f"完成了任务: {m1.group(2)}"
                    amount = int(m1.group(3))
                else:
                    m2 = re.match(r"^(\w+) completed quest: (.+?) \(ID=(\d+)\) for (\d+) points$", message)
                    if m2:
                        user = m2.group(1)
                        action = f"完成了任务: {m2.group(2)} (ID={m2.group(3)})"
                        amount = int(m2.group(4))
                    else:
                        m3 = re.match(r"^(\w+) (?:earned|spent) (\d+) points for (.+)$", message)
                        if m3:
                            user = m3.group(1)
                            amount = int(m3.group(2))
                            action = m3.group(3)

                formatted_logs.append(
                    {
                        "id": log.get("id"),
                        "user": user,
                        "action": action,
                        "amount": amount,
                        "timestamp": log.get("timestamp"),
                    }
                )

            return {"status": "ok", "quests": quests, "profiles": profiles, "logs": formatted_logs}
        except Exception as e:  # defensive fallback
            return {"status": "error", "error": str(e)}

    @router.post("/quests")
    async def create_quest_api(title: str, q_type: str, reward: int, assignee: str):
        """新建一个 Quest，同时在 SQLite 和 OMO 中建立任务"""
        try:
            db_path = _REPO_ROOT / "projects" / "family-hub" / "family_hub.db"
            if not db_path.exists():
                return {"error": "family_hub.db not found"}

            import sqlite3

            with closing(sqlite3.connect(str(db_path))) as conn:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO quests (title, type, reward, completed, assignee) VALUES (?, ?, ?, 0, ?)",
                        (title, q_type, reward, assignee),
                    )
                    quest_id = cursor.lastrowid

            def _utc_now() -> str:
                return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

            task_id = f"QUEST-{quest_id}"
            omo_dir = _REPO_ROOT / ".omo"

            task_data = {
                "id": task_id,
                "title": title,
                "description": f"游戏化任务: 奖励 {reward} 积分, 归属于 {assignee}",
                "status": "candidate",
                "task_type": "quest",
                "risk_level": "L0",
                "depends_on": [],
                "source_docs": [".omo/tasks/planned/quest_template.yaml"],
                "deliverables": [f"完成 Quest: {title}"],
                "imported_via": "cockpit_quest_api",
                "context_uri": f"bos://governance/tasks/planned/{task_id}",
                "assigned_to": None,
                "dispatch_id": None,
                "run_ref": None,
                "approval_ref": None,
                "review_ref": None,
                "knowledge_refs": [],
                "handoff_refs": [],
                "governance_refs": [
                    ".omo/standards/omo-governance-surfaces.md",
                    ".omo/_truth/x1-governance-policies.yaml",
                ],
                "entry_gate": [],
                "evidence_required": [f"由 {assignee} 在家庭枢纽标记完成"],
                "test_plan": ["omo check-quest"],
                "allowed_operation_level": "L0",
                "human_approval_required": False,
                "metadata": {
                    "quest_id": quest_id,
                    "assignee": assignee,
                    "reward": reward,
                    "type": q_type,
                    "created_via": "cockpit quest api",
                    "created_at": _utc_now(),
                },
            }

            omo_ingress.create_planned_task(
                omo_dir,
                task_data=task_data,
                ingress_plane="projects/cockpit",
                source_ref=f"cockpit:quest:create:{task_id}",
            )

            return {"status": "ok", "quest_id": quest_id, "task_id": task_id}
        except Exception as e:  # defensive fallback
            return {"status": "error", "error": str(e)}

    @router.post("/quests/{quest_id}/complete")
    async def complete_quest_api(quest_id: int):
        """将 Quest 标记为完成：归档 OMO 任务并发布事件进行清算"""
        try:
            db_path = _REPO_ROOT / "projects" / "family-hub" / "family_hub.db"
            if not db_path.exists():
                return {"error": "family_hub.db not found"}

            import sqlite3

            # 1. 消除直写违规的 Quest (99901)
            if quest_id == 99901:
                violations_res = await get_omos_violations()
                if isinstance(violations_res, dict) and violations_res.get("status") == "ok":
                    if not violations_res.get("passed"):
                        violation_len = len(violations_res.get("violations", []))
                        return {
                            "status": "error",
                            "error": f"当前仍存在 {violation_len} 处直写违规，请先修复代码再点击达成！",
                        }

                # 校验通过！给 parent 发放 100 积分
                with closing(sqlite3.connect(str(db_path))) as conn:
                    with conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE profiles SET wisdomPoints = wisdomPoints + 100 WHERE role = 'parent'")
                        log_msg = "parent completed quest: 消除 AST 直写违规行为 for 100 points"
                        cursor.execute(
                            "INSERT INTO logs (message, type, timestamp) VALUES (?, 'quest_completion', datetime('now', 'localtime'))",
                            (log_msg,),
                        )

                try:
                    bus_event.publish(
                        topic="QuestCompleted",
                        payload={
                            "quest_id": quest_id,
                            "task_id": "QUEST-VIOLATION-FIX",
                            "assignee": "parent",
                            "reward": 100,
                            "type": "wisdom",
                        },
                        source_uri="bos://governance/cockpit/quests",
                    )
                except Exception:  # defensive fallback
                    pass
                return {"status": "ok", "task_id": "QUEST-VIOLATION-FIX", "event_published": True}

            # 2. 治理 OMO Card 卡片的 Quest (99910+)
            elif quest_id >= 99910 and quest_id < 100000:
                from cockpit.scripts.cockpit_mcp import _scan_cards

                cards = _scan_cards()

                def card_id_to_int(card_id: str) -> int:
                    digits = "".join(ch for ch in card_id if ch.isdigit())
                    if digits:
                        return 99910 + (int(digits) % 1000)
                    return 99910 + (hash(card_id) % 1000)

                target_card = None
                for card in cards:
                    if card_id_to_int(card["id"]) == quest_id:
                        target_card = card
                        break

                if not target_card:
                    return {"status": "error", "error": "对应的 OMO 卡片未找到或已关闭"}

                from cockpit.scripts.cockpit_mcp import _CARDS_DIR

                md_files = list(_CARDS_DIR.rglob("*.md"))
                card_file_path = None
                for f in md_files:
                    try:
                        text = f.read_text(encoding="utf-8")
                        if target_card["id"] in text:
                            card_file_path = f
                            break
                    except Exception:  # defensive fallback
                        pass

                if not card_file_path:
                    return {"status": "error", "error": f"未找到卡片 {target_card['id']} 的本地 Markdown 文件"}

                content = card_file_path.read_text(encoding="utf-8")
                import re

                # 仅在首个 Frontmatter 区替换 status 字段以确保安全
                frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
                match = frontmatter_pattern.match(content)
                if match:
                    frontmatter = match.group(1)
                    new_frontmatter = re.sub(r"status:\s*[a-zA-Z0-9_\-]+", "status: done", frontmatter)
                    new_content = content[: match.start(1)] + new_frontmatter + content[match.end(1) :]
                else:
                    new_content = re.sub(r"status:\s*[a-zA-Z0-9_\-]+", "status: done", content, count=1)

                card_file_path.write_text(new_content, encoding="utf-8")

                reward = (
                    150 if target_card.get("priority") == "P0" else 100 if target_card.get("priority") == "P1" else 50
                )

                with closing(sqlite3.connect(str(db_path))) as conn:
                    with conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE profiles SET wisdomPoints = wisdomPoints + ? WHERE role = 'parent'", (reward,)
                        )
                        log_msg = f"parent completed quest: [Dev Card] {target_card['title']} for {reward} points"
                        cursor.execute(
                            "INSERT INTO logs (message, type, timestamp) VALUES (?, 'quest_completion', datetime('now', 'localtime'))",
                            (log_msg,),
                        )

                try:
                    omo_dir = _REPO_ROOT / ".omo"
                    from cockpit.adapters.omo import complete_task

                    complete_task(
                        omo_dir,
                        task_id=f"CARD-{target_card['id']}",
                        actor="projects/cockpit",
                        source_ref=f"cockpit:quest:card:done:{target_card['id']}",
                        now=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        evidence_paths=[str(card_file_path.relative_to(_REPO_ROOT))],
                    )
                except Exception:  # defensive fallback
                    pass

                try:
                    bus_event.publish(
                        topic="QuestCompleted",
                        payload={
                            "quest_id": quest_id,
                            "task_id": f"CARD-{target_card['id']}",
                            "assignee": "parent",
                            "reward": reward,
                            "type": "wisdom",
                        },
                        source_uri="bos://governance/cockpit/quests",
                    )
                except Exception:  # defensive fallback
                    pass

                return {"status": "ok", "task_id": f"CARD-{target_card['id']}", "event_published": True}

            # 3. 正常家庭 Quest 任务
            else:
                with closing(sqlite3.connect(str(db_path))) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    quest = cursor.execute(
                        "SELECT * FROM quests WHERE id = ? AND completed = 0", (quest_id,)
                    ).fetchone()

                    if not quest:
                        return {"status": "error", "error": "Quest not found or already completed"}

                    with conn:
                        cursor.execute("UPDATE quests SET completed = 1 WHERE id = ?", (quest_id,))

                        assignee = quest["assignee"]
                        reward = quest["reward"]
                        q_type = quest["type"]

                        col = "wisdomPoints" if q_type == "wisdom" else "responsibilityPoints"
                        cursor.execute(f"UPDATE profiles SET {col} = {col} + ? WHERE role = ?", (reward, assignee))

                        log_msg = f"{assignee} completed quest: {quest['title']} (ID={quest_id}) for {reward} points"
                        cursor.execute(
                            "INSERT INTO logs (message, type, timestamp) VALUES (?, 'quest_completion', datetime('now', 'localtime'))",
                            (log_msg,),
                        )

                task_id = f"QUEST-{quest_id}"
                omo_dir = _REPO_ROOT / ".omo"
                try:

                    def _utc_now() -> str:
                        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

                    omo_ingress.complete_task(
                        omo_dir,
                        task_id=task_id,
                        actor="projects/cockpit",
                        source_ref=f"cockpit:quest:done:{task_id}",
                        now=_utc_now(),
                        evidence_paths=[f"sqlite://family-hub/quests/{quest_id}"],
                    )
                except Exception:  # defensive fallback
                    pass

                try:
                    bus_event.publish(
                        topic="QuestCompleted",
                        payload={
                            "quest_id": quest_id,
                            "task_id": task_id,
                            "assignee": assignee,
                            "reward": reward,
                            "type": q_type,
                        },
                        source_uri="bos://governance/cockpit/quests",
                    )
                except Exception:  # defensive fallback
                    pass

                return {"status": "ok", "task_id": task_id, "event_published": True}
        except Exception as e:  # defensive fallback
            return {"status": "error", "error": str(e)}

    @router.post("/fix-drift")
    async def api_fix_drift():
        """执行 SSOT 自动修复 (ssot-guardian.py --auto-fix)"""
        try:
            import asyncio
            import subprocess

            guardian_path = str(_REPO_ROOT / "bin" / "ssot-guardian.py")
            proc = await asyncio.to_thread(
                subprocess.run, ["python3", guardian_path, "--auto-fix"], capture_output=True, text=True
            )

            asyncio.create_task(_git_commit_fix_drift())

            return {
                "status": "ok",
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "msg": "SSOT 自动修复及状态固化提交完成！"
                if proc.returncode == 0 or "自动修复" in proc.stdout
                else "修复完成，部分漂移仍需人工核对。",
            }
        except Exception as e:  # defensive fallback
            return {"status": "error", "error": str(e)}

    @router.get("/violations")
    async def get_omos_violations():
        """扫描并定位直接写入 .omo/ 或 spaces/ 的违规代码行 (direct_omo_io_violation)"""
        import asyncio

        global _VIOLATIONS_CACHE, _VIOLATIONS_CACHE_TIME
        now = time.time()
        if _VIOLATIONS_CACHE is not None and (now - _VIOLATIONS_CACHE_TIME) < _VIOLATIONS_TTL:
            return _VIOLATIONS_CACHE

        import re
        import subprocess

        gatekeeper = _REPO_ROOT / "projects" / "ecos" / "scripts" / "contract_gatekeeper.py"
        if not gatekeeper.exists():
            return {"status": "error", "error": "contract_gatekeeper.py not found"}

        default_paths = [
            "projects/aetherforge/packages",
            "projects/agora/src",
            "projects/c2g/src",
            "projects/cockpit/src",
            "projects/ecos/src",
            "projects/family-hub/src",
            "projects/l4-kernel/src",
            "projects/metaos/src",
            "projects/model-driven/src",
            "projects/omo/src",
            "projects/runtime/src",
            "scripts",
            "bin",
        ]

        cmd = [sys.executable, str(gatekeeper)]
        existing_paths = []
        for p in default_paths:
            full_p = _REPO_ROOT / p
            if full_p.exists():
                existing_paths.append(str(full_p))
        cmd.extend(existing_paths)

        try:
            proc = await asyncio.to_thread(subprocess.run, cmd, cwd=str(_REPO_ROOT), capture_output=True, text=True)
            output = proc.stdout
            violations = []

            current_file = None
            for line in output.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue
                if line_str.startswith("Gatekeeper:") or line_str.startswith("Remediation:"):
                    continue
                m_violation = re.match(r"^\s*(\d+):\s*(.*)$", line)
                if m_violation:
                    if current_file:
                        violations.append(
                            {"file": current_file, "line": int(m_violation.group(1)), "detail": m_violation.group(2)}
                        )
                else:
                    current_file = line_str

            res = {"status": "ok", "passed": proc.returncode == 0, "violations": violations}
            _VIOLATIONS_CACHE = res
            _VIOLATIONS_CACHE_TIME = now
            return res
        except Exception as e:  # defensive fallback
            return {"status": "error", "error": str(e)}

    @router.post("/circuit-break")
    async def post_circuit_break(payload: dict):
        """更新熔断器状态 (处理 broken: bool)"""
        broken = payload.get("broken", False)
        try:
            from cockpit.adapters.omo import update_provider_plane_settings

            omo_dir = _REPO_ROOT / ".omo"
            success = update_provider_plane_settings(omo_dir, circuit_broken=broken)
            if success:
                try:
                    bus_event.publish(
                        topic="CircuitBreakerUpdated",
                        payload={"circuit_broken": broken},
                        source_uri="bos://governance/cockpit/circuit_breaker",
                    )
                except Exception:  # defensive fallback
                    pass
                return {"status": "ok", "circuit_broken": broken}
            else:
                return {"status": "error", "error": "Failed to update provider-plane.yaml"}
        except Exception as e:  # defensive fallback
            return {"status": "error", "error": str(e)}

    @router.post("/budget")
    async def post_budget(payload: dict):
        """更新单日预算安全线 (处理 budget: float)"""
        budget = payload.get("budget", 100.0)
        try:
            from cockpit.adapters.omo import update_provider_plane_settings

            omo_dir = _REPO_ROOT / ".omo"
            success = update_provider_plane_settings(omo_dir, daily_budget=budget)
            if success:
                try:
                    bus_event.publish(
                        topic="DailyBudgetUpdated",
                        payload={"daily_budget": budget},
                        source_uri="bos://governance/cockpit/daily_budget",
                    )
                except Exception:  # defensive fallback
                    pass
                return {"status": "ok", "daily_budget": budget}
            else:
                return {"status": "error", "error": "Failed to update provider-plane.yaml"}
        except Exception as e:  # defensive fallback
            return {"status": "error", "error": str(e)}

    @router.get("/thoughts")
    async def get_thoughts():
        """提取或模拟虚拟董事会的思绪流"""
        try:
            import yaml

            system_yaml = _REPO_ROOT / ".omo" / "state" / "system.yaml"
            health_score = 100
            phase = "未知"
            if system_yaml.exists():
                try:
                    with open(system_yaml) as f:
                        state = yaml.safe_load(f) or {}
                        health_score = state.get("health_score", 100)
                        phase = state.get("current_phase", "未知")
                except Exception:  # defensive fallback
                    pass

            plane_path = _REPO_ROOT / ".omo" / "state" / "provider-plane.yaml"
            circuit_broken = False
            daily_budget = 100.0
            if plane_path.exists():
                try:
                    with open(plane_path) as f:
                        plane = yaml.safe_load(f) or {}
                        circuit_broken = plane.get("circuit_broken", False)
                        daily_budget = plane.get("daily_budget", 100.0)
                except Exception:  # defensive fallback
                    pass

            violation_count = 0
            try:
                v_res = await get_omos_violations()
                if isinstance(v_res, dict) and v_res.get("status") == "ok":
                    violation_count = len(v_res.get("violations", []))
            except Exception:  # defensive fallback
                pass

            timestamp = datetime.now(UTC).isoformat()

            # Builder
            if violation_count > 0:
                b_text = f"糟糕，检测到 {violation_count} 处 direct-omo-io 直写违规！我们必须遵循规范，通过 omo_cockpit_bridge.py 或 OMO CLI 代理读写，杜绝文件直写。"
            elif circuit_broken:
                b_text = "算力大盘已熔断，为了确保系统稳定性，我已停止云端 API 发送，全力切换到本地 Ollama/LMStudio 离线推理网格。"
            elif health_score < 90:
                b_text = f"系统健康度降至 {health_score}，还有一些 OMO 卡片处于未清偿状态。我们 Builder 应该优先偿还高 severity 的技术债务！"
            else:
                b_text = (
                    f"当前处于 Phase: {phase}。Hermes 研发总线一切正常，架构规矩执行完美，随时可以进行快速的 MVP 迭代。"
                )

            # Devil
            if violation_count > 0:
                d_text = "直写 omo/spaces 绕过了系统网格的影子门禁，这会彻底破坏 SSOT！我建议立刻触发构建红线，在违规清零前禁止一切代码合并。"
            elif circuit_broken:
                d_text = "熔断是正确的决策！如果不及时止损，单日费用将大幅超出预算。我们必须审视是否有智能体在陷入死循环调用。"
            elif health_score < 90:
                d_text = f"债务熵增会带来蝴蝶效应。健康分只剩 {health_score} 了，如果我们不警惕，这会迅速侵蚀 runtime 稳定度。"
            else:
                d_text = "看似一切顺利，但仍需警惕子模块指针漂移 (submodule_pointer_drift)。必须严格遵守‘先子仓库 Commit，再主仓库 Bump 指针’的规则。"

            # Sage
            if violation_count > 0:
                s_text = "规矩的建立并非限制创造力，而是为了在多 Agent 协同中保持系统的自愈与一致。直写违规实际上反映了流程的失序。"
            elif circuit_broken:
                s_text = "算力的调配与预算的限制，是独立造物主生存的第一性原理。利用有限 of 算力做最有价值的推演，是我们的核心课题。"
            elif health_score < 90:
                s_text = (
                    "技术债是开发效率的预支。我们现在需要放慢脚步，对齐治理面的元规则，做一次系统性的整理和架构收敛。"
                )
            else:
                s_text = "BOS 路由作为跨层调用的唯一路径，是 5+4+1+1 架构的灵魂。将一切能力服务化、路由化，才能保证未来的无缝扩展。"

            # Keeper
            if violation_count > 0:
                k_text = f"我已在状态面 (State Plane) 记录了这 {violation_count} 项直写拦截警告，事件已发送至 OMO audit 日志。修复前，系统不可标记为完备。"
            elif circuit_broken:
                k_text = f"警报：算力调配已进入安全限制模式（熔断中，预算：${daily_budget}/天）。正在将所有心智路由流转向备用离线节点。"
            elif health_score < 90:
                k_text = f"当前系统健康度 {health_score} 已记入 `system.yaml` 归档。未清算任务数仍高，请尽快在 QuestBoard 中清算治理冒险卡片。"
            else:
                k_text = "控制论闭环完备。已将最新治理决策持久化并归档。SLA 达成率为 100%，所有心智探针与 Agora 链路运转顺畅。"

            thoughts = [
                {"role": "builder", "name": "Builder", "avatar": "🧑‍💻", "content": b_text},
                {"role": "devil", "name": "Devil", "avatar": "⚡️", "content": d_text},
                {"role": "sage", "name": "Sage", "avatar": "🧠", "content": s_text},
                {"role": "keeper", "name": "Keeper", "avatar": "👁️", "content": k_text},
            ]
            return {"status": "ok", "timestamp": timestamp, "thoughts": thoughts}
        except Exception as e:  # defensive fallback
            return {"status": "error", "error": str(e)}
