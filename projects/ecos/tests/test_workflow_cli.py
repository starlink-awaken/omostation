"""mof-workflow CLI 集成测试 (P52)
验证所有子命令正常工作
"""

import sys
import subprocess
from pathlib import Path

WF_CLI = str(Path(__file__).parent.parent / "src" / "ecos" / "ssot" / "tools" / "mof-workflow.py")


def run(*args):
    return subprocess.run(["python3", WF_CLI] + list(args), capture_output=True, text=True)


class TestWorkflowCLI:
    def test_help(self):
        r = run("--help")
        assert r.returncode == 1
        assert "list" in r.stdout

    def test_stats(self):
        r = run("stats")
        assert r.returncode == 0
        assert "核心指标" in r.stdout

    def test_stats_json(self):
        r = run("stats", "--json")
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        assert data["total"] >= 26

    def test_list_all(self):
        r = run("list")
        assert r.returncode == 0

    def test_list_domain_filter(self):
        r = run("list", "--domain", "analysis")
        assert r.returncode == 0
        assert "Minerva" in r.stdout or "analysis" in r.stdout.lower()

    def test_list_json(self):
        r = run("list", "--json")
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        assert "workflows" in data
        assert data["total"] >= 26

    def test_show(self):
        r = run("show", "minerva-deep-research")
        assert r.returncode == 0
        assert "Minerva" in r.stdout
        assert "Decompose" in r.stdout

    def test_show_nonexistent(self):
        r = run("show", "nonexistent-workflow")
        assert r.returncode == 1

    def test_validate_all(self):
        r = run("validate")
        assert r.returncode == 0

    def test_validate_single(self):
        r = run("validate", "minerva-deep-research")
        assert r.returncode == 0

    def test_run_dry(self):
        r = run("run", "minerva-deep-research", "--dry-run")
        assert r.returncode == 0
        assert "干运行" in r.stdout or "dry" in r.stdout.lower()

    def test_relations_all(self):
        r = run("relations")
        assert r.returncode == 0

    def test_relations_single(self):
        r = run("relations", "minerva-deep-research")
        assert r.returncode == 0

    def test_graph_mermaid(self):
        r = run("graph", "--format", "mermaid")
        assert r.returncode == 0
        assert "graph TD" in r.stdout

    def test_graph_dot(self):
        r = run("graph", "--format", "dot")
        assert r.returncode == 0
        assert "digraph" in r.stdout

    def test_check_refs(self):
        r = run("check-refs")
        assert r.returncode == 0
        assert "通过" in r.stdout or "校验" in r.stdout
