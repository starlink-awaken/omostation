"""Tests for cockpit code CLI command routing."""

from unittest.mock import MagicMock, patch

from cockpit.cli import main


def test_code_workflow_missing_command(capsys):
    """Test 'cockpit code workflow' without specifying a subcommand."""
    with patch("sys.argv", ["cockpit", "code", "workflow"]):
        res = main()
        assert res == 1


@patch("subprocess.run")
@patch("pathlib.Path.exists")
def test_code_workflow_impact(mock_exists, mock_run, capsys):
    """Test 'cockpit code workflow impact' passes correct arguments to subprocess."""
    mock_run.return_value = MagicMock(returncode=0)
    mock_exists.return_value = True
    with patch("sys.argv", ["cockpit", "code", "workflow", "impact", "--symbol", "MyClass"]):
        res = main()

        # Check that we exited 0
        assert res == 0

        # Check the subprocess call arguments
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args

        # Expected command sequence
        expected_cmd = ["uv", "run", "--package", "codeanalyze", "codeanalyze", "workflow", "impact", "MyClass"]
        assert args[0] == expected_cmd


@patch("subprocess.run")
@patch("pathlib.Path.exists")
def test_code_analyze(mock_exists, mock_run, capsys):
    """Test 'cockpit code analyze' passes correct arguments to subprocess."""
    mock_run.return_value = MagicMock(returncode=0)
    mock_exists.return_value = True
    with patch("sys.argv", ["cockpit", "code", "analyze"]):
        res = main()

        # Check that we exited 0
        assert res == 0

        # Check the subprocess call arguments
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args

        # Expected command sequence
        expected_cmd = ["uv", "run", "--package", "codeanalyze", "codeanalyze", "analyze"]
        assert args[0] == expected_cmd
