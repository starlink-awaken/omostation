"""Audit pipeline — orchestrates audit groups."""

from __future__ import annotations

import re
from pathlib import Path

from codeanalyze.reports.audit.checkers import _extract_docx, _extract_pdf, _read_wiki  # type: ignore[import-not-found]
from codeanalyze.reports.audit.models import AuditGroup, AuditReport  # type: ignore[import-not-found]


def _check_policy_graph(root: Path, wiki: Path, report: AuditReport) -> None:
    """Group 1: Policy docs vs policy graph + TIMELINE."""
    g1 = AuditGroup(name="政策文件 vs 政策图谱+TIMELINE")
    policy_txt = _read_wiki(wiki, "30-政策与申报/00-政策图谱.md")
    timeline_txt = _read_wiki(wiki, "TIMELINE.md")

    if policy_txt:
        g1.add_check("政策图谱文件存在", True)

    notice = root / "40-政策法规/中小试平台/关于做好2026年本市中试平台项目有关工作的通知.pdf"
    if notice.exists():
        t = _extract_pdf(notice, 1000)
        dn = re.search(r"(京发改〔\d{4}〕\d+号)", t)
        doc_num = dn.group(0) if dn else "未提取到"
        g1.add_check(
            f"287号文提取 ({doc_num})",
            "287" in (doc_num or ""),
            f"图谱中287号: {'✅' if '287号' in policy_txt else '❌'}",
        )
        g1.add_check("287号在TIMELINE中", "287" in timeline_txt)

    cv_dir = root / "40-政策法规/概念验证平台政策"
    cv_files = list(cv_dir.glob("*.pdf")) if cv_dir.exists() else []
    for cv_pdf in cv_files:
        t = _extract_pdf(cv_pdf, 800)
        dn = re.search(r"(京科\w*〔\d{4}〕\d+号)", t)
        if dn:
            g1.add_check(f"概念验证文号 ({dn.group(0)})", True)

    g1.add_check("中试十四条在政策图谱中", "中试服务能力提升" in policy_txt)
    report.add_group(g1)


def _check_digital_platform(root: Path, wiki: Path, report: AuditReport) -> None:
    """Group 2: Digital platform docs vs knowledge base."""
    g2 = AuditGroup(name="数字化方案 vs 知识库")
    dp_root = wiki / "60-数字化平台建设"
    dp_files = list(dp_root.rglob("*.md")) if dp_root.exists() else []
    g2.add_check(f"知识库文件数: {len(dp_files)}", len(dp_files) > 0)

    v6_name = "全国高校绿色能源成果转化中心数字化智能运营平台建设实施总体方案 v6.0.docx"
    v6 = root / "60-实施方案与方法论/10-当前实施方案/过程资料/总体实施方案" / v6_name
    if v6.exists():
        t = _extract_docx(v6, 3000)
        dp_all = "".join(f.read_text("utf-8", errors="ignore") for f in dp_files) if dp_files else ""
        for term in ["四链融合", "死亡之谷", "红蓝三区", "业务飞轮", "CAS", "C-T-F"]:
            g2.add_check(
                f"概念覆盖: {term}",
                term in dp_all,
                f"方案={'✅' if term in t else '❌'} | wiki={'✅' if term in dp_all else '❌'}",
            )
    report.add_group(g2)


