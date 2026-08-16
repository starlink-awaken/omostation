from __future__ import annotations

import kairon


def test_root_package_is_importable():
    assert kairon.__version__
    assert "agora" in kairon.workspace_packages()


def test_root_package_describe_reports_workspace_members():
    description = kairon.describe()

    assert description["name"] == "kairon"
    assert description["workspace_member_count"] >= 1  # type: ignore[reportOperatorIssue]
