#!/usr/bin/env python3
"""Shadow Reporter — Shadow 场景观察报告器.

为 shadow 阶段的场景生成观察报告, 无需激活即可提供价值.
收集数据, 评估就绪度, 为激活决策提供依据.

用法:
    python3 shadow-reporter.py --all              # 报告所有 shadow 场景
    python3 shadow-reporter.py --scene <id>       # 报告指定场景
    python3 shadow-reporter.py --json             # JSON 输出
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENE_DIR = REPO / "docs/scene-cards"
REPORT_DIR = REPO / ".omo/_delivery/shadow-reports"


def load_scene_cards() -> list[dict]:
    """加载所有 scene cards."""
    scenes = []
    if not SCENE_DIR.exists():
        return scenes

    for f in sorted(SCENE_DIR.glob("*.yaml")):
        try:
            import yaml
            text = f.read_text()
            fm = None
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    fm = yaml.safe_load(text[3:end])
            if fm is None:
                fm = yaml.safe_load(text)
            if fm and isinstance(fm, dict):
                fm["_file"] = str(f.relative_to(REPO))
                scenes.append(fm)
        except Exception:
            continue

    return scenes


def generate_shadow_report(scene: dict) -> dict:
    """为 shadow 场景生成观察报告."""
    scene_id = scene.get("scene_id", scene.get("title", "?"))
    lifecycle = scene.get("lifecycle", "draft")
    blockers = scene.get("activation_blockers", [])
    approval = scene.get("approval_state", "")

    # 评估就绪度
    readiness = "ready" if not blockers and approval == "confirmed" else "blocked"
    if approval == "pending_business_confirmation":
        readiness = "needs_approval"

    report = {
        "scene_id": scene_id,
        "lifecycle": lifecycle,
        "activation": scene.get("activation", "?"),
        "approval_state": approval,
        "blockers": blockers,
        "readiness": readiness,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # 根据场景类型添加特定的观察数据
    if "project" in scene_id:
        report["observations"] = observe_project_supervision()
    elif "meeting" in scene_id:
        report["observations"] = observe_meeting_supervision()
    elif "report" in scene_id:
        report["observations"] = observe_periodic_reporting()
    elif "research" in scene_id:
        report["observations"] = observe_research_pipeline()
    elif "knowledge" in scene_id:
        report["observations"] = observe_knowledge_curation()
    elif "inbox" in scene_id:
        report["observations"] = observe_unified_inbox()

    return report


def observe_project_supervision() -> dict:
    """观察项目监督数据源."""
    plans_dir = REPO / "docs/plans"
    active_plans = []

    if plans_dir.exists():
        for f in plans_dir.glob("*.yaml"):
            try:
                import yaml
                content = yaml.safe_load(f.read_text())
                if isinstance(content, dict) and content.get("status") == "active":
                    active_plans.append({
                        "id": content.get("id", f.stem),
                        "title": content.get("title", "?"),
                    })
            except Exception:
                continue

    return {
        "data_source": "docs/plans/",
        "active_plans": len(active_plans),
        "sample_plans": active_plans[:5],
        "recommendation": f"可监督 {len(active_plans)} 个活跃项目",
    }


def observe_meeting_supervision() -> dict:
    """观察会议监督数据源."""
    # 检查是否有会议记录
    meeting_files = []
    for pattern in ["**/meeting*.md", "**/会议*.md", "**/minutes*.md"]:
        meeting_files.extend(REPO.glob(pattern))

    return {
        "data_source": "workspace meeting notes",
        "meeting_files_found": len(meeting_files),
        "sample_files": [str(f.relative_to(REPO)) for f in meeting_files[:5]],
        "recommendation": f"发现 {len(meeting_files)} 个会议记录文件, 可结构化",
    }


def observe_periodic_reporting() -> dict:
    """观察定期报告数据源."""
    # 检查 PR/CI 数据
    pr_data = list(REPO.glob("**/bin/scripts-*.json"))
    ci_data = list(REPO.glob("**/bin/scripts-*.jsonl"))

    return {
        "data_source": "PR/CI evidence",
        "pr_data_files": len(pr_data),
        "ci_data_files": len(ci_data),
        "recommendation": f"可聚合 {len(pr_data) + len(ci_data)} 个数据源生成周报",
    }


def observe_research_pipeline() -> dict:
    """观察研究管道数据源."""
    research_dir = REPO / "docs/research" if (REPO / "docs/research").exists() else None
    return {
        "data_source": "research notes",
        "research_dir_exists": research_dir is not None,
        "recommendation": "需要配置 iris 连接器 (rss/zhihu/wxread)",
    }


def observe_knowledge_curation() -> dict:
    """观察知识策展数据源."""
    knowledge_files = list(REPO.glob("docs/knowledge/**/*.md"))
    return {
        "data_source": "docs/knowledge/",
        "knowledge_files": len(knowledge_files),
        "recommendation": f"可策展 {len(knowledge_files)} 个知识文档",
    }


def observe_unified_inbox() -> dict:
    """观察统一收件箱数据源."""
    return {
        "data_source": "multi-channel messages",
        "channels": ["apple_mail", "netease_mail", "github", "personal_signals"],
        "recommendation": "需要配置邮件连接器",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Shadow Reporter")
    parser.add_argument("--all", action="store_true", help="Report all shadow scenes")
    parser.add_argument("--scene", help="Report specific scene")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    scenes = load_scene_cards()
    shadow_scenes = [s for s in scenes if s.get("lifecycle") == "shadow"]

    if args.scene:
        shadow_scenes = [s for s in shadow_scenes if args.scene in s.get("scene_id", "")]

    reports = []
    for scene in shadow_scenes:
        report = generate_shadow_report(scene)
        reports.append(report)

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Shadow Scene Observation Reports")
    print("=" * 56)
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Shadow scenes: {len(reports)}")
    print()

    for r in reports:
        icon = "✓" if r["readiness"] == "ready" else "⚠" if r["readiness"] == "needs_approval" else "✗"
        print(f"  {icon} {r['scene_id']}")
        print(f"      Readiness: {r['readiness']}")
        if r["blockers"]:
            print(f"      Blockers: {', '.join(r['blockers'])}")
        obs = r.get("observations", {})
        if obs:
            print(f"      Data: {obs.get('recommendation', '')}")
        print()


if __name__ == "__main__":
    sys.exit(main())