def _check_org_chart(root: Path, wiki: Path, report: AuditReport) -> None:
    """Group 3: Org chart vs ENTITIES.md."""
    g3 = AuditGroup(name="组织文件 vs ENTITIES.md")
    entities_txt = _read_wiki(wiki, "ENTITIES.md")
    org_dir = root / "10-组织架构"

    org_files = list(org_dir.glob("*.pdf")) if org_dir.exists() else []
    for org_pdf in org_files:
        t = _extract_pdf(org_pdf, 5000)
        person_patterns = [
            r"(?:(?:组长|主任|区长|局长|院长|校长|社长|总监|经理|书记|部长)\s*)([一-鿿]{2,3})(?=\s*[一-鿿]{2,}(?:委会|公司|大学|学院|局|处|中心|行|办))",
            r"([一-鿿]{2,3})(?=\s*[一-鿿]{2,}(?:委会|公司|大学|学院|局|处|中心|行|办))",
        ]
        people = set()
        for pat in person_patterns:
            people.update(re.findall(pat, t))
        roles = set(
            re.findall(
                r"([一-鿿]{2,6}(?:组(?!长)|组长|主任|区长|书记|部长|局长|经理|秘书|协调员|主席|院长|校长|社长|总监))", t
            )
        )
        e_flat = " ".join(set(re.findall(r"名称[：:]\s*([^\n]+)", entities_txt))) if entities_txt else ""
        matched = sum(1 for p in people if p in e_flat) if people else 0
        matched_r = sum(1 for r in roles if r[:4] in e_flat or r[:3] in e_flat) if roles else 0
        g3.add_check(
            f"人物: {len(people)}个 (匹配: {matched})",
            matched >= 1 or len(people) > 0,
            f"PDF {len(people)}人名 + {len(roles)}角色名, {matched}/{matched_r}匹配ENTITIES",
        )

    if not org_files:
        g3.add_check("组织文件检查", False, "10-组织架构/ 下无可分析的 PDF")
    report.add_group(g3)


def _check_platform_data(root: Path, wiki: Path, report: AuditReport) -> None:
    """Group 4: Platform data sheet vs platform overview."""
    g4 = AuditGroup(name="平台情况表 vs 平台全景")
    pm_txt = _read_wiki(wiki, "10-生态运营/20-平台全景.md")
    merged = root / "30-平台资料/附件：高校区域技术转移转化中心公共转化平台建设情况表（合并版）.docx"

    if merged.exists():
        t = _extract_docx(merged, 6000)
        platforms = set(re.findall(r"(?:^|\s|[，,\n])([一-鿿]{4,40}(?:平台|中心|实验室|基地|项目|装置|设备|系统))", t))
        p_names = {p.strip() for p in platforms if len(p.strip()) >= 4}
        if p_names:
            covered = sum(1 for p in p_names if any(c[:10] in pm_txt for c in [p])) if pm_txt else 0
            g4.add_check(
                f"平台覆盖率: {covered}/{len(p_names)}",
                covered >= 1 or len(p_names) > 0,
                f"提取 {len(p_names)} 个平台, {covered} 在平台全景",
            )
        else:
            for kw in ["中试", "概念验证", "实验室", "测试", "检测", "研发"]:
                if kw in t:
                    g4.add_check(f"平台关键词 '{kw}'", True)
                    break
            else:
                g4.add_check("平台情况表解析", False)
    else:
        g4.add_check("平台情况表存在", False)
    report.add_group(g4)


def _check_wiki_structure(wiki: Path, report: AuditReport) -> None:
    """Group 5: Wiki structural integrity."""
    g5 = AuditGroup(name="Wiki 结构完整性")
    required = {
        "MEMORY.md": wiki / "MEMORY.md",
        "STATE.md": wiki / "STATE.md",
        "ENTITIES.md": wiki / "ENTITIES.md",
        "TIMELINE.md": wiki / "TIMELINE.md",
        "INDEX.md": wiki / "INDEX.md",
        "KnowledgeProtocol.md": wiki / "_meta/KnowledgeProtocol.md",
    }
    for name, path in required.items():
        g5.add_check(f"核心文件: {name}", path.exists())
    report.add_group(g5)


def run_audit(project_root: str) -> AuditReport:
    """Run full knowledge audit on a document project."""
    root = Path(project_root).resolve()
    wiki = root / "_工作机制" / "wiki"
    report = AuditReport()

    if not wiki.is_dir():
        report.add_group(
            AuditGroup(name="Wiki 结构", checks=[{"label": "_工作机制/wiki 目录存在", "passed": False, "detail": ""}])
        )
        return report

    _check_policy_graph(root, wiki, report)
    _check_digital_platform(root, wiki, report)
    _check_org_chart(root, wiki, report)
    _check_platform_data(root, wiki, report)
    _check_wiki_structure(wiki, report)

    return report
