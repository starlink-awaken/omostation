"""BET-Y1Q3-T6-03: mof-deepen 模块最小测试面.

验证10个模块的可加载性与核心函数可调用性.
不测试具体逻辑, 仅验证模块存在且入口函数可导入.

对应模块:
  - admin_scenes.py: ADMIN_SCENES dispatcher 注册
  - deadline_tracker.py: 任务截止追踪
  - doc_generator.py: 公文模板生成
  - health_agent.py: 健康域扫描
  - mail_agent.py: 邮件分类
  - mail_daemon.py: 邮件守护进程
  - mail_reader.py: 邮件读取
  - mail_sender.py: 邮件草稿生成
  - scene-reflection.py: 场景反思
  - scene-outcome-recorder.py: 场景结果记录
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# worktree 根目录 (测试文件在 tests/, 向上1级即 worktree root)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "ssot"))


def _load(mod_name: str, path: Path):
    """加载带连字符的Python模块 (参考 test_signal_poller.py)."""
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_admin_scenes_import_and_dispatcher():
    """admin_scenes.py: 可加载 + ADMIN_SCENES dispatcher 存在."""
    mod = _load("admin_scenes", ROOT / "bin" / "ssot" / "admin_scenes.py")
    assert hasattr(mod, "ADMIN_SCENES"), "ADMIN_SCENES dispatcher 必须存在"
    assert isinstance(mod.ADMIN_SCENES, dict), "ADMIN_SCENES 应为 dict"
    assert "admin-inbox" in mod.ADMIN_SCENES, "admin-inbox 场景必须注册"


def test_deadline_tracker_import_and_functions():
    """deadline_tracker.py: 可加载 + 核心函数可调用."""
    mod = _load("deadline_tracker", ROOT / "bin" / "ssot" / "deadline_tracker.py")
    assert hasattr(mod, "register_task"), "register_task 函数必须存在"
    assert hasattr(mod, "load_tasks"), "load_tasks 函数必须存在"
    assert callable(mod.register_task), "register_task 应可调用"
    assert callable(mod.load_tasks), "load_tasks 应可调用"


def test_doc_generator_import_and_functions():
    """doc_generator.py: 可加载 + 核心函数可调用."""
    mod = _load("doc_generator", ROOT / "bin" / "ssot" / "doc_generator.py")
    assert hasattr(mod, "generate_doc"), "generate_doc 函数必须存在"
    assert hasattr(mod, "save_draft"), "save_draft 函数必须存在"
    assert callable(mod.generate_doc), "generate_doc 应可调用"
    assert callable(mod.save_draft), "save_draft 应可调用"


def test_health_agent_import_and_scan():
    """health_agent.py: 可加载 + 扫描函数可调用."""
    mod = _load("health_agent", ROOT / "bin" / "ssot" / "health_agent.py")
    assert hasattr(mod, "scan_health_reports"), "scan_health_reports 函数必须存在"
    assert callable(mod.scan_health_reports), "scan_health_reports 应可调用"


def test_mail_agent_import_and_classify():
    """mail_agent.py: 可加载 + 分类函数可调用."""
    mod = _load("mail_agent", ROOT / "bin" / "ssot" / "mail_agent.py")
    assert hasattr(mod, "classify_mail"), "classify_mail 函数必须存在"
    assert callable(mod.classify_mail), "classify_mail 应可调用"


def test_mail_daemon_import_and_cycle():
    """mail_daemon.py: 可加载 + run_cycle 函数可调用."""
    mod = _load("mail_daemon", ROOT / "bin" / "ssot" / "mail_daemon.py")
    assert hasattr(mod, "run_cycle"), "run_cycle 函数必须存在"
    assert callable(mod.run_cycle), "run_cycle 应可调用"


def test_mail_reader_import_and_read():
    """mail_reader.py: 可加载 + 读取函数可调用."""
    mod = _load("mail_reader", ROOT / "bin" / "ssot" / "mail_reader.py")
    assert hasattr(mod, "read_netease_mail"), "read_netease_mail 函数必须存在"
    assert hasattr(mod, "read_all"), "read_all 函数必须存在"
    assert callable(mod.read_netease_mail), "read_netease_mail 应可调用"
    assert callable(mod.read_all), "read_all 应可调用"


def test_mail_sender_import_and_create():
    """mail_sender.py: 可加载 + create_draft 函数可调用."""
    mod = _load("mail_sender", ROOT / "bin" / "ssot" / "mail_sender.py")
    assert hasattr(mod, "create_draft"), "create_draft 函数必须存在"
    assert callable(mod.create_draft), "create_draft 应可调用"


def test_scene_reflection_import_and_generate():
    """scene-reflection.py: 可加载 + generate_reflection 函数可调用."""
    mod = _load("scene_reflection", ROOT / "bin" / "ssot" / "scene-reflection.py")
    assert hasattr(mod, "generate_reflection"), "generate_reflection 函数必须存在"
    assert callable(mod.generate_reflection), "generate_reflection 应可调用"


def test_scene_outcome_recorder_import_and_record():
    """scene-outcome-recorder.py: 可加载 + record_outcome 函数可调用."""
    mod = _load("scene_outcome_recorder", ROOT / "bin" / "ssot" / "scene-outcome-recorder.py")
    assert hasattr(mod, "record_outcome"), "record_outcome 函数必须存在"
    assert callable(mod.record_outcome), "record_outcome 应可调用"
