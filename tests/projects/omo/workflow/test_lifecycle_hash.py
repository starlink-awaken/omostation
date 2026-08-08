import pytest
from omo.workflow.lifecycle import claim_run, WorkflowError

def test_claim_run_requires_hash(tmp_path):
    with pytest.raises(WorkflowError, match="Missing or invalid affected-hash. You must run affected-graph.py first."):
        claim_run({}, "run123", "test_actor", ["projects/gbrain"], [], False, affected_hash=None)
