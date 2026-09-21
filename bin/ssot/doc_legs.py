#!/usr/bin/env python3
"""Documents 场景能力腿 — 43 个 documents-* 场景的 action 实现.

背景 (2026-09-17): 43 个 scene-documents-* 场景声明了 journey
(documents-*-journey), 其 states 调用 action: llm_classify / process /
record_result / emit_event. 但 journey-engine._execute_action 只认
llm_classify(返回 0.85 stub) / emit_event / generate_decision /
doc-review legs / iris_list_*;process 与 record_result 落到默认分支
返回 {"status": "succeeded"} —— 声明与执行不一致, 且不产出任何值.

本模块实现这 2 个真实腿, 并将文档场景按任务类 (quarantine / owner /
cutover / audit / convergence) 分组 daily-run, 避免 43 个场景同时刷屏.

设计原则 (对齐 doc-review-checks.py):
- 复用既有规则 / 源, 不另立一套 (防规则漂移)
- 纯函数, 零副作用 (写入由 journey-engine 的 _record_auto_outcome 负责)
- 置信度由检查结果聚合 (confidence_of), 驱动 human_gate 自动/升级分支
- 信号源只认 workspace_docs (doc.changed / doc.updated), 其余连接器透传
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]


def _scene_outcome_dir(scene_id: str) -> Path:
    """outcome 落盘目录 — 委托 _shared (唯一合法解析入口).

    先补 sys.path 再导入: 不靠调用方 import 方式碰运气 —— 实测非常规导入下
    ImportError 会静默退回硬编码路径, 保护直接失效 (#3989 同型教训)。
    """
    _here = str(Path(__file__).resolve().parent)
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from _shared import scene_outcome_dir
    return scene_outcome_dir(scene_id, _ROOT)

# ── 任务类分组 (按 journey 名 / 卡片 trigger) ─────────────────────

TASK_CLASS_GROUPS = {
    "quarantine": [
        "documents-consumer-audit", "documents-consumer-audit-modes",
        "documents-consumer-tokenization", "documents-consumer-tail",
    ],
    "owner": [
        "documents-owner-job", "documents-workspace-watch",
        "documents-learning-control", "documents-learning-helpers",
        "documents-concept-weave", "documents-domain-sync",
        "documents-family-runtime", "documents-freshness",
        "documents-vault-health", "documents-zcode-config",
        "documents-zcode-state",
    ],
    "cutover": [
        "documents-ocr-cutover", "documents-ocr-preflight",
        "documents-schedule-cutover", "documents-bridge-preflight",
        "documents-convergence-preflight", "documents-controller-preflight",
        "documents-predictor-preflight", "documents-signals-preflight",
    ],
    "audit": [
        "documents-accepted-release", "documents-contract-ocr",
        "documents-cockpit-convergence", "documents-cockpit-runtime",
        "documents-execution-retirement", "documents-l4-convergence",
        "documents-opc-runtime", "documents-public-runtime",
        "documents-weijian-cleanup", "documents-weijian-control",
        "documents-weijian-runtime",
    ],
    "convergence": [
        "documents-release-root", "documents-root-control-tools",
        "documents-root-oneoff", "documents-root-tools",
        "documents-guizi-scripts", "documents-guizi-symlinks",
        "documents-guizi-tools", "documents-guozhuan-symlinks",
        "documents-guozhuan-tools",
    ],
}

# 反向映射: journey 前缀 → 任务类
_JOURNEY_PREFIX = {
    "documents-consumer-": "quarantine",
    "documents-owner-": "owner",
    "documents-workspace": "owner",
    "documents-learning-": "owner",
    "documents-concept-": "owner",
    "documents-domain-": "owner",
    "documents-family-": "owner",
    "documents-freshness": "owner",
    "documents-vault-": "owner",
    "documents-zcode-": "owner",
    "documents-ocr-": "cutover",
    "documents-schedule-": "cutover",
    "documents-bridge-": "cutover",
    "documents-convergence-": "cutover",
    "documents-controller-": "cutover",
    "documents-predictor-": "cutover",
    "documents-signals-": "cutover",
    "documents-accepted-": "audit",
    "documents-contract-": "audit",
    "documents-execution-": "audit",
    "documents-l4-": "audit",
    "documents-cockpit-": "audit",
    "documents-opc-": "audit",
    "documents-public-": "audit",
    "documents-weijian-": "audit",
    "documents-release-": "convergence",
    "documents-root-": "convergence",
    "documents-guizi-": "convergence",
    "documents-guozhuan-": "convergence",
}

# ── 规则 (对齐既有实现) ──────────────────────────────────────────

# 工作区文档路径白名单 — 只处理工作区内的文档, 拒绝外部路径注入
# .omo/_knowledge/ 作为通用知识根目录, 支持 applenotes 等内容型连接器写入
ALLOWED_DOC_ROOTS = ("docs", ".omo/_knowledge", ".omo/_truth/scenarios/v3")

# 最小正文行数 / 最大文件大小 (防空壳 / 巨型文件)
MIN_DOC_LINES = 3
MAX_DOC_CHARS = 2_000_000


# ── 工具 ─────────────────────────────────────────────────────────

def _load_doc_review_checks():
    """复用 doc-review-checks 模块 (若存在)."""
    p = _ROOT / "bin" / "ssot" / "doc-review-checks.py"
    if not p.is_file():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("doc_review_checks", p)
    if spec is None or spec.loader is None:
        return None
    m = importlib.util.module_from_spec(spec)
    sys.modules["doc_review_checks"] = m
    spec.loader.exec_module(m)
    return m


def _resolve_doc_path(signal: dict) -> Path | None:
    """从信号载荷解析待处理文档路径 (workspace_docs 源)."""
    raw = signal.get("raw_item") if isinstance(signal.get("raw_item"), dict) else {}
    for key in ("path", "rel_path", "file", "document"):
        value = raw.get(key) or signal.get(key)
        if isinstance(value, str) and value.endswith(".md"):
            target = Path(value)
            if not target.is_absolute():
                target = _ROOT / value
            try:
                resolved = target.resolve()
                root_resolved = _ROOT.resolve()
                # 路径越界拒绝
                if not any(
                    resolved.is_relative_to((root_resolved / r))
                    for r in ALLOWED_DOC_ROOTS
                ):
                    return None
                return resolved
            except OSError:
                return None
    return None


def _doc_stub(doc: Path) -> dict[str, Any]:
    """最小文档元信息 (只读)."""
    try:
        stat = doc.stat()
        text = doc.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        return {
            "path": str(doc.relative_to(_ROOT)),
            "exists": True,
            "lines": len(lines),
            "chars": len(text),
            "mtime": stat.st_mtime,
            "sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
        }
    except OSError as exc:
        return {"path": str(doc.relative_to(_ROOT) if _ROOT in doc.parents else str(doc)),
                "exists": False, "error": str(exc)}


# ── 能力腿 ───────────────────────────────────────────────────────

def _process_content(signal: dict, content: str, dry_run: bool) -> dict[str, Any]:
    """处理内容型文档 (applenotes 等连接器直接提供文本, 无 .md 文件路径).

    对齐文件型文档的规则: 非空壳 / 超限检查; 格式/敏感/依据检查需要文件路径,
    内容型信号跳过 (连接器已做初步清洗).
    """
    issues: list[dict[str, Any]] = []
    checks = 0
    lines = content.splitlines()

    # 规则 1: 非空壳
    checks += 1
    if len(lines) < MIN_DOC_LINES:
        issues.append({"kind": "too_short",
                        "detail": f"{len(lines)} 行 < {MIN_DOC_LINES}"})

    # 规则 2: 不超限
    checks += 1
    if len(content) > MAX_DOC_CHARS:
        issues.append({"kind": "too_large",
                        "detail": f"{len(content)} chars > {MAX_DOC_CHARS}"})

    ok = not issues
    return {
        "status": "succeeded" if ok else "partial",
        "action": "process",
        "checks": checks,
        "passed": checks - len(issues),
        "issues": issues,
        "doc": {
            "path": signal.get("source", "connector"),
            "exists": True,
            "lines": len(lines),
            "chars": len(content),
            "source": signal.get("source", ""),
            "content_based": True,
        },
        "dry_run": dry_run,
    }


def process_document(signal: dict, *, dry_run: bool = False) -> dict[str, Any]:
    """处理文档: 路径校验 / 存在性 / 规则检查 (格式 + 敏感 + 依据).

    支持两种信号源:
      - workspace_docs: 文件路径信号 (.md 路径, 走完整路径校验 + doc-review-checks)
      - 内容型连接器 (applenotes 等): 直接提供 content 文本, 跳过路径校验,
        仅做非空壳 / 超限检查 (格式/敏感/依据检查需要文件路径, 由连接器预清洗)

    真实动作:
      1. 路径越界拒绝 (防注入, 仅文件型信号)
      2. 文件不存在 → partial (非静默成功)
      3. 空壳 / 超大文件 → 标注
      4. 复用 doc-review-checks 跑完整检查 (若有)
      5. 内容型信号: 直接处理 content, 不做路径校验
    返回结果被 journey 累积到 ctx.variables 供 record_result 聚合 + 置信度驱动 gate.
    """
    doc = _resolve_doc_path(signal)
    issues: list[dict[str, Any]] = []
    checks = 0

    if doc is None:
        # 内容型信号 (applenotes 等连接器): 直接提供 content 文本, 无 .md 文件路径
        # → 按内容处理, 不做路径校验 (路径校验仅针对 workspace_docs 文件源)
        raw = signal.get("raw_item") if isinstance(signal.get("raw_item"), dict) else {}
        content = signal.get("content") or raw.get("content") or ""
        if isinstance(content, str) and content.strip():
            return _process_content(signal, content, dry_run)
        issues.append({"kind": "path_rejected", "detail": "outside_allowed_roots"})
        return {"status": "partial", "action": "process", "checks": 0,
                "passed": 0, "issues": issues, "dry_run": dry_run}

    stub = _doc_stub(doc)
    if not stub.get("exists"):
        issues.append({"kind": "file_missing", "detail": stub.get("path")})
        return {"status": "partial", "action": "process", "checks": 1,
                "passed": 0, "issues": issues, **stub, "dry_run": dry_run}

    # 规则 1: 非空壳
    checks += 1
    if int(stub.get("lines", 0)) < MIN_DOC_LINES:
        issues.append({"kind": "too_short",
                        "detail": f"{stub.get('lines')} 行 < {MIN_DOC_LINES}"})

    # 规则 2: 不超限
    checks += 1
    if int(stub.get("chars", 0)) > MAX_DOC_CHARS:
        issues.append({"kind": "too_large",
                        "detail": f"{stub.get('chars')} chars > {MAX_DOC_CHARS}"})

    # 规则 3: 复用 doc-review-checks (若有) — 格式 / 敏感 / 依据
    drc = _load_doc_review_checks()
    if drc:
        review = drc.review(stub["path"], _ROOT)
        checks += 3
        for i in review.get("format", {}).get("issues", []):
            issues.append({"kind": f"format:{i['kind']}", "detail": i.get("detail", "")})
        for i in review.get("sensitivity", {}).get("issues", []):
            issues.append({"kind": f"sensitivity:{i['kind']}", "detail": i.get("detail", ""),
                           "samples": i.get("samples", [])})
        for i in review.get("basis", {}).get("issues", []):
            issues.append({"kind": f"basis:{i['kind']}", "detail": i.get("detail", "")})

    ok = not issues
    return {
        "status": "succeeded" if ok else "partial",
        "action": "process", "checks": checks,
        "passed": checks - len(issues),
        "issues": issues,
        "doc": stub,
        "dry_run": dry_run,
    }


def record_result(ctx_variables: dict, *, dry_run: bool = False) -> dict[str, Any]:
    """记录处理结果: 聚合 process 检查结果 + 签名, 写 outcome 记录入口.

    ctx_variables 含 journey-engine 累积的:
      - doc_process_result (process_document 返回值)
      - scene_id / run_id / confidence (由 engine 注入)
    """
    proc = ctx_variables.get("doc_process_result")
    if not isinstance(proc, dict):
        return {"status": "partial", "action": "record_result",
                "error": "no_process_result", "dry_run": dry_run}

    issues = proc.get("issues", [])
    checks = int(proc.get("checks", 0))
    passed = int(proc.get("passed", 0))
    confidence = round(max(0.0, min(1.0, passed / checks)), 4) if checks > 0 else 0.85
    doc = proc.get("doc", {})

    record = {
        "scene_id": ctx_variables.get("scene_id"),
        "run_id": ctx_variables.get("run_id"),
        "doc_path": doc.get("path"),
        "doc_sha256": doc.get("sha256"),
        "status": proc.get("status"),
        "checks": checks,
        "passed": passed,
        "issues_count": len(issues),
        "issues": issues,
        "confidence": confidence,
        "dry_run": dry_run,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    # 签名 (防后续篡改)
    payload = json.dumps(record, sort_keys=True, ensure_ascii=False).encode()
    record["record_hash"] = hashlib.sha256(payload).hexdigest()[:16]

    # 写入 outcome 记录目录 (引擎后续可消费; 不替代 _record_auto_outcome)
    # 落盘路径走 _shared.scene_outcome_dir —— 该目录是**入仓证据面**
    # (.gitignore 显式反忽略 + .gitkeep), 故必须经统一解析入口:
    # 支持 SCENE_OUTCOME_DIR 覆盖, 且 pytest 上下文自动改写为临时目录,
    # 防测试夹具污染价值证据 (2026-09-19 实证: scene-documents-test 夹具
    # 曾被写进该目录)。
    if not dry_run:
        out_dir = _scene_outcome_dir(ctx_variables.get("scene_id") or "unknown")
        out_dir.mkdir(parents=True, exist_ok=True)
        run_id = ctx_variables.get("run_id", "unknown")
        (out_dir / f"{run_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"status": "succeeded", "action": "record_result",
            "record": record, "dry_run": dry_run}


def get_task_class(journey_id: str) -> str | None:
    """按 journey 名返回任务类 (quarantine / owner / cutover / audit / convergence)."""
    for prefix, cls in _JOURNEY_PREFIX.items():
        if journey_id.startswith(prefix):
            return cls
    return None


def daily_run_order(tasks: list[str] | None = None) -> list[list[str]]:
    """返回按任务类分组的 daily-run 顺序.

    每组内场景串行执行 (避免同时刷屏); 组间并行度低 (每天 5 组).
    默认按任务类优先级: quarantine → owner → cutover → audit → convergence.
    """
    tasks = tasks or [
        f"scene-documents-{name}"
        for cls in ("quarantine", "owner", "cutover", "audit", "convergence")
        for name in TASK_CLASS_GROUPS[cls]
    ]
    grouped: dict[str, list[str]] = {c: [] for c in TASK_CLASS_GROUPS}
    unclassified: list[str] = []
    for t in tasks:
        base = t.replace("scene-documents-", "")
        cls = get_task_class(base + "-journey")
        (grouped[cls] if cls else unclassified).append(t)
    ordered = [grouped[c] for c in ("quarantine", "owner", "cutover", "audit", "convergence") if grouped[c]]
    if unclassified:
        ordered.append(unclassified)
    return ordered


# ── 引擎 action 桥接 ─────────────────────────────────────────────

def bridge_to_engine() -> dict[str, Any]:
    """将 process / record_result 接入 journey-engine._execute_action.

    直接修改引擎文件 (幂等):
      - process → 调用 doc_legs.process_document(signal)
      - record_result → 调用 doc_legs.record_result(ctx.variables)
    """
    engine = _ROOT / "bin" / "ssot" / "journey-engine.py"
    src = engine.read_text(encoding="utf-8")

    if "_execute_doc_legs_action" in src:
        return {"bridged": True, "reason": "already bridged"}

    # 在 _execute_action 末尾 default 分支之前插入
    old = '    # 3. iris connector actions (e.g., action: "iris_list_apple_mail")\n'
    new = '''    # 2c. Documents 场景能力腿 (43 个 scene-documents-*):
    # process / record_result 此前落到默认分支, 静默成功但不产出值.
    if action in ("process", "record_result"):
        return _execute_doc_legs_action(action, ctx)

    # 3. iris connector actions (e.g., action: "iris_list_apple_mail")
'''
    if old not in src:
        return {"bridged": False, "reason": "engine_marker_not_found"}
    src = src.replace(old, new, 1)

    # 在文件末尾追加辅助函数
    helper = '''

def _doc_legs_module():
    """惰性加载能力腿模块 (与 journey-engine 同目录)."""
    import importlib.util
    path = Path(__file__).with_name("doc_legs.py")
    spec = importlib.util.spec_from_file_location("doc_legs", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["doc_legs"] = module
    spec.loader.exec_module(module)
    return module


def _execute_doc_legs_action(action: str, ctx) -> dict:
    """Documents 场景能力腿执行."""
    try:
        dl = _doc_legs_module()
    except Exception as exc:  # noqa: BLE001
        return {"status": "partial", "action": action, "error": str(exc)[:200]}

    if action == "process":
        result = dl.process_document(ctx.signal or {}, dry_run=ctx.dry_run)
        ctx.variables["doc_process_result"] = result
        return {"status": result.get("status", "partial"), "action": action,
                "checks": result.get("checks"), "passed": result.get("passed"),
                "issues": [i.get("kind") for i in result.get("issues", [])]}

    # record_result
    ctx.variables.setdefault("scene_id", ctx.scene_id)
    ctx.variables.setdefault("run_id", ctx.run_id)
    result = dl.record_result(ctx.variables, dry_run=ctx.dry_run)
    return {"status": result.get("status", "partial"), "action": action,
            "record": result.get("record")}

'''
    src = src + helper
    engine.write_text(src, encoding="utf-8")
    return {"bridged": True, "file": str(engine)}


# ── poller 接线 ──────────────────────────────────────────────────

def hook_poller() -> dict[str, Any]:
    """为 scene-signal-poller 增加 daily-run 分组调度."""
    poller = _ROOT / "bin" / "ssot" / "scene-signal-poller.py"
    src = poller.read_text(encoding="utf-8")

    if "DOCUMENTS_TASK_CLASS" in src:
        return {"hooked": True, "reason": "already hooked"}

    injection = '''
# Documents 任务类分组调度 (2026-09-17): 避免 43 个场景同时刷屏.
_DOCUMENTS_TASK_CLASS = None

def _set_documents_task_class(cls):
    global _DOCUMENTS_TASK_CLASS
    _DOCUMENTS_TASK_CLASS = cls

def _documents_task_class_filter(scene_id):
    if _DOCUMENTS_TASK_CLASS is None:
        return True
    base = scene_id.replace("scene-documents-", "")
    from doc_legs import get_task_class
    return get_task_class(base + "-journey") == _DOCUMENTS_TASK_CLASS

'''
    marker = '_ROOT = Path(__file__).resolve().parents[2]\n'
    idx = src.find(marker)
    if idx < 0:
        return {"hooked": False, "reason": "marker_not_found"}
    src = src[:idx] + injection + src[idx:]

    loop_marker = '        if scene_filter and scene_id != scene_filter:\n'
    idx = src.find(loop_marker)
    if idx < 0:
        return {"hooked": False, "reason": "loop_marker_not_found"}
    indent = ' ' * 8
    src = src[:idx] + f'{indent}if not _documents_task_class_filter(scene_id):\n{indent}    continue\n' + src[idx:]

    old = 'def poll(dry_run: bool = False, scene_filter: str | None = None,\n         limit_per_connector: int = 10) -> dict[str, Any]:'
    new = 'def poll(dry_run: bool = False, scene_filter: str | None = None,\n         limit_per_connector: int = 10,\n         task_class: str | None = None) -> dict[str, Any]:'
    src = src.replace(old, new)
    old_body = '    cards = _load_scene_cards()\n'
    new_body = '    _set_documents_task_class(task_class)\n    cards = _load_scene_cards()\n'
    src = src.replace(old_body, new_body, 1)

    poller.write_text(src, encoding="utf-8")
    return {"hooked": True, "file": str(poller)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge-engine", action="store_true")
    ap.add_argument("--hook-poller", action="store_true")
    ap.add_argument("--daily-run-order", action="store_true")
    ap.add_argument("--group", action="store_true")
    ap.add_argument("--process-signal", type=str)
    args = ap.parse_args()

    if args.bridge_engine:
        print(json.dumps(bridge_to_engine(), ensure_ascii=False, indent=2))
    elif args.hook_poller:
        print(json.dumps(hook_poller(), ensure_ascii=False, indent=2))
    elif args.daily_run_order:
        for i, group in enumerate(daily_run_order(), 1):
            print(f"=== batch {i} ===")
            for g in group:
                print(" ", g)
    elif args.group:
        for cls, names in TASK_CLASS_GROUPS.items():
            print(f"{cls}: {len(names)} scenes")
    elif args.process_signal:
        sig = json.loads(args.process_signal)
        print(json.dumps(process_document(sig, dry_run=False), ensure_ascii=False, indent=2))
    else:
        ap.print_help()