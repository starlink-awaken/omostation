import pytest
from omo.workflow.lifecycle import WorkflowError, claim_run


def test_claim_run_requires_existing_run(tmp_path):
    with pytest.raises(WorkflowError, match="run not found"):
        claim_run(
            {},
            "run123",
            "test_actor",
            ["projects/knowledge/gbrain"],
            [],
            False,
            affected_receipt=None,
        )
