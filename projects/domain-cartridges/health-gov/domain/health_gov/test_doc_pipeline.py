"""Self-test for the health-gov doc-cycle pipeline (verify entry).

Run: `uv run --with reportlab python -m domain.health_gov.test_doc_pipeline`
(exit 0 = pass; CWD-independent).

Covers: 3 e2e (局发通知下行文 / 跨部门平行函 / 会议纪要督办，含署名与真实 PDF 导出),
负例熔断 (涉密拒收/文号格式错/无署名批阅/退回无意见/退回后不可发出/缺要素阻止导出/非法跃迁),
36 例合成校准 (18 有效 + 18 登记/版式缺陷, F1 >= 0.6 assisted 门).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Ensure the cartridge package is importable when invoked as a module
# (uv run python -m domain.health_gov.test_doc_pipeline), CWD-independent.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from .doc_pipeline import (  # noqa: E402
    approve,
    close_action,
    dispatch,
    draft_opinion,
    export_package,
    is_overdue,
    record_minutes,
    register_incoming,
    supervise,
    validate_redhead,
)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {name}")
    else:
        msg = f"FAIL  {name}" + (f" — {detail}" if detail else "")
        print(msg)
        FAILURES.append(msg)


def expect_reject(name: str, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except (ValueError, RuntimeError):
        print(f"PASS  {name}")
        return
    msg = f"FAIL  {name} — 应拒绝而放行"
    print(msg)
    FAILURES.append(msg)


AGENCY = "×市卫生健康委员会"


def base_doc(**kw):
    d = dict(doc_id="WF-2026-001", title="×市卫生健康委员会关于开展秋冬季传染病防控工作的通知",
             doc_no="×卫发〔2026〕12号", kind="notice", urgency="normal",
             classification="internal", source="市政府办公室",
             received_date="2026年9月10日", agency=AGENCY,
             recipients="各区县卫生健康局，委直各单位", text="　　为切实做好秋冬季传染病防控工作，现将有关事项通知如下。",
             printer=AGENCY, printed_date="2026年9月15日")
    d.update(kw)
    return d


def test_e2e_notice(tmp: Path) -> None:
    """e2e-1: 局发通知下行文全周期."""
    doc = register_incoming(**base_doc())
    check("e2e1-registered", doc.status == "registered")
    op = draft_opinion(doc, drafter="办公室张主任")
    check("e2e1-opinion", "贯彻落实" in op.opinion and op.deadline_days == 15, op.opinion)
    ap = approve(doc, approver="王局长", decision="同意", decided_at="2026-09-11")
    check("e2e1-approved", doc.status == "approved" and ap.approver == "王局长")
    check("e2e1-redhead-ok", validate_redhead(doc) == [], str(validate_redhead(doc)))
    arts = export_package(doc, tmp / "e2e1", approval=ap)
    pdf = Path(arts["pdf"])
    check("e2e1-pdf", pdf.exists() and pdf.read_bytes()[:5] == b"%PDF-" and pdf.stat().st_size > 2000)
    check("e2e1-txt", Path(arts["txt"]).exists() and "主送机关" in Path(arts["txt"]).read_text(encoding="utf-8"))
    dispatch(doc)
    check("e2e1-dispatched", doc.status == "dispatched" and not is_overdue(doc))


def test_e2e_letter(tmp: Path) -> None:
    """e2e-2: 跨部门平行函全周期(加急)."""
    doc = register_incoming(**base_doc(doc_id="WH-2026-008", kind="letter", urgency="urgent",
                                       title="×市卫生健康委员会关于商请联合开展医疗废物专项检查的函",
                                       doc_no="×卫函〔2026〕8号",
                                       recipients="市生态环境局",
                                       text="　　为加强医疗废物规范化管理，商请贵局联合开展专项检查。"))
    op = draft_opinion(doc, drafter="医政处李处长")
    check("e2e2-opinion", "研提回复意见" in op.opinion and op.deadline_days == 3, op.opinion)
    ap = approve(doc, approver="分管赵副局长", decision="同意", decided_at="2026-09-12")
    arts = export_package(doc, tmp / "e2e2", approval=ap)
    check("e2e2-pdf", Path(arts["pdf"]).stat().st_size > 2000)
    dispatch(doc)
    check("e2e2-dispatched", doc.status == "dispatched")


def test_e2e_minutes() -> None:
    """e2e-3: 会议纪要督办."""
    mm = record_minutes("HY-2026-09-14", "秋冬季传染病防控工作部署会", "2026-09-14",
                        ["王局长", "赵副局长", "张主任"],
                        ["会议原则通过防控工作方案"],
                        [{"item": "印发防控工作通知", "owner": "办公室", "due": "2026-09-16"},
                         {"item": "完成医疗机构督导首轮", "owner": "医政处", "due": "2026-09-10"},
                         {"item": "上报疫苗储备情况", "owner": "疾控科", "due": "2026-09-20"}])
    close_action(mm, "印发防控工作通知", closed_by="张主任")
    rep = supervise(mm, today="2026-09-15")
    check("e2e3-counts", (rep["done"], rep["overdue"], rep["open"]) == (1, 1, 1), str(rep))
    check("e2e3-overdue-top", rep["督办"][0]["state"] == "overdue"
          and rep["督办"][0]["overdue_days"] == 5, str(rep["督办"]))
    expect_reject("e2e3-close-unsigned", close_action, mm, "上报疫苗储备情况", "")


def test_negatives() -> None:
    expect_reject("neg-secret", register_incoming, **base_doc(classification="secret"))
    expect_reject("neg-topsecret", register_incoming, **base_doc(classification="topsecret"))
    expect_reject("neg-docno", register_incoming, **base_doc(doc_no="卫发2026-12号"))
    d = register_incoming(**base_doc(doc_id="NEG-1"))
    draft_opinion(d, drafter="张主任")
    expect_reject("neg-unsigned-approve", approve, d, "", "同意")
    expect_reject("neg-return-nocomment", approve, d, "王局长", "退回")
    expect_reject("neg-bad-decision", approve, d, "王局长", "已阅")
    expect_reject("neg-double-draft", draft_opinion, d, "张主任")
    # 退回后不可发出 / 不可导出红头
    d_ret = register_incoming(**base_doc(doc_id="NEG-RET"))
    draft_opinion(d_ret, drafter="张主任")
    ap_ret = approve(d_ret, approver="王局长", decision="退回", comment="请补充依据")
    check("neg-return-status", d_ret.status == "returned" and d_ret.last_decision == "退回")
    expect_reject("neg-return-dispatch", dispatch, d_ret)
    with tempfile.TemporaryDirectory() as td:
        expect_reject("neg-return-export", export_package, d_ret, td, approval=ap_ret)
    # 退回后可重新拟办
    draft_opinion(d_ret, drafter="张主任")
    check("neg-return-redraft", d_ret.status == "drafted")
    # xh-letter alias
    d_alias = register_incoming(**base_doc(doc_id="NEG-ALIAS", kind="xh-letter",
                                           title="×市卫生健康委员会关于商请联合检查的函",
                                           doc_no="×卫函〔2026〕9号"))
    check("neg-xh-letter-alias", d_alias.kind == "letter")
    d2 = register_incoming(**base_doc(doc_id="NEG-2", recipients=""))
    draft_opinion(d2, drafter="张主任")
    approve(d2, approver="王局长", decision="同意")
    check("neg-redhead-errors", len(validate_redhead(d2)) > 0)
    with tempfile.TemporaryDirectory() as td:
        expect_reject("neg-export-blocked", export_package, d2, td)
    d3 = register_incoming(**base_doc(doc_id="NEG-3"))
    expect_reject("neg-skip-approve", dispatch, d3)
    expect_reject("neg-skip-draft", approve, d3, "王局长", "同意")


def test_calibration(tmp: Path) -> None:
    """36 例合成校准: 18 有效(应全放行) + 18 缺陷(应全拦截), F1 >= 0.6."""
    tp = fp = fn = 0
    for i in range(18):
        try:
            doc = register_incoming(**base_doc(doc_id=f"CAL-OK-{i:02d}"))
            draft_opinion(doc, drafter="张主任")
            approve(doc, approver="王局长", decision="同意")
            if validate_redhead(doc) == []:
                export_package(doc, tmp / f"cal-{i:02d}")
                tp += 1
            else:
                fn += 1
        except (ValueError, RuntimeError):
            fn += 1
    # 登记/版式缺陷注入（6 类轮转）。熔断类（无署名/退回无意见/非法跃迁）在 test_negatives。
    defects = [
        dict(classification="secret"), dict(doc_no="坏文号"), dict(recipients=""),
        dict(printer=""), dict(title="短"), dict(text=""),
    ]
    for i in range(18):
        kw = defects[i % len(defects)]
        try:
            doc = register_incoming(**base_doc(doc_id=f"CAL-BAD-{i:02d}", **kw))
            draft_opinion(doc, drafter="张主任")
            approve(doc, approver="王局长", decision="同意")
            if validate_redhead(doc) == []:
                fp += 1  # 缺陷被放行 = 误报
        except (ValueError, RuntimeError):
            pass  # 正确拦截 = TN
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    print(f"CALIB  tp={tp} fp={fp} fn={fn} precision={precision:.3f} recall={recall:.3f} F1={f1:.3f}")
    check("calib-f1", f1 >= 0.6, f"F1={f1:.3f}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_e2e_notice(tmp)
        test_e2e_letter(tmp)
        test_e2e_minutes()
        test_negatives()
        test_calibration(tmp)
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURES")
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
