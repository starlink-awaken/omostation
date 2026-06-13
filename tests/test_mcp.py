import json

from cockpit.scripts.cockpit_mcp import github_pr_review


def test_github_pr_review_empty_url():
    res = json.loads(github_pr_review(""))
    assert "error" in res
    assert res["error"] == "PR URL is required"


def test_github_pr_review_valid_url():
    res = json.loads(github_pr_review("https://github.com/org/repo/pull/123"))
    assert "error" not in res
    assert res["status"] == "reviewed"
    assert res["score"] == 85
    assert len(res["feedback"]) == 3
