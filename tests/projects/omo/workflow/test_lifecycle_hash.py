import pytest

from omo.workflow.lifecycle import WorkflowError, claim_run


def test_claim_run_requires_receipt(tmp_path):
    with pytest.raises(WorkflowError, match="Missing affected graph receipt"):
        claim_run(
            {},
            "run123",
            "test_actor",
            ["projects/gbrain"],
            [],
            False,
            affected_receipt=None,
        )
