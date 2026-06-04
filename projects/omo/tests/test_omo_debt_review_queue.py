from __future__ import annotations

from pathlib import Path

import pytest

from scripts.omo_debt_registry import DebtItem
from scripts.omo_debt_review_queue import build_review_queue


def _item(
    item_id: str,
    *,
    severity: str = 'medium',
    gate_level: str = 'none',
    next_review_at: str | None = '2026-06-09T00:00:00Z',
    last_reviewed_at: str | None = '2026-06-02T00:00:00Z',
    owner: str = 'omo-governance',
    evidence_refs: tuple[str, ...] = ('evidence.md',),
    mitigation_refs: tuple[str, ...] = ('mitigation.md',),
) -> DebtItem:
    return DebtItem(
        id=item_id,
        title=f'{item_id} title',
        dimension='governance_process',
        subdimension='cadence',
        domain='.omo',
        scope='governance_kernel',
        severity=severity,
        weight=0.2,
        entropy_class='pointer',
        lifecycle_state='scheduled',
        owner=owner,
        affected_roots=('.omo',),
        evidence_refs=evidence_refs,
        mitigation_refs=mitigation_refs,
        opened_at='2026-06-01T00:00:00Z',
        last_reviewed_at=last_reviewed_at,
        next_review_at=next_review_at,
        gate_level=gate_level,
        history=(),
    )


def test_build_review_queue_splits_due_upcoming_unscheduled_and_escalation_sections(tmp_path: Path) -> None:
    (tmp_path / 'evidence.md').write_text('evidence\n', encoding='utf-8')
    (tmp_path / 'mitigation.md').write_text('mitigation\n', encoding='utf-8')

    queue = build_review_queue(
        (
            _item('GATE_DUE', severity='critical', gate_level='gate', next_review_at='2026-06-05T00:00:00Z', owner='platform-governance'),
            _item('FUTURE_OK', severity='high', next_review_at='2026-06-12T00:00:00Z'),
            _item('UNSCHEDULED', owner='', next_review_at=None),
            _item('STALE_DUE', severity='medium', next_review_at='2026-06-06T00:00:00Z', mitigation_refs=()),
        ),
        now='2026-06-10T00:00:00Z',
        repo_root=tmp_path,
    )

    assert [entry['id'] for entry in queue['due_now']] == ['GATE_DUE', 'STALE_DUE']
    assert [entry['id'] for entry in queue['upcoming']] == ['FUTURE_OK']
    assert [entry['id'] for entry in queue['unscheduled']] == ['UNSCHEDULED']
    assert [entry['id'] for entry in queue['escalation_candidates']] == ['GATE_DUE', 'STALE_DUE']
    assert queue['unscheduled'][0]['owner'] == 'unowned'
    assert queue['summary']['due_now_count'] == 2
    assert queue['summary']['upcoming_count'] == 1
    assert queue['summary']['unscheduled_count'] == 1
    assert queue['summary']['by_owner'] == {
        'omo-governance': 2,
        'platform-governance': 1,
        'unowned': 1,
    }
    assert queue['summary']['by_severity'] == {
        'critical': 1,
        'high': 1,
        'medium': 2,
    }


def test_build_review_queue_rejects_invalid_timestamps(tmp_path: Path) -> None:
    (tmp_path / 'evidence.md').write_text('evidence\n', encoding='utf-8')
    (tmp_path / 'mitigation.md').write_text('mitigation\n', encoding='utf-8')

    with pytest.raises(ValueError, match='not-a-timestamp'):
        build_review_queue(
            (_item('BROKEN', next_review_at='not-a-timestamp'),),
            now='2026-06-10T00:00:00Z',
            repo_root=tmp_path,
        )
